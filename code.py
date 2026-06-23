FIRMWARE_VERSIONS = {
    "code.py": "3.9.26",
    "hardware.py": "3.9.26",
    "utils.py": "3.9.26",
    "gamepad.py": "3.9.26",
    "serial_handler.py": "3.9.26",
    "pin_detect.py": "3.9.26",
    "boot.py": "3.9.26",
    "demo_routine.py": "3.9.26",
    "demo_state.py": "3.9.26"
}

# BGG Firmware v3.9.26 - Smart Acknowledgment System
# - Enhanced device detection and communication
# - Smart ACK messages for Windows app compatibility
# - Conditional debug output prevents firmware corruption
# - Maintains v3.9.26 stability with communication improvements

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
        
        # Safety check: ensure color is a tuple/list before assignment
        if isinstance(color, str):
            print(f"Warning: LED color for {name} is still a string: {color}")
            color = hex_to_rgb(color)
        elif not isinstance(color, (tuple, list)):
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
    global previous_tilt_state, previous_virtual_guide
    changed = False
    
    for name, pin in buttons.items():
        pressed = not pin["obj"].value
        if pressed != current_state[name]:
            current_state[name] = pressed
            changed = True
            if name in BUTTON_MAP:
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
    if tilt_wave_active:
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