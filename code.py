FIRMWARE_VERSIONS = {
    "code.py": "5.0.1",
    "hardware.py": "5.0.1",
    "utils.py": "5.0.1",
    "gamepad.py": "5.0.1",
    "serial_handler.py": "5.0.1",
    "pin_detect.py": "5.0.1",
    "boot.py": "5.0.1",
    "demo_routine.py": "5.0.1",
    "demo_state.py": "5.0.1"
}

# BGG Firmware v5.0.1 - Preset Slot Switching Development
# - Based on working v5.0.1 firmware
# - Incremental guide mode implementation with live preview testing
# - Conditional debug output prevents firmware corruption
# - Maintains v5.0.1 stability with communication improvements

def get_firmware_versions():
    return FIRMWARE_VERSIONS

import usb_cdc
try:
    from demo_routine import run_demo_generator
    demo_routine_available = True
except ImportError:
    print("demo_routine.py not found - demo functionality disabled")
    demo_routine_available = False
try:
    from demo_state import demo_gen
    demo_state_available = True
except ImportError:
    print("demo_state.py not found - demo functionality disabled")
    demo_state_available = False
import time
import json
import board
import microcontroller
import analogio
from hardware import resolve_pin, setup_buttons, setup_whammy, setup_leds
from utils import hex_to_rgb, load_config
from gamepad import CustomGamepad
from serial_handler import handle_serial

try:
    with open("/config.json", "r") as f:
        raw_config = json.load(f)
    print("config.json loaded")
except Exception as e:
    print("Failed to load config.json:", e)
    raw_config = {}

config = load_config(raw_config, resolve_pin)

gp = CustomGamepad()
buttons = setup_buttons(config, raw_config)
whammy = setup_whammy(config)
leds = setup_leds(config)
previous_virtual_guide = False

# Setup joystick pins from config
joystick_x = analogio.AnalogIn(config.get("joystick_x_pin", board.GP28))
joystick_y = analogio.AnalogIn(config.get("joystick_y_pin", board.GP29))
hat_mode = config.get("hat_mode", "joystick")  # default to joystick

# Whammy calibration/config values
WHAMMY_MIN = config.get("whammy_min", 32000)
WHAMMY_MAX = config.get("whammy_max", 65400)
WHAMMY_REVERSE = config.get("whammy_reverse", False)

def map_whammy(raw):
    # Clamp and scale whammy value to 0-255
    v = max(WHAMMY_MIN, min(WHAMMY_MAX, raw))
    norm = (v - WHAMMY_MIN) / (WHAMMY_MAX - WHAMMY_MIN) if WHAMMY_MAX > WHAMMY_MIN else 0
    if WHAMMY_REVERSE:
        norm = 1.0 - norm
    return int(norm * 255)

current_state = {k: False for k in buttons}
user_presets = {}
preset_colors = {}

# Guide Button Input Detection Variables
guide_button_pressed = False
guide_button_press_time = None  # Time when GUIDE was first pressed (in seconds)
guide_entry_detected = False  # Flag to avoid repeated detection
guide_triple_press_count = 0  # Counter for triple-press detection
guide_last_press_time = None  # Time of last guide button press (for triple-press timeout)
GUIDE_HOLD_DURATION = 1.0  # 1 second hold to enter guide mode
GUIDE_TRIPLE_PRESS_TIMEOUT = 0.5  # 500ms window for triple-press

# Guide Mode State Variables
guide_mode_active = False  # Flag for being in guide mode
current_guide_slot = 1  # Current slot being viewed (1-6) for USER presets
guide_preset_type = "user"  # "user" or "standard" - which preset type to display
current_standard_preset_index = 0  # Current index in standard presets list
guide_mode_entry_time = None  # Time when guide mode was entered
GUIDE_MODE_TIMEOUT = 30.0  # Exit guide mode after 30 seconds of inactivity
guide_mode_last_action_time = None  # Track last button press for timeout

