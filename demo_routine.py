# demo_routine.py
__version__ = "3.9.26"

def get_version():
    return __version__

# Contains the LED demo routine for the BGG device
import time
from utils import hex_to_rgb

def run_demo_generator(leds, config, preset_colors, start_tilt_wave):
    """
    Generator-based non-blocking demo routine for BGG device.
    Yields control back to main loop frequently for smooth timing and tiltwave animation.
    """
    released_colors = config["released_color"]
    pressed_colors = config["led_color"]
    led_count = len(leds)
    cycles = 3
    # Timings in seconds (adjust as needed)
    t_show_released = 1.0
    t_seq_pressed = 0.5
    t_all_pressed = 1.0
    t_all_released = 0.5
    t_tiltwave = 2.5

    for cycle in range(cycles):
        # 1. Show released colours
        for i in range(led_count):
            leds[i] = released_colors[i]
        leds.show()
        t0 = time.monotonic()
        while time.monotonic() - t0 < t_show_released:
            yield

        # 2. Sequential pressed colours (6→0)
        for idx in range(6, -1, -1):
            for i in range(led_count):
                leds[i] = released_colors[i]
            leds[idx] = pressed_colors[idx]
            leds.show()
            t1 = time.monotonic()
            while time.monotonic() - t1 < t_seq_pressed:
                yield
        # After last, revert all to released
        for i in range(led_count):
            leds[i] = released_colors[i]
        leds.show()
        yield  # Let main loop update

        # 3. All pressed colours
        for i in range(led_count):
            leds[i] = pressed_colors[i]
        leds.show()
        t2 = time.monotonic()
        while time.monotonic() - t2 < t_all_pressed:
            yield

        # 4. All released colours
        for i in range(led_count):
            leds[i] = released_colors[i]
        leds.show()
        t3 = time.monotonic()
        while time.monotonic() - t3 < t_all_released:
            yield

        # 5. Activate tiltwave
        start_tilt_wave()
        t4 = time.monotonic()
        while time.monotonic() - t4 < t_tiltwave:
            yield

    # End of demo: restore released colours
    for i in range(led_count):
        leds[i] = released_colors[i]
    leds.show()
