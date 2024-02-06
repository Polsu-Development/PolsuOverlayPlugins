from logging import Logger
from typing import Type, TypeVar


import asyncio
import traceback

from aiohttp import ClientSession, ContentTypeError
from PyQt5.QtCore import QThread, pyqtSignal


class Plugin:
    name = "Seraph Blacklist Plugin"

    disabled = False
    version = "1.0.0"

    OVERRIDE_global_blacklist = True

    def __init__(
        self,
        logger: Logger,
        table: Type[TypeVar('PluginTable')],
        settings: Type[TypeVar('PluginSettings')],
        window: Type[TypeVar('PluginWindow')],
        notification: Type[TypeVar('PluginNotification')],
        player: Type[TypeVar('PluginPlayer')],
    ) -> None:    
        """
        Initialise the plugin
        """
        self.logger = logger
        self.table = table
        self.settings = settings
        self.window = window
        self.notification = notification
        self.player = player

        self.key = None

        self.bl_threads = {}
        self.sl_threads = {}
        self.cache = {}

        self.api = "https://api.seraph.si"
        self.headers = {
            "User-Agent": f"Polsu Overlay - Seraph Blacklist Plugin [{self.version}]",
        }

        logger.info("[SeraphBL] Plugin has been initialised!")


#┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n
#┃                                                                                                              ┃\n
#┃                                               >> EVENTS <<                                                   ┃\n
#┃                                                                                                              ┃\n
#┃  • The following events are called by the overlay.                                                           ┃\n
#┃                                                                                                              ┃\n
#┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n
    def on_load(self) -> None:
        """
        Called when the plugin is loaded
        """
        self.logger.info("[SeraphBL] Plugin has been loaded!")

        key = self.settings.getSetting("Seraph-APIKey")

        if not key:
            self.askForAPIKey()
        else:
            self.key = key
            self.headers["seraph-api-key"] = self.key


    def on_unload(self) -> None:
        """
        Called when the plugin is unloaded
        """
        self.logger.info("[SeraphBL] Plugin has been unloaded!")

    
    def on_player_insert(self, player: object) -> None:
        """
        Called when the player is inserted
        """
        self.logger.info(f"[SeraphBL] Player: {player.username} has been inserted! Looking up...")

        if player.uuid in self.cache:
            self.insertPlayer(player, self.cache[player.uuid])
        else:
            if player.uuid != "":
                try:
                    self.bl_threads[player.uuid] = BlacklistWorker(
                        api=self.api,
                        headers=self.headers,
                        key=self.key,
                        player=player,
                    )
                    self.bl_threads[player.uuid].playerData.connect(self.insertPlayer)
                    self.bl_threads[player.uuid].start()
                except:
                    self.logger.error(f"[SeraphBL] Failed to get player: {player.username}!\n\nTraceback: {traceback.format_exc()}")

    
    def on_final_kill(self, player: str) -> None:
        """
        Called when a player is a final kill
        """
        self.logger.info(f"[SeraphBL] Player: {player} has been killed! Sending data...")

        player = self.player.getCache(player)

        if not player:
            self.logger.error(f"[SeraphBL] Failed to get player: {player}!")

        if player:
            self.sl_threads[player.uuid] = SafelistWorker(
                api=self.api,
                headers=self.headers,
                key=self.key,
                player=player,
            )
            self.sl_threads[player.uuid].start()


#┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n
#┃                                                                                                              ┃\n
#┃                                             >> FUNCTIONS <<                                                  ┃\n
#┃                                                                                                              ┃\n
#┃  • The following functions are used by the plugin.                                                           ┃\n
#┃                                                                                                              ┃\n
#┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n
    def insertPlayer(self, player: object, data: dict) -> None:
        """
        Insert the player into the table
        
        :param data: The data to insert
        """
        if data == {}:
            return
        else:
            self.cache[player.uuid] = data

            tooltip = ""
            icon = None

            if data.get("blacklist", {}).get("tagged", False):
                reason = data.get('blacklist', {}).get('reason', 'Unknown').replace('\n', '<br>')
                tooltip += f"<b>Blacklisted</b><br>{reason}<br>Type: {data.get('blacklist', {}).get('report_type', 'Unknown').title()}<br><br>"
                icon = "custom-blacklist"
            if data.get("annoylist", {}).get("tagged", False):
                reason = data.get('annoylist', {}).get('tooltip', 'Unknown').replace('\n', '<br>')
                tooltip += f"<b>Annoylisted</b><br>{reason}<br><br>"

                if not icon:
                    icon = "annoying"
            if data.get("safelist", {}).get("tagged", False):
                reason = data.get('safelist', {}).get('tooltip', 'Unknown').replace('\n', '<br>')
                tooltip += f"<b>Safelisted</b><br>{reason}<br>Times Killed: {data.get('safelist', {}).get('timesKilled', 0)}<br>Security Level: {data.get('safelist', {}).get('security_level', 0)}<br><br>"
                
                if not icon:
                    icon = "verified"

            tooltip += f"<b>Statistics</b><br>Encounters: {data.get('statistics', {}).get('encounters', 0)}<br>Threat Level: {data.get('statistics', {}).get('threat_level', 0)}"

            if not icon:
                icon = "info"

            if data.get("name_change", {}).get("changed", False):
                tooltip += f"<br><br><b>Name Changed Recently!</b>"

            self.table.setGlobalBlacklist(
                uuid=player.uuid, 
                tooltip=tooltip,
                icon=icon,
                text=f"{data.get('statistics', {}).get('encounters', 0):,d}"
            )

            if data.get("blacklist", {}).get("tagged", False):
                self.table.setLineColour(player.uuid, "#FF0000")
            elif data.get("annoylist", {}).get("tagged", False):
                self.table.setLineColour(player.uuid, "#FFFF00")
            elif data.get("safelist", {}).get("tagged", False):
                self.table.setLineColour(player.uuid, "#00AA00")


    def askForAPIKey(self) -> None:
        """
        Ask for the API key
        """
        self.logger.info("[SeraphBL] Asking for API key!")

        key = self.window.ask(
            title="Seraph Blacklist Plugin",
            message="Please enter your Seraph API Key:",
        )

        if key == "":
            self.disabled = True
            self.notification.send(
                title="Seraph Blacklist Plugin",
                message="You have not entered an API key. Therefore, the plugin was disabled.",
            )
        else:
            self.settings.updateSetting("Seraph-APIKey", key)
            self.key = key


#┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n
#┃                                                                                                              ┃\n
#┃                                              >> WORKERS <<                                                   ┃\n
#┃                                                                                                              ┃\n
#┃  • The following workers are used by the plugin to send API requests.                                        ┃\n
#┃                                                                                                              ┃\n
#┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n
class BlacklistWorker(QThread):
    """
    The worker class, used to get blacklist data
    """
    playerData= pyqtSignal(object, dict)

    def __init__(self, api: str, headers: dict, key: str, player: object) -> None:
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
        self.player = player
 

    def run(self) -> None:
        """
        Run the thread
        """
        try:
            self.playerData.emit(self.player, asyncio.run(self.getPlayer(self.player.uuid)))
        except Exception as e:
            print(e)
            self.playerData.emit(self.player, {})


    async def getPlayer(self, uuid: str) -> dict:
        """
        Get the player from the API
        
        :param uuid: The UUID of the player
        :return: The player data
        """
        try:
            async with ClientSession() as session:
                async with session.get(f"{self.api}/blacklist/{uuid}", headers=self.headers) as response:
                    json = await response.json()

                    if not json["success"]:
                        return {}
                    else:
                        return json["data"]
        except ContentTypeError:
            return {}


class SafelistWorker(QThread):
    """
    The worker class, used to get safelist data
    """
    def __init__(self, api: str, headers: dict, key: str, player: object) -> None:
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
        self.player = player
 

    def run(self) -> None:
        """
        Run the thread
        """
        try:
            asyncio.run(self.getPlayer(self.player.uuid))
        except:
            pass


    async def getPlayer(self, uuid: str) -> dict:
        """
        Get the player from the API
        
        :param uuid: The UUID of the player
        :return: The player data
        """
        try:
            async with ClientSession() as session:
                async with session.get(f"{self.api}/safelist/{uuid}", headers=self.headers) as response:
                    json = await response.json()

                    if not json["success"]:
                        return {}
                    else:
                        return json["data"]
        except ContentTypeError:
            return {}