# Demo Mode State Variables
demo_mode_active = False  # Flag for demo mode
demo_preset_index = 0  # Current preset being displayed
demo_last_change_time = None  # Track time for preset intervals
DEMO_PRESET_INTERVAL = 2.4  # Change preset every 2.4 seconds (tiltwave duration)
demo_tiltwave_triggered = False  # Track if tiltwave was triggered on this transition

# Tilt Wave Effect Variables - Enhanced for dynamic 7-LED effect
tilt_wave_enabled = config.get("tilt_wave_enabled", True)
tilt_wave_active = False
tilt_wave_step = 0
tilt_wave_max_steps = 120  # 2.4 seconds for longer, flashier effect
previous_tilt_state = False
tilt_wave_led_counter = 0  # Counter to throttle LED updates
stored_led_colors = []  # Store current LED state before wave (dynamic size)

# Enhanced wave colors - brighter, more dynamic blues and whites
WAVE_COLORS = [
    (0, 0, 255),      # Deep blue
    (0, 100, 255),    # Bright blue
    (0, 150, 255),    # Electric blue  
    (50, 200, 255),   # Cyan-blue
    (100, 220, 255),  # Light electric blue
    (150, 240, 255),  # Bright cyan
    (200, 250, 255),  # Nearly white-blue
    (255, 255, 255),  # Pure white (peak)
    (200, 250, 255),  # Bright cyan (fade back)
    (150, 240, 255),  # Light electric blue
    (100, 220, 255),  # Electric blue
    (50, 200, 255),   # Cyan-blue
    (0, 150, 255),    # Electric blue
    (0, 100, 255),    # Bright blue
    (0, 50, 255),     # Deep blue
    (0, 25, 128),     # Darker blue
    (0, 12, 64),      # Very dark blue
    (0, 0, 32),       # Almost off
    (0, 0, 0)         # Off
]

def start_tilt_wave():
    """Start the enhanced blue tilt wave effect - stores current colors first"""
    global tilt_wave_active, tilt_wave_step, stored_led_colors
    if tilt_wave_enabled and leds is not None:
        # Store current LED colors before starting wave (dynamic size)
        stored_led_colors = []
        for i in range(len(leds)):
            stored_led_colors.append(tuple(leds[i]))
        
        tilt_wave_active = True
        tilt_wave_step = 0

def update_tilt_wave():
    """Update the enhanced tilt wave animation - dynamic multi-LED cascading effect"""
    global tilt_wave_active, tilt_wave_step, tilt_wave_led_counter
    
    if not tilt_wave_active or leds is None:
        return False
    
    # Only update LEDs every 2nd cycle (reduce from 100Hz to 50Hz for smoother animation)
    tilt_wave_led_counter += 1
    if tilt_wave_led_counter < 2:
        return True
    tilt_wave_led_counter = 0
    
    # Check if animation is complete
    if tilt_wave_step >= tilt_wave_max_steps:
        # Restore original colors and end animation
        for i in range(len(leds)):
            if i < len(stored_led_colors):
                leds[i] = stored_led_colors[i]
        leds.show()
        tilt_wave_active = False
        # Refresh LEDs to current button states to avoid stale animation frame
        update_leds()
        return False
    
    # Enhanced cascading wave effect across all LEDs
    # Create a traveling wave that sweeps across LEDs with trailing effects
    led_count = len(leds)
    
    # Calculate wave position (0 to led_count-1, with extra time for full fade)
    wave_cycles = 3  # Number of complete sweeps
    total_sweep_steps = tilt_wave_max_steps // wave_cycles
    current_cycle_step = tilt_wave_step % total_sweep_steps
    
    # Wave position calculation - sweeps left to right multiple times
    wave_position = (current_cycle_step * (led_count * 2)) // total_sweep_steps  # 0 to (led_count*2-1) range for smooth travel
    
    for led_index in range(led_count):
        # Calculate distance from wave center
        distance = abs(led_index * 2 - wave_position)  # Scale LED positions
        
        # Multiple wave effects:
        if distance == 0:
            # Direct hit - brightest color
            color_idx = 7  # Pure white peak
        elif distance == 1:
            # Adjacent - very bright
            color_idx = 5 + (current_cycle_step % 3)  # Cycle through bright colors
        elif distance == 2:
            # Near - bright blue
            color_idx = 3 + (current_cycle_step % 2)
        elif distance <= 4:
            # Trailing effect - medium blue
            color_idx = max(0, 4 - distance)
        else:
            # Far from wave - dim or off
            color_idx = 0
        
        # Add some sparkle effects on secondary cycles
        cycle_num = tilt_wave_step // total_sweep_steps
        if cycle_num > 0 and (led_index + tilt_wave_step) % led_count == 0:
            color_idx = min(len(WAVE_COLORS) - 1, color_idx + 3)  # Extra brightness
        
        # Clamp color index
        color_idx = min(len(WAVE_COLORS) - 1, max(0, color_idx))
        leds[led_index] = WAVE_COLORS[color_idx]
    
    leds.show()
    tilt_wave_step += 1
    return True

