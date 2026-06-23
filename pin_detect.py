# pin_detect.py v3.9.26
__version__ = "3.9.26"

def get_version():
    return __version__

"""
Pin detection logic for BGG Firmware
- Deinit all button pins
- Poll all digital pins for activity
- Map detected pin to logical button
- Save/cancel logic for config update and reboot
"""


import board
import microcontroller
import digitalio
import time
import json

# Load exclusion list from pin_detect_config.json
try:
    with open("/pin_detect_config.json", "r") as f:
        pin_detect_config = json.load(f)
    DIGITAL_PINS = set(pin_detect_config.get("digital_pins", []))
    RESERVED_PINS = set(pin_detect_config.get("reserved_pins", []))
    ANALOG_PINS = set(pin_detect_config.get("analog_pins", []))
    LED_PINS = set(pin_detect_config.get("led_pins", []))

except Exception as e:
    print(f"[PIN DETECT] Could not load exclusion list: {e}")
    EXCLUDED_PINS = []

PIN_DETECT_VERSION = "2.1"

def get_version():
    return PIN_DETECT_VERSION

# List all digital pins available on the board, excluding reserved/analog pins
# Load pin lists from pin_detect_config.json
try:
    with open("/pin_detect_config.json", "r") as f:
        pin_detect_config = json.load(f)
except Exception as e:
    print(f"[PIN DETECT] Could not load pin config: {e}")
    DIGITAL_PINS = set()
    RESERVED_PINS = set()
    ANALOG_PINS = set()
    LED_PINS = set()

# Only use digital pins that are not reserved, analog, or LED pins
ALL_DIGITAL_PINS = [
    pin for pin in DIGITAL_PINS
    if pin not in RESERVED_PINS and pin not in ANALOG_PINS and pin not in LED_PINS
]

# Deinit all button pins (pass in buttons dict)
def deinit_all_buttons(buttons):
    for pin in buttons.values():
        try:
            pin["obj"].deinit()
        except Exception:
            pass

# Poll all digital pins for activity
def detect_pin(button_name, duration=5):
    print(f"[PIN DETECT] Starting detection for {button_name}")
    detected_pin = None
    start = time.monotonic()
    pin_objs = {}
    # Initialize all pins as inputs with pullups using digitalio
    for pin_name in ALL_DIGITAL_PINS:
        try:
            pin_obj = getattr(board, pin_name)
            pin = digitalio.DigitalInOut(pin_obj)
            pin.direction = digitalio.Direction.INPUT
            pin.pull = digitalio.Pull.UP
            pin_objs[pin_name] = pin
            print(f"[PIN DETECT] Added pin: {pin_name}")
        except Exception as e:
            print(f"[PIN DETECT] Failed to add pin: {pin_name} ({e})")
    print(f"[PIN DETECT] Monitoring pins: {list(pin_objs.keys())}")
    while time.monotonic() - start < duration:
        for pin_name, pin in pin_objs.items():
            try:
                if not pin.value:  # Button pressed (active low)
                    detected_pin = pin_name
                    print(f"[PIN DETECT] Detected {pin_name}")
                    break
            except Exception:
                pass
        if detected_pin:
            break
        time.sleep(0.01)
    # Deinit all pin objects
    for pin in pin_objs.values():
        try:
            pin.deinit()
        except Exception:
            pass
    return detected_pin

# Save detected pin to config and reboot
def save_detected_pin(config_path, button_name, pin_name):
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        config[button_name] = pin_name
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"[PIN DETECT] Saved {button_name}: {pin_name} to config")
        microcontroller.reset()
    except Exception as e:
        print(f"[PIN DETECT] Failed to save pin: {e}")

# Cancel pin detect and reboot
def cancel_pin_detect():
    print("[PIN DETECT] Cancelled, rebooting...")
    microcontroller.reset()
