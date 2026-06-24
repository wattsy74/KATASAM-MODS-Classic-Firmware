# FEAT-006 Firmware Change Plan

Date: 2026-06-23
Target: Classic-Firmware (CircuitPython)

## Objective

Add on-device switchable presets with this behavior:
- Long-press Guide enters preset switching mode.
- D-pad Left/Right cycles preset slot selection.
- Start confirms selected slot as default, applies it, and exits switching mode.
- Preset default persists across reboot.

## Current Firmware Construction

## Boot and update pipeline
- boot.py configures USB HID/CDC identity and runs update processing from /updates at boot.
- boot.py merges config and preset JSON files safely, with backups and atomic writes.
- boot.py can recover from failed update loops using updating.flag and update_retry_count.txt.

## Runtime loop and input model
- code.py initializes config, hardware, gamepad, and serial state.
- Main loop order:
1. poll_inputs() (buttons -> HID)
2. whammy update
3. LED updates (normal or tilt wave)
4. handle_serial(...) command processing
- Gamepad reports are emitted by CustomGamepad in gamepad.py.

## Serial command architecture
- serial_handler.py contains a line-based command parser and state machine for:
- READFILE/WRITEFILE/IMPORTUSER
- READVERSION/READUID/READDEVICENAME
- PREVIEWLED, READPIN, REBOOT, REBOOTBOOTSEL, MKDIR, etc.
- user_presets.json writes are validated and atomic.

## Preset data today
- user_presets.json currently contains slot-style keys User 1..User 5 plus _metadata.
- code.py currently initializes active preset with user_presets.get("NewUserPreset1", {}).
- This means startup currently relies on a legacy key that is not aligned with current slot naming.

## What Must Change

## 1) Add persistent preset state file

Add new file: /preset_state.json

Proposed schema:
{
  "schema_version": 1,
  "active_slot": 1,
  "default_slot": 1,
  "last_updated": "<iso8601 optional>"
}

Rules:
- If file missing/corrupt, initialize defaults active_slot=1 and default_slot=1.
- Keep slot index constrained to 1..6.

## 2) Standardize slot naming and runtime load path

In code.py:
- Replace startup fallback NewUserPreset1 with slot-derived key mapping:
- slot 1 -> "User 1"
- slot 2 -> "User 2"
- ...
- slot 6 -> "User 6"
- Load preset_state.json at startup and apply default_slot to preset_colors.
- If selected slot has no data, fallback to User 1 or empty-safe map.

Why required:
- Align runtime behavior with app slot naming and FEAT-006 UX.

## 3) Implement preset switching mode in input loop

In code.py:
- Add mode state and timing fields:
- preset_switch_mode (bool)
- guide_press_start (monotonic timestamp)
- selected_slot (int 1..6)
- debounce fields for left/right/start while mode active

Behavior:
- Detect Guide long-press >= 900ms (configurable constant).
- Enter preset_switch_mode:
- gate gameplay HID updates for navigation controls
- initialize selected_slot from active/default slot
- show visual entry feedback
- While in preset_switch_mode:
- Left decrements slot (wrap 1->6)
- Right increments slot (wrap 6->1)
- each move previews selected slot colors on LEDs
- Start confirms:
- active_slot = selected_slot
- default_slot = selected_slot
- save preset_state.json atomically
- apply selected slot colors immediately
- exit mode with confirmation feedback

## 4) Gate HID output while switching mode is active

In code.py/poll_inputs():
- While preset_switch_mode is true, suppress normal button-to-gamepad mapping for controls used by switching flow.
- Keep non-conflicting controls optional (recommended: suppress all gameplay buttons for deterministic behavior).

Why required:
- Prevent accidental in-game actions when user is selecting presets.

## 5) Add helper functions for slot apply/persist

In code.py (or dedicated new module if preferred):
- load_user_presets_safe()
- load_preset_state_safe()
- save_preset_state_atomic(state)
- get_slot_key(slot_index)
- apply_slot_to_preset_colors(slot_index)
- preview_slot_leds(slot_index)

Implementation note:
- Reuse existing JSON safety and atomic-write pattern already used in serial_handler.py/boot.py.

## 6) Expand default preset slots from 5 to 6

In user_presets.json:
- Add User 6 default object with same color fields as other slots.
- Keep _metadata and existing slot keys intact.

In code.py/serial_handler.py:
- Ensure any key validation and slot fallback logic accepts User 6.

## 7) Add serial commands for app capability/state visibility

In serial_handler.py, add commands:
- READPRESETSTATE
- WRITEPRESETSTATE:{json}
- LISTPRESETSLOTS

Response proposals:
- READPRESETSTATE -> PRESETSTATE:{json}\nEND
- WRITEPRESETSTATE -> PRESETSTATE:OK or ERROR:...
- LISTPRESETSLOTS -> PRESETSLOTS:["User 1",...,"User 6"]\nEND

Compatibility behavior:
- If command unknown on older firmware, existing ERROR: Unknown command remains.
- New app should probe capability via READPRESETSTATE and gracefully fallback.

## 8) ACK behavior update for new commands

In serial_handler.py smart ACK list:
- Include READPRESETSTATE, WRITEPRESETSTATE, LISTPRESETSLOTS so host behavior remains consistent with current protocol style.

## 9) Update firmware metadata/version surfaces

Update:
- __version__ in modified modules.
- FIRMWARE_VERSIONS map in code.py.
- version_manifest.json checksums/sizes/release notes.
- README summary/version text if you use it as release artifact context.

## 10) Update boot merge logic to preserve new state file

In boot.py:
- Ensure update processing keeps/preserves preset_state.json user values on firmware updates.
- Recommended behavior:
- For preset_state.json, preserve existing default_slot/active_slot if valid.
- If schema changes later, perform migration logic.

## Risks and Edge Cases

- Legacy key mismatch risk: NewUserPreset1 vs User N is already a latent inconsistency.
- Input ambiguity: devices without physical Guide may use virtual Guide (UP+DOWN); long-press handling must not break this path.
- LED preview conflicts: switching-mode previews must coexist with tilt wave and serial LED indicator states.
- Partial slot data: missing keys in a slot should not crash LED update paths.
- Runtime write safety: avoid blocking main loop too long when writing preset_state.json.

## Suggested Implementation Order

1. Fix slot key loading in code.py (remove NewUserPreset1 dependency).
2. Add preset_state.json load/save helpers.
3. Add switching-mode state machine in poll_inputs().
4. Add LED preview/confirm feedback behavior.
5. Add serial commands in serial_handler.py.
6. Add User 6 defaults and version metadata updates.
7. Validate with app integration and reboot persistence tests.

## Validation Checklist

- Boot with missing preset_state.json creates defaults and runs normally.
- Guide long-press enters mode reliably.
- Left/Right wraps through 1..6 and previews each slot.
- Start commits default slot and exits mode.
- Reboot restores last committed default slot.
- Legacy serial commands continue to function.
- App can still IMPORTUSER/READFILE user_presets.json without regressions.
- New serial state commands return deterministic responses with END markers where applicable.
