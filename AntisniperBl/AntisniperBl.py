from logging import Logger
from typing import Type, TypeVar

from datetime import datetime

import asyncio
import traceback

from aiohttp import ClientSession, ContentTypeError
from PyQt5.QtCore import QThread, pyqtSignal


class Plugin:
    name = "AntisniperBL"

    disabled = False
    version = "0.0.1"

    def __init__(
        self,
        logger: Logger,
        table: Type[TypeVar("PluginTable")],
        settings: Type[TypeVar("PluginSettings")],
        window: Type[TypeVar("PluginWindow")],
        notification: Type[TypeVar("PluginNotification")],
    ) -> None:
        """
        Initialise the plugin
        """
        self.logger = logger
        self.table = table
        self.settings = settings
        self.window = window
        self.notification = notification

        self.key = None

        self.bl_tokens = []

        self.bl_threads = {}
        self.ws_threads = {}

        self.headers = {}
        self.blacklist_cache = {}

        self.api = "https://api.antisniper.net/"

        logger.info("[AntisniperBL] Plugin has been initialised!")


    # ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n
    # ┃                                                                                                              ┃\n
    # ┃                                               >> EVENTS <<                                                   ┃\n
    # ┃                                                                                                              ┃\n
    # ┃  • The following events are called by the overlay.                                                           ┃\n
    # ┃                                                                                                              ┃\n
    # ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n
    def on_load(self) -> None:
        """
        Called when the plugin is loaded
        """
        self.logger.info("[AntisniperBL] Plugin has been loaded!")

        key = self.settings.getSetting("Antisniper-APIKey")

        bl_tokens = self.settings.getSetting("Antisniper-BlacklistTokens")

        if not bl_tokens:
            self.settings.updateSetting("Antisniper-BlacklistTokens", [])
        else:
            self.bl_tokens = bl_tokens

        if not key:
            self.ask_for_apikey()
        else:
            valid = asyncio.run(self.validate_apikey(key))

            if not valid:
                self.notification.send(
                    title="AntisniperBL Plugin",
                    message="API key is invalid. Please enter a working one.",
                )
                self.ask_for_apikey()
            self.key = key
            self.headers["Apikey"] = self.key


    def on_unload(self) -> None:
        """
        Called when the plugin is unloaded
        """
        self.logger.info("[AntisniperBL] Plugin has been unloaded!")


    def on_who(self, players: object) -> None:
        """
        Called when the who command is executed
        """
        self.update_blacklist(players)


    def on_list(self, players: object) -> None:
        """
        Called when the list command is executed
        """
        self.update_blacklist(players)


    def on_player_insert(self, player: object) -> None:
        """
        Called when the player is inserted
        """
        self.logger.info(
            f"[AntisniperBL] Player: {player.username} has been inserted! Looking up..."
        )

        if player.username in self.blacklist_cache:
            self.insert_player(player, self.blacklist_cache[player.username])
        else:
            if player.uuid != "":
                try:
                    self.bl_threads[player.uuid] = BlacklistWorker(
                        api=self.api,
                        headers=self.headers,
                        key=self.key,
                        players=player.username,
                        bl_tokens=self.bl_tokens,
                    )
                    self.bl_threads[player.uuid].playerData.connect(
                        lambda name, data: self.insert_player(player, data)
                    )
                    self.bl_threads[player.uuid].start()
                except:
                    self.logger.error(
                        f"[AntisniperBL] Failed to get player: {player.username}!\n\nTraceback: {traceback.format_exc()}"
                    )


    # ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n
    # ┃                                                                                                              ┃\n
    # ┃                                             >> FUNCTIONS <<                                                  ┃\n
    # ┃                                                                                                              ┃\n
    # ┃  • The following functions are used by the plugin.                                                           ┃\n
    # ┃                                                                                                              ┃\n
    # ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n
    def insert_player(self, player: object, data: dict) -> None:
        """
        Insert the player into the table

        :param data: The data to insert
        """
        if data == {}:
            return
        else:
            tooltip = ""
            icon = None

            if data.get("blacklisted"):
                reasons = data.get("reasons", ["Unknown"])
                tooltip += "<b>Blacklisted</b><br>"
                if not reasons:
                    tooltip += "Unknown reason<br>"
                else:
                    tooltip += "<b>Reasons</b><br>"
                for reason in reasons:
                    tooltip += f"{reason}<br>"

                tooltip += f"Added: {datetime.fromtimestamp(data.get('added'))}"

                icon = "custom-blacklist"

                self.table.setGlobalBlacklist(
                    uuid=player.uuid, tooltip=tooltip, icon=icon
                )
                if data.get("blacklisted"):
                    self.table.setLineColour(player.uuid, "#FF0000")


    def update_blacklist(self, players: object) -> None:
        """
        Update the blacklist

        :param players: The players to update
        """
        not_cached = []

        for player in players:
            if not player in self.blacklist_cache:
                not_cached.append(player)

        if not_cached:
            try:
                self.bl_threads["all"] = BlacklistWorker(
                    api=self.api,
                    headers=self.headers,
                    key=self.key,
                    players=not_cached,
                    bl_tokens=self.bl_tokens,
                )
                self.bl_threads["all"].playerData.connect(self.add_to_cache)
                self.bl_threads["all"].start()
            except:
                self.logger.error(
                    f"[AntisniperBL] Failed to get players: {not_cached}!\n\nTraceback: {traceback.format_exc()}"
                )


    def add_to_cache(self, player: object, data: object) -> None:
        """
        Add the player to the cache
        """
        self.blacklist_cache[player] = data


    def ask_for_apikey(self) -> None:
        """
        Ask for the API key
        """
        self.logger.info("[AntisniperBL] Asking for API key!")

        key = self.window.ask(
            title="AntisniperBL Plugin",
            message="Please enter your Antisniper API Key:",
        )

        if key == "":
            self.disabled = True
            self.notification.send(
                title="AntisniperBL Plugin",
                message="You have not entered an API key. Therefore, the plugin was disabled.",
            )
        else:
            valid = asyncio.run(self.validate_apikey(key))
            if valid:
                self.notification.send(
                    title="AntisniperBL Plugin",
                    message="API key is valid!",
                )
                self.settings.updateSetting("Antisniper-APIKey", key)
                self.key = key
                self.headers["Apikey"] = self.key
            else:
                self.notification.send(
                    title="AntisniperBL Plugin",
                    message="API key is invalid. Therefore, the plugin was disabled.",
                )
                self.disabled = True


    async def validate_apikey(self, key: str) -> bool:
        """
        Validate the API key

        :param key: The API
        """
        try:
            async with ClientSession() as session:
                async with session.get(
                    f"{self.api}/v2/user", headers={"Apikey": key}
                ) as response:
                    json = await response.json()

                    if not json["success"]:
                        return False
                    else:
                        return True
        except ContentTypeError:
            return False


# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n
# ┃                                                                                                              ┃\n
# ┃                                              >> WORKERS <<                                                   ┃\n
# ┃                                                                                                              ┃\n
# ┃  • The following workers are used by the plugin to send API requests.                                        ┃\n
# ┃                                                                                                              ┃\n
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n
class BlacklistWorker(QThread):
    """
    The worker class, used to get blacklist data
    """

    playerData = pyqtSignal(object, dict)

    def __init__(
        self, api: str, headers: dict, key: str, players: object, bl_tokens: list
    ) -> None:
        """
        Initialise the class

        :param api: The API URL
        :param headers: The API headers
        :param key: The API key
        :param player: The player object
        """
        super(QThread, self).__init__()
        self.api = api
        self.headers = headers
        self.key = key
        self.players = players
        self.bl_tokens = bl_tokens

    def run(self) -> None:
        """
        Run the thread
        """
        try:
            if self.bl_tokens:
                for i in range(0, len(self.bl_tokens), 20):
                    asyncio.run(
                        self.post_players(self.players, self.bl_tokens[i : i + 20])
                    )

            asyncio.run(self.post_players(self.players, []))
        except Exception as e:
            print(e)

    async def post_players(self, players: list, bl_tokens: list) -> dict:
        """
        Get the players from the API

        :param players: The players
        :return: The players data
        """

        if not isinstance(players, list):
            players = [players]
        try:
            async with ClientSession() as session:
                async with session.post(
                    f"{self.api}/v2/blacklist",
                    headers=self.headers,
                    json=(
                        {"players": players}
                        if not bl_tokens
                        else {"players": players, "tokens": bl_tokens}
                    ),
                ) as response:
                    json = await response.json()

                    if not json["success"]:
                        return {}
                    else:
                        for player in json["data"]:
                            self.playerData.emit(player["ign"], player)
        except ContentTypeError:
            return {}
