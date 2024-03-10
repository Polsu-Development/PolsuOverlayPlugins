from logging import Logger
from typing import Type, TypeVar
import keyboard

class Plugin:
    name = "KeybindsWindows"

    disabled = False
    version = "0.0.1"

    def __init__(
        self,
        logger: Logger,
        logs: Type[TypeVar("PluginLogs")], # type: ignore
        table: Type[TypeVar("PluginTable")], # type: ignore
        window: Type[TypeVar("PluginWindow")], # type: ignore
    ) -> None:
        """
        Initialise the plugin
        """
        self.logger = logger
        self.logs = logs
        self.table = table
        self.window = window

        self.hideOverlayKey = 1
        self.whoKey = 2
        self.reloadKey = 3
        
        self.open = True

    def hide_overlay_key(self):
        print("Hide overlay key function called")

    def who_key(self):
        print("Who key function called")
        self.logs.who()

    def reload_key(self):
        print("Reload key function called")
        self.table.resetTable()

    def on_load(self) -> None:
        """
        Called when the plugin is loaded
        """
        self.logger.info(f"Loaded {self.name} v{self.version}")
        keyboard.add_hotkey(self.hideOverlayKey, self.hide_overlay_key)
        keyboard.add_hotkey(self.whoKey, self.who_key)
        keyboard.add_hotkey(self.reloadKey, self.reload_key)