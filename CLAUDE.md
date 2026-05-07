# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

qafill is a Windows-only system tray tool that generates fake test data and auto-pastes it via global hotkeys. It runs as a background process (`pythonw testdata.py`) with a colored dot in the system tray. The user presses Ctrl+Shift+Space to arm, then a single key (N for name, E for email, etc.) to generate and paste data into the focused field.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python -m unittest test_testdata -v

# Run the app (foreground, for debugging)
python testdata.py

# Run the app (background, normal usage)
start.bat
```

There is no linter or build step. The project is a single Python script.

## Architecture

Everything lives in `testdata.py`. There is no package structure.

### Key dispatch flow

All keyboard logic runs through pynput's `win32_event_filter`, not `on_press`. This is critical to understand: **pynput's `suppress_event()` prevents `on_press` from firing for that event**. So any logic that needs to run for suppressed keys (ARM combo, chord keys while armed) must execute directly in the filter.

```
Physical key press
  -> _win32_event_filter (runs first, receives Windows VK codes)
       - Modifier keys: pass through (never suppress)
       - Ctrl+Shift+Space: call arm_mode(), suppress
       - Armed + chord key: dispatch action in thread, suppress
       - Armed + non-chord key: disarm, suppress
       - Not armed: pass through
  -> _on_press (only receives non-suppressed events)
       - Tracks modifier key state in _current_modifiers set
  -> _on_release
       - Removes keys from _current_modifiers
```

### Two layers of key representation

The filter receives Windows VK codes (integers like `0x4E` for N). The chord map uses lowercase character strings (`"n"`). `_vk_to_char()` bridges the two. `_MODIFIER_KEYS` uses pynput Key objects for `_on_press`; `_VK_MODIFIERS` uses VK code integers for the filter. Both sets must stay in sync conceptually.

### State machine

The app has two states: **idle** (blue dot) and **armed** (green dot). `arm_mode()` builds a fresh `_chord_map` dict and starts a 3-second auto-disarm timer. `disarm_mode()` clears the map and cancels the timer. The `_armed` boolean gates all behavior. `disarm_mode` is idempotent (early return if already disarmed).

### Side effects and testability

Module-level code runs on import: `ctypes.windll` call, `Faker()` instance, `Controller()` instance, `_load_dotenv()`, and `local.py` import. The Listener and tray icon are behind `if __name__ == "__main__"`. Tests mock `_controller` and `_listener` at the instance level, and set `icon` to a MagicMock.

### Custom strings

`local.py` (gitignored) exports a `CUSTOM_STRINGS` list of `(label, value)` tuples. Values are resolved once at startup via `resolve()` - callables are invoked, literals pass through. Mapped to keys 5-8 while armed.

## Conventions

- Add new data types by adding entries to the `_chord_map` dict in `arm_mode()`, and to `HOTKEY_REFERENCE` for the reference window.
- Test card expiry dates should use a date far enough in the future to avoid periodic breakage.
- The `copy()` function handles clipboard + paste + notification for all data types. All chord actions should go through it (except `repeat_last` and `toggle_notifications`).
- When adding new VK codes to `_VK_MODIFIERS`, also add the corresponding pynput Key to `_MODIFIER_KEYS`.