def update_guide_mode_leds():
    """Render guide mode LED feedback - show full board with selected preset colors (released state)"""
    global current_guide_slot, guide_preset_type, current_standard_preset_index
    if leds is None:
        return
    
    # Determine which preset to display
    if guide_preset_type == "standard" and current_standard_preset_index < len(standard_presets_list):
        preset_name = standard_presets_list[current_standard_preset_index]
        preset_data = standard_presets.get(preset_name, {})
        display_name = f"Standard: {preset_name}"
    elif guide_preset_type == "user" and current_guide_slot in slot_presets:
        preset_data = slot_presets[current_guide_slot]
        display_name = f"User Slot {current_guide_slot}"
    else:
        preset_data = {}
        display_name = "No preset"
    
    # Render all buttons with their released colors from the selected preset
    for button_name, element_id_prefix in BUTTON_TO_ELEMENT_ID.items():
        led_index = config.get(f"{button_name}_led")
        if led_index is None:
            continue
        
        # Look up the released color from the preset
        hex_color = None
        
        # For strum buttons, try "-released" or "-active"
        if "strum" in element_id_prefix:
            hex_color = preset_data.get(f"{element_id_prefix}-released")
            if hex_color is None:
                hex_color = preset_data.get(f"{element_id_prefix}-active")
        else:
            # For frets, try "-released" first, then "-pressed" as fallback
            hex_color = preset_data.get(f"{element_id_prefix}-released")
            if hex_color is None:
                hex_color = preset_data.get(f"{element_id_prefix}-pressed")
        
        if hex_color:
            # Convert hex to RGB and set LED
            try:
                color = hex_to_rgb(hex_color)
                leds[led_index] = color
            except Exception as e:
                print(f"[GUIDE] Error setting LED {button_name}: {e}")
                leds[led_index] = (0, 0, 0)
        else:
            # No color found - turn off LED
            leds[led_index] = (0, 0, 0)
    
    leds.show()
    print(f"[GUIDE] Displaying {display_name}")

def flash_white_leds(flash_count=2, flash_duration=0.1):
    """Flash all LEDs white N times for mode transitions"""
    global leds
    if leds is None:
        return
    
    original_colors = []
    for i in range(len(leds)):
        original_colors.append(tuple(leds[i]))
    
    for _ in range(flash_count):
        # Flash on (white)
        for i in range(len(leds)):
            leds[i] = (255, 255, 255)
        leds.show()
        time.sleep(flash_duration)
        
        # Flash off (black)
        for i in range(len(leds)):
            leds[i] = (0, 0, 0)
        leds.show()
        time.sleep(flash_duration)
    
    # Restore original colors
    for i in range(len(leds)):
        leds[i] = original_colors[i]
    leds.show()

