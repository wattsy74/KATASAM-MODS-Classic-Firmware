# Changelog

All notable changes to the Classic-Firmware project will be documented in this file.

## [5.0.2] - 2026-06-25

### Added

#### Demo Mode Feature
- **Boot Activation**: Hold GREEN_FRET + ORANGE_FRET together for 0.5+ seconds at power-on to enter demo mode
- **Automatic Preset Cycling**: Demo mode cycles through all 13 standard presets every 5 seconds
- **Continuous Loop**: Demo mode runs until device is powered off
- **Display-Only Scenario**: Perfect for retail displays or demo setups without computer/gamepad connection

#### LED Transition Feedback
- **White LED Flashes (2x)**: All 7 NeoPixel LEDs flash white on mode transitions for visual feedback
  - Guide mode entry (triple-press GUIDE or 1-second hold)
  - Guide mode exit (START button)
  - Demo mode activation (boot sequence)
- **Flash Duration**: 100ms white, 100ms off, repeats 2x per transition
- **State Preservation**: LED colors automatically restored after flashes

#### Color Format Support
- **Enhanced hex_to_rgb()**: Now supports both color formats seamlessly
  - Hex format: `#XXXXXX` or `XXXXXX`
  - RGB format: `rgb(r, g, b)` with automatic number extraction and 0-255 clamping
- **Preset Compatibility**: Works with presets using either format (e.g., BumbleGum Yellow uses rgb())

#### Deployment Tools
- **deploy-to-device.sh**: Smart deployment script with separate prompts
  - Prompt 1: Deploy code files (`.py`, `lib/`, data `.json`)
  - Prompt 2: Deploy user config files (`config.json`, `presets.json`, `user_presets.json`)
  - Allows code updates without overwriting user presets
- **create_uf2_from_device.sh**: Firmware backup utility
  - Multiple UF2/binary output formats (-1 MB, -s 750KB, -x 500KB, -f 2MB full)
  - Auto-backup existing files with timestamp
  - Colored terminal output

#### Version Tracking
- **version_manifest.json**: New file for tracking deployment information

### Fixed

- **Tiltwave Regression**: Fixed animation displaying single blue frame after guide mode preset selection
  - Root cause: Missing cleanup on guide mode exit
  - Solution: Reset all tiltwave state variables (tilt_wave_active, tilt_wave_step, tilt_wave_led_counter) when exiting guide mode
- **Tiltwave Stale Frame**: Fixed LEDs stuck on final blue frame after animation completion
  - Root cause: update_leds() not called when animation finished
  - Solution: Added update_leds() call at end of update_tilt_wave()

### Technical Details

#### New State Variables (code.py lines ~92-106)
```python
demo_mode_active = False
demo_preset_index = 0
demo_last_change_time = time.monotonic()
DEMO_PRESET_INTERVAL = 5.0  # seconds between preset changes
```

#### Boot Check Logic (before main loop)
- GREEN_FRET and ORANGE_FRET must both be pressed continuously for 0.5 seconds
- Only checks at startup, not during gameplay (prevents accidental activation)
- Triggers flash_white_leds(2, 0.15) on activation

#### Main Loop LED Priority
```
if demo_mode_active:
    update_demo_mode_leds()
elif guide_mode_active:
    update_guide_mode_leds()
elif tilt_wave_active:
    update_tilt_wave()
elif gamepad_changed:
    update_leds()
```

#### Global Declarations
All functions that modify state variables properly declare them:
- `poll_inputs()`: guide_preset_type, current_standard_preset_index, guide_mode_active, etc.
- `update_tilt_wave()`: tilt_wave_active, tilt_wave_step, tilt_wave_led_counter

### Testing Recommendations

1. **Demo Mode Boot Sequence**
   - Power on with GREEN+ORANGE held together
   - Verify 2x white LED flash
   - Verify presets cycle every 5 seconds
   - Confirm mode persists until power-off

2. **Guide Mode Transitions**
   - Enter: Triple-press GUIDE or hold 1 second → 2x white flash
   - Cycle presets: UP/DOWN for standard, LEFT/RIGHT for user slots
   - Exit: Press START → 2x white flash
   - Verify LEDs return to normal state

3. **Color Formats**
   - Test all 13 standard presets display correctly
   - Verify rgb() format presets (e.g., BumbleGum Yellow) show proper colors
   - Verify hex format presets work as expected

4. **Normal Gameplay**
   - Verify demo mode doesn't trigger accidentally during normal play
   - Confirm UP/DOWN/LEFT/RIGHT blocked from gamepad when in guide mode
   - Verify gamepad controls unaffected in normal mode

### Known Limitations

- Demo mode only checks for GREEN+ORANGE combo at boot time for stability
- White flashes store/restore LED colors, so custom animations may be interrupted briefly

### Migration Notes

- No breaking changes from v5.0.1
- user_presets.json and config.json remain compatible
- Existing presets work with new color format support

---

## [5.0.1] - Previous

[Previous release notes]
