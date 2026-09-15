import winsound
import keyboard
import sounddevice as sd
import numpy as np
import threading
import time

def play_beep_start():
    try:
        winsound.Beep(1000, 150)
        winsound.Beep(1400, 150)
    except Exception:
        pass

def play_beep_end():
    try:
        winsound.Beep(1200, 120)
        winsound.Beep(800, 150)
    except Exception:
        pass

class HotkeyVoiceListener:
    def __init__(self, hotkey="F8"):
        self.hotkey = hotkey
        self.activated = False
        self._setup_hotkey()

    def _setup_hotkey(self):
        def on_hotkey():
            if not self.activated:
                print(f"\n⌨️ Atalho [{self.hotkey}] pressionado! Ativando Luna...")
                self.activated = True
        try:
            keyboard.add_hotkey(self.hotkey, on_hotkey)
        except Exception as e:
            print(f"Aviso de atalho: {e}")

    def wait_for_activation(self):
        self.activated = False
        while not self.activated:
            time.sleep(0.05)
        play_beep_start()
        return True