def update_demo_mode_leds():
    """Update LEDs for demo mode - display current preset's released colors"""
    global demo_preset_index, leds
    if leds is None or demo_preset_index >= len(standard_presets_list):
        return
    
    preset_name = standard_presets_list[demo_preset_index]
    preset_data = standard_presets.get(preset_name, {})
    
    # Render all buttons with preset's released colors
    for button_name, element_id_prefix in BUTTON_TO_ELEMENT_ID.items():
        led_index = config.get(f"{button_name}_led")
        if led_index is None:
            continue
        
        # Get released color from preset
        hex_color = None
        if "strum" in element_id_prefix:
            hex_color = preset_data.get(f"{element_id_prefix}-released")
            if hex_color is None:
                hex_color = preset_data.get(f"{element_id_prefix}-active")
        else:
            hex_color = preset_data.get(f"{element_id_prefix}-released")
            if hex_color is None:
                hex_color = preset_data.get(f"{element_id_prefix}-pressed")
        
        if hex_color:
            try:
                color = hex_to_rgb(hex_color)
                leds[led_index] = color
            except Exception as e:
                print(f"[DEMO] Error setting LED {button_name}: {e}")
                leds[led_index] = (0, 0, 0)
        else:
            leds[led_index] = (0, 0, 0)
    
    leds.show()
    print(f"[DEMO] Displaying preset {demo_preset_index + 1}/{len(standard_presets_list)}: {preset_name}")

def update_leds():
    """Update normal LED colors based on button states and config"""
    if leds is None:
        return
    
    for name, pin in buttons.items():
        i = config.get(f"{name}_led")
        if i is None or leds is None: 
            continue
        pressed = current_state[name]
        key = f"{name} Pressed" if pressed else f"{name} Released"
        color = preset_colors.get(key)
        if color: 
            color = hex_to_rgb(color)
        else: 
            color = config["led_color"][i] if pressed else config["released_color"][i]
            # Convert hex string to RGB tuple if needed
            if isinstance(color, str):
                color = hex_to_rgb(color)
        
        # Safety check: ensure color is a tuple/list before assignment
        if not isinstance(color, (tuple, list)):
            print(f"Warning: Invalid LED color type for {name}: {type(color)}")
            color = (0, 0, 0)  # Default to black
            
        leds[i] = color
    leds.show()

if leds is not None:
    update_leds()


serial = usb_cdc.data
serial.timeout = 0.001
buffer = ""
mode = None
filename = ""
file_lines = []
last_whammy = None

try:
    with open("/user_presets.json", "r") as f:
        user_presets = json.load(f)
    preset_colors = user_presets.get("NewUserPreset1", {})
except Exception as e:
    print("Could not load user presets:", e)

# Load all 6 preset slots for guide mode display
slot_presets = {}
SLOT_NAMES = ["User 1", "User 2", "User 3", "User 4", "User 5", "User 6"]
for slot_num, slot_name in enumerate(SLOT_NAMES, 1):
    if slot_name in user_presets:
        slot_presets[slot_num] = user_presets[slot_name]
    else:
        print(f"[WARNING] Slot {slot_num} ({slot_name}) not found in user_presets.json")
        slot_presets[slot_num] = {}

# Load standard presets from presets.json for guide mode
standard_presets = {}
standard_presets_list = []  # List of preset names in order
try:
    with open("/presets.json", "r") as f:
        presets_data = json.load(f)
        standard_presets = presets_data.get("presets", {})
        standard_presets_list = list(standard_presets.keys())
    print(f"[GUIDE] Loaded {len(standard_presets)} standard presets: {standard_presets_list}")
except Exception as e:
    print(f"[WARNING] Could not load standard presets: {e}")
    standard_presets_list = []

# Mapping from button names to element ID prefixes for preset color lookup
BUTTON_TO_ELEMENT_ID = {
    "GREEN_FRET": "green-fret",
    "RED_FRET": "red-fret",
    "YELLOW_FRET": "yellow-fret",
    "BLUE_FRET": "blue-fret",
    "ORANGE_FRET": "orange-fret",
    "STRUM_UP": "strum-up",
    "STRUM_DOWN": "strum-down",
}

