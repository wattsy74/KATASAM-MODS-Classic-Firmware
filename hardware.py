# hardware.py
__version__ = "4.0.0"

def get_version():
    return __version__
# Hardware setup and initialization functions for BGG Firmware
import board
import digitalio
import neopixel
import analogio
import microcontroller

def resolve_pin(pin_name):
    return getattr(board, pin_name)

def setup_buttons(cfg, raw_config):
    btns = {}
    for key, pin in cfg.items():
        if (
            isinstance(pin, microcontroller.Pin)
            and not key.endswith("_led")
            and key not in ("WHAMMY", "neopixel_pin", "joystick_x_pin", "joystick_y_pin")
        ):
            p = digitalio.DigitalInOut(pin)
            p.direction = digitalio.Direction.INPUT
            p.pull = digitalio.Pull.UP
            board_pin_name = raw_config.get(key) if isinstance(raw_config.get(key), str) and raw_config.get(key).startswith("GP") else None
            btns[key] = {"obj": p, "pin_name": key, "board_pin_name": board_pin_name}
    return btns

def setup_whammy(cfg):
    try:
        return analogio.AnalogIn(cfg["WHAMMY"])
    except:
        return None

def setup_leds(cfg):
    try:
        return neopixel.NeoPixel(cfg["neopixel_pin"], len(cfg["led_color"]), brightness=cfg["led_brightness"], auto_write=False)
    except Exception as e:
        print("NeoPixel init failed:", e)
        return None

