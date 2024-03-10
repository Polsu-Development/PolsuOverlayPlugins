from logging import Logger
from typing import Type, TypeVar
from pynput import keyboard

class Plugin:
    name = "KeybindsLinux"

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

        self.hideOverlayKey = keyboard.KeyCode.from_char(1)
        self.whoKey = keyboard.KeyCode.from_char(2)
        self.reloadKey = keyboard.KeyCode.from_char(3)
        self.keys = {
            self.hideOverlayKey: self.hide_overlay_key,
            self.whoKey: self.who_key,
            self.reloadKey: self.reload_key,
        }
        self.open = True

    def hide_overlay_key(self):
        print("Hide overlay key function called")

    def who_key(self):
        print("Who key function called")
        self.logs.who()

    def reload_key(self):
        print("Reload key function called")
        self.table.resetTable()

    def on_release(self, key):
        func = self.keys.get(key)
        if func:
            func()       
    
    def on_load(self) -> None:
        """
        Called when the plugin is loaded
        """
        self.logger.info(f"Loaded {self.name} v{self.version}")
        listener = keyboard.Listener(
            on_release=self.on_release)
        listener.start()