# Mapping from button names to config array indices for led_color and released_color
# Order in config arrays: [STRUM_UP, STRUM_DOWN, ORANGE_FRET, BLUE_FRET, YELLOW_FRET, RED_FRET, GREEN_FRET]
BUTTON_TO_LED_INDEX = {
    "STRUM_UP": 0,
    "STRUM_DOWN": 1,
    "ORANGE_FRET": 2,
    "BLUE_FRET": 3,
    "YELLOW_FRET": 4,
    "RED_FRET": 5,
    "GREEN_FRET": 6,
}

# Load preset state (current active slot)
try:
    with open("/preset_state.json", "r") as f:
        preset_state = json.load(f)
        current_guide_slot = preset_state.get("active_slot", 1)
        print(f"[BOOT] Loaded preset state: active_slot = {current_guide_slot}")
except Exception as e:
    print("Could not load preset_state.json:", e)
    current_guide_slot = 1

BUTTON_MAP = {
    "GREEN_FRET": 1,
    "RED_FRET": 2,
    "YELLOW_FRET": 3,
    "BLUE_FRET": 4,
    "ORANGE_FRET": 5,
    "STRUM_UP": 6,
    "STRUM_DOWN": 7,
    "SELECT": 8,
    "START": 9,
    "TILT": 10,
    "GUIDE": 11
}

def compute_hat():
    if hat_mode == "dpad":
        # Use only dpad buttons
        u, d, l, r = (current_state.get(k, False) for k in ("UP", "DOWN", "LEFT", "RIGHT"))
        return 1 if u and r else 3 if d and r else 5 if d and l else 7 if u and l else 0 if u else 2 if r else 4 if d else 6 if l else 0x0F
    else:
        # Use joystick for hat (full range, only ignore truly floating)
        if joystick_x.value in (0, 65535) or joystick_y.value in (0, 65535):
            u, d, l, r = (current_state.get(k, False) for k in ("UP", "DOWN", "LEFT", "RIGHT"))
            return 1 if u and r else 3 if d and r else 5 if d and l else 7 if u and l else 0 if u else 2 if r else 4 if d else 6 if l else 0x0F

        threshold = 12000
        center_x = 32400
        center_y = 33800
        x_val = joystick_x.value - center_x
        y_val = joystick_y.value - center_y

        if abs(x_val) > threshold or abs(y_val) > threshold:
            diag_thresh = threshold * 0.7
            if abs(x_val) > diag_thresh and abs(y_val) > diag_thresh:
                if x_val > 0 and y_val > 0:
                    return 1  # Up-Right
                if x_val < 0 and y_val > 0:
                    return 7  # Up-Left
                if x_val > 0 and y_val < 0:
                    return 3  # Down-Right
                if x_val < 0 and y_val < 0:
                    return 5  # Down-Left
            if abs(y_val) > abs(x_val):
                if y_val > threshold:
                    return 0  # Up
                if y_val < -threshold:
                    return 4  # Down
            else:
                if x_val > threshold:
                    return 2  # Right
                if x_val < -threshold:
                    return 6  # Left
            return 0x0F
        # Fallback to dpad
        u, d, l, r = (current_state.get(k, False) for k in ("UP", "DOWN", "LEFT", "RIGHT"))
        return 1 if u and r else 3 if d and r else 5 if d and l else 7 if u and l else 0 if u else 2 if r else 4 if d else 6 if l else 0x0F

def poll_inputs():
    global previous_tilt_state, previous_virtual_guide, guide_button_pressed, guide_button_press_time
    global guide_entry_detected, guide_triple_press_count, guide_last_press_time
    global guide_mode_active, guide_mode_entry_time, guide_mode_last_action_time, current_guide_slot
    global guide_preset_type, current_standard_preset_index
    changed = False
    
    for name, pin in buttons.items():
        pressed = not pin["obj"].value
        if pressed != current_state[name]:
            current_state[name] = pressed
            changed = True
            
            # Special handling for GUIDE button - detect entry before sending to gamepad
            if name == "GUIDE":
                guide_button_pressed = pressed
                current_time = time.monotonic()  # Use monotonic() for CircuitPython timing
                
                if pressed:
                    # GUIDE button pressed
                    if guide_button_press_time is None:
                        guide_button_press_time = current_time
                        print("[GUIDE] Button pressed - timing hold...")
                    
                    # Check for triple-press (3 quick taps)
                    if guide_last_press_time is not None:
                        time_since_last = current_time - guide_last_press_time
                        if time_since_last < GUIDE_TRIPLE_PRESS_TIMEOUT:
                            guide_triple_press_count += 1
                            print(f"[GUIDE] Tap {guide_triple_press_count}/3 detected")
                            if guide_triple_press_count >= 3 and not guide_entry_detected:
                                print("[GUIDE] Triple-press detected - Entry to Guide Mode!")
                                guide_entry_detected = True
                                guide_mode_active = True
                                guide_mode_entry_time = current_time
                                guide_mode_last_action_time = current_time
                                print(f"[GUIDE MODE] Entered! Current slot: {current_guide_slot}")
                                flash_white_leds(flash_count=2, flash_duration=0.1)
                                guide_triple_press_count = 0  # Reset counter
                        else:
                            # Timeout - reset counter
                            guide_triple_press_count = 1
                            print("[GUIDE] Tap timeout - counter reset")
                    else:
                        guide_triple_press_count = 1
                    
                    guide_last_press_time = current_time
                else:
                    # GUIDE button released - check hold time
                    if guide_button_press_time is not None:
                        hold_duration = current_time - guide_button_press_time
                        print(f"[GUIDE] Button released after {hold_duration:.3f}s")
                        if hold_duration >= GUIDE_HOLD_DURATION and not guide_entry_detected:
                            print(f"[GUIDE] 1-second hold detected ({hold_duration:.2f}s) - Entry to Guide Mode!")
                            guide_entry_detected = True
                            guide_mode_active = True
                            guide_mode_entry_time = current_time
                            guide_mode_last_action_time = current_time
                            print(f"[GUIDE MODE] Entered! Current slot: {current_guide_slot}")
                            flash_white_leds(flash_count=2, flash_duration=0.1)
                        guide_button_press_time = None
            
            # Guide Mode: LEFT/RIGHT slot stepping (USER presets)
            if guide_mode_active and pressed:  # Only on press, not release
                if name == "LEFT":
                    # Previous slot (wrap 1 → 6)
                    guide_preset_type = "user"
                    current_guide_slot = current_guide_slot - 1 if current_guide_slot > 1 else 6
                    guide_mode_last_action_time = time.monotonic()
                    print(f"[GUIDE] User slot stepped LEFT: {current_guide_slot}")
                    changed = True
                elif name == "RIGHT":
                    # Next slot (wrap 6 → 1)
                    guide_preset_type = "user"
                    current_guide_slot = current_guide_slot + 1 if current_guide_slot < 6 else 1
                    guide_mode_last_action_time = time.monotonic()
                    print(f"[GUIDE] User slot stepped RIGHT: {current_guide_slot}")
                    changed = True
                elif name == "UP":
                    # Previous standard preset (wrap around)
                    if len(standard_presets_list) > 0:
                        guide_preset_type = "standard"
                        current_standard_preset_index = current_standard_preset_index - 1 if current_standard_preset_index > 0 else len(standard_presets_list) - 1
                        guide_mode_last_action_time = time.monotonic()
                        preset_name = standard_presets_list[current_standard_preset_index]
                        print(f"[GUIDE] Standard preset stepped UP: {preset_name}")
                        changed = True
                elif name == "DOWN":
                    # Next standard preset (wrap around)
                    if len(standard_presets_list) > 0:
                        guide_preset_type = "standard"
                        current_standard_preset_index = current_standard_preset_index + 1 if current_standard_preset_index < len(standard_presets_list) - 1 else 0
                        guide_mode_last_action_time = time.monotonic()
                        preset_name = standard_presets_list[current_standard_preset_index]
                        print(f"[GUIDE] Standard preset stepped DOWN: {preset_name}")
                        changed = True
            
            # Guide Mode: START button to confirm and save preset
            if guide_mode_active and name == "START" and pressed:
                # Get the correct preset data based on type
                try:
                    if guide_preset_type == "standard" and current_standard_preset_index < len(standard_presets_list):
                        preset_name = standard_presets_list[current_standard_preset_index]
                        preset_data = standard_presets.get(preset_name, {})
                        print(f"[GUIDE MODE] Saving standard preset: {preset_name}")
                    else:
                        preset_data = slot_presets.get(current_guide_slot, {})
                        print(f"[GUIDE MODE] Saving user preset slot {current_guide_slot}")
                    
                    # Create new color arrays from preset
                    new_led_color = config.get("led_color", [])
                    new_released_color = config.get("released_color", [])
                    
                    # Copy colors from preset to config arrays
                    for button_name, led_index in BUTTON_TO_LED_INDEX.items():
                        element_id_prefix = BUTTON_TO_ELEMENT_ID.get(button_name)
                        if element_id_prefix is None:
                            continue
                        
                        # Get pressed color
                        if "strum" in element_id_prefix:
                            pressed_color = preset_data.get(f"{element_id_prefix}-active")
                            if pressed_color is None:
                                pressed_color = preset_data.get(f"{element_id_prefix}-released")
                        else:
                            pressed_color = preset_data.get(f"{element_id_prefix}-pressed")
                            if pressed_color is None:
                                pressed_color = preset_data.get(f"{element_id_prefix}-released")
                        
                        # Get released color
                        released_color = preset_data.get(f"{element_id_prefix}-released")
                        if released_color is None and "strum" in element_id_prefix:
                            released_color = preset_data.get(f"{element_id_prefix}-active")
                        
                        if pressed_color:
                            new_led_color[led_index] = pressed_color
                        if released_color:
                            new_released_color[led_index] = released_color
                    
                    # Update config in memory
                    config["led_color"] = new_led_color
                    config["released_color"] = new_released_color
                    raw_config["led_color"] = new_led_color
                    raw_config["released_color"] = new_released_color
                    
                    # Write updated config to file
                    with open("/config.json", "w") as f:
                        json.dump(raw_config, f)
                    
                    print(f"[GUIDE MODE] Saved preset colors to config.json")
                    
                    # Save preset info to preset_state.json
                    if guide_preset_type == "standard":
                        preset_state = {"preset_type": "standard", "preset_name": standard_presets_list[current_standard_preset_index]}
                    else:
                        preset_state = {"preset_type": "user", "active_slot": current_guide_slot}
                    with open("/preset_state.json", "w") as f:
                        json.dump(preset_state, f)
                    
                    print(f"[GUIDE MODE] Saved preset to preset_state.json")
                    
                    # CRITICAL: Reset tiltwave state and restore normal LEDs
                    guide_mode_active = False
                    guide_entry_detected = False  # Allow re-entry
                    guide_preset_type = "user"  # Reset to user presets for next entry
                    current_standard_preset_index = 0
                    tilt_wave_active = False
                    tilt_wave_step = 0
                    tilt_wave_led_counter = 0  # Reset throttling counter for clean tiltwave restart
                    
                    # Update LEDs to normal state based on current button presses
                    update_leds()
                    flash_white_leds(flash_count=2, flash_duration=0.1)
                    print("[GUIDE MODE] Exiting guide mode - colors now default")
                except Exception as e:
                    print(f"[GUIDE MODE] Error saving colors: {e}")
            
            if name in BUTTON_MAP:
                # Don't send LEFT/RIGHT/UP/DOWN/START to gamepad when in guide mode (used for navigation)
                if not (guide_mode_active and name in ("LEFT", "RIGHT", "UP", "DOWN", "START")):
                    (gp.press if pressed else gp.release)(BUTTON_MAP[name])
            
            # Check for tilt sensor activation
            if name == "TILT" and pressed and not previous_tilt_state:
                start_tilt_wave()
            
            # Update tilt state tracking
            if name == "TILT":
                previous_tilt_state = pressed

    # Check for virtual GUIDE button (UP + DOWN pressed simultaneously)
    # This handles devices that don't have a physical GUIDE button
    up_pressed = current_state.get("UP", False)
    down_pressed = current_state.get("DOWN", False)
    virtual_guide_pressed = up_pressed and down_pressed
    
    # Handle virtual GUIDE button state changes
    if virtual_guide_pressed != previous_virtual_guide:
        if virtual_guide_pressed:
            gp.press(BUTTON_MAP["GUIDE"])
        else:
            gp.release(BUTTON_MAP["GUIDE"])
        changed = True
        previous_virtual_guide = virtual_guide_pressed
    
    gp.set_hat(compute_hat())
    return changed

# Boot-time check for demo mode activation (GREEN + ORANGE frets held together at startup)
print("[BOOT] Checking for demo mode activation...")
demo_activation_time = time.monotonic()
demo_activation_duration = 0.5  # Check for 0.5 seconds
while time.monotonic() - demo_activation_time < demo_activation_duration:
    green_fret_pressed = not buttons["GREEN_FRET"]["obj"].value
    orange_fret_pressed = not buttons["ORANGE_FRET"]["obj"].value
    if green_fret_pressed and orange_fret_pressed:
        demo_mode_active = True
        demo_preset_index = 0
        demo_last_change_time = time.monotonic()
        demo_tiltwave_triggered = False
        print("[BOOT] Demo mode activated! GREEN+ORANGE combo detected.")
        flash_white_leds(flash_count=2, flash_duration=0.15)
        break
    time.sleep(0.01)

while True:
    # PRIORITY 1: Always poll gamepad inputs first (critical for gameplay)
    gamepad_changed = poll_inputs()
    
    # PRIORITY 2: Handle whammy (also critical for gameplay)
    if whammy:
        w_raw = whammy.value
        w = map_whammy(w_raw)
        if w != last_whammy:
            gp.set_whammy(w)
            last_whammy = w
    
    # PRIORITY 3: LED updates (lower priority, can be throttled)
    if demo_mode_active:
        # Demo mode cycles through presets with tiltwave animation (2.4 seconds per preset)
        current_time = time.monotonic()
        if demo_last_change_time is not None and current_time - demo_last_change_time >= DEMO_PRESET_INTERVAL:
            # Time to change to next preset
            demo_preset_index = (demo_preset_index + 1) % len(standard_presets_list)
            demo_last_change_time = current_time
            demo_tiltwave_triggered = False  # Reset flag for next transition
            update_demo_mode_leds()
        elif demo_last_change_time is None:
            # First time in demo mode
            demo_last_change_time = current_time
            update_demo_mode_leds()
        
        # Trigger tiltwave on preset transition if not already triggered
        if not demo_tiltwave_triggered and not tilt_wave_active:
            start_tilt_wave()
            demo_tiltwave_triggered = True
        
        # If tiltwave is active, it will render (has priority via main loop order)
        # Otherwise show the demo preset colors
        if not tilt_wave_active:
            update_demo_mode_leds()
    elif guide_mode_active:
        # Guide mode overrides all other LED rendering
        update_guide_mode_leds()
    elif tilt_wave_active:
        # Tilt wave overrides normal LEDs but doesn't block gamepad
        update_tilt_wave()
    elif gamepad_changed:
        # Only update normal LEDs if gamepad state changed
        update_leds()
    
    # PRIORITY 4: Serial communication (lowest priority)
    buffer, mode, filename, file_lines, config, raw_config, leds, buttons, whammy, current_state, user_presets, preset_colors = handle_serial(
        serial, config, raw_config, leds, buttons, whammy, current_state, user_presets, preset_colors,
        buffer, mode, filename, file_lines, gp, update_leds, poll_inputs, joystick_x, joystick_y, 8, start_tilt_wave
    )

    # Advance demo routine if active
    if demo_state_available:
        import demo_state
        if demo_state.demo_gen is not None:
            try:
                next(demo_state.demo_gen)
            except StopIteration:
                demo_state.demo_gen = None
    
    # Minimal sleep to prevent CPU spinning (1ms = 1000Hz max loop rate)
    time.sleep(0.001)
