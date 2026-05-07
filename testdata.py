try:
    import os
    import ctypes
    import pyperclip
    import time
    import threading
    import tkinter as tk
    from datetime import datetime
    from faker import Faker
    from plyer import notification
    import pystray
    from PIL import Image, ImageDraw
    from pynput.keyboard import Key, KeyCode, Listener, Controller
except ImportError as e:
    import tkinter.messagebox as mb
    mb.showerror(
        "qafill - Missing dependency",
        f"{e}\n\nRun setup.bat to install all dependencies."
    )
    raise SystemExit(1)

# Register app identity so Windows shows "qafill" in system tray icons list
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("qafill")

fake = Faker()
notifications_enabled = False
last_label = None
last_value = None

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qafill.log")
ARM_TIMEOUT = 3.0  # seconds before auto-disarm

_armed = False
_arm_timer = None
_arm_last_time = 0.0
_chord_map = {}

_controller = Controller()
_listener = None
_current_modifiers = set()

# pynput Key objects that are modifiers (never trigger chord actions)
_MODIFIER_KEYS = {
    Key.ctrl, Key.ctrl_l, Key.ctrl_r,
    Key.shift, Key.shift_l, Key.shift_r,
    Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr,
    Key.cmd, Key.cmd_l, Key.cmd_r,
    Key.caps_lock, Key.num_lock, Key.scroll_lock,
}

# VK codes for modifier keys (used by win32_event_filter)
_VK_MODIFIERS = {
    0x10, 0x11, 0x12,        # VK_SHIFT, VK_CONTROL, VK_MENU
    0xA0, 0xA1,              # VK_LSHIFT, VK_RSHIFT
    0xA2, 0xA3,              # VK_LCONTROL, VK_RCONTROL
    0xA4, 0xA5,              # VK_LMENU, VK_RMENU
    0x5B, 0x5C,              # VK_LWIN, VK_RWIN
    0x14, 0x90, 0x91,        # VK_CAPITAL, VK_NUMLOCK, VK_SCROLL
}


def _ctrl_held():
    return bool(_current_modifiers & {Key.ctrl, Key.ctrl_l, Key.ctrl_r})


def _shift_held():
    return bool(_current_modifiers & {Key.shift, Key.shift_l, Key.shift_r})


def _key_char(key):
    """Get the lowercase character for a key, or None for non-character keys."""
    if isinstance(key, KeyCode) and key.char:
        return key.char.lower()
    return None


def _is_arm_combo(key):
    """Return True if Ctrl+Shift+Space was just completed."""
    is_space = key == Key.space or (isinstance(key, KeyCode) and key.char == ' ')
    return is_space and _ctrl_held() and _shift_held()


def _on_press(key):
    """Handle all key-down events from the single global Listener."""
    if key in _MODIFIER_KEYS:
        _current_modifiers.add(key)

    if _is_arm_combo(key):
        arm_mode()
        return

    if not _armed:
        return

    name = _key_char(key)
    if name and name in _chord_map:
        action = _chord_map[name]
        threading.Thread(
            target=lambda a=action: (disarm_mode(), a()),
            daemon=True,
        ).start()
    elif key not in _MODIFIER_KEYS:
        disarm_mode()


def _on_release(key):
    _current_modifiers.discard(key)


def _win32_event_filter(msg, data):
    """Suppress key events selectively so they don't reach the focused app.

    Called before on_press/on_release for each event. Calling
    _listener.suppress_event() prevents the event from reaching other
    applications, but on_press/on_release still fire.
    """
    WM_KEYDOWN = 0x0100
    WM_SYSKEYDOWN = 0x0104

    if msg not in (WM_KEYDOWN, WM_SYSKEYDOWN):
        return

    vk = data.vkCode

    # Never suppress modifier keys - OS needs them for state tracking
    if vk in _VK_MODIFIERS:
        return

    # Suppress all non-modifier key-downs while armed
    if _armed:
        _listener.suppress_event()
        return

    # Suppress space when Ctrl+Shift held (ARM combo) so it doesn't
    # type a space or trigger other shortcuts in the focused app
    if vk == 0x20 and _ctrl_held() and _shift_held():
        _listener.suppress_event()


def log(message):
    with open(LOG_PATH, "a") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


def resolve(value):
    """Call the value if callable, otherwise use it as a literal string."""
    try:
        return value() if callable(value) else value
    except Exception as e:
        log(f"resolve error: {e}")
        return f"[error: {e}]"


# Payment processor test cards - mapped to chord keys 1-4
# Add or swap out cards for your processor - format: (label, number, expiry, cvv)
TEST_CARDS = [
    ("Visa",        "4263982640269299", "12/2028", "837"),
    ("Mastercard",  "5425233430109903", "12/2028", "234"),
    ("Amex",        "374251018720955",  "12/2028", "1234"),
    ("Discover",    "6011000000000004", "12/2028", "123"),
]

# Load .env into os.environ before importing local.py so lambdas can use os.environ.get()
def _load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

_load_dotenv()

# Local custom strings - chord keys 5-8
# Create local.py (gitignored) using local.example.py as a template
try:
    from local import CUSTOM_STRINGS
    CUSTOM_STRINGS = [(label, resolve(value)) for label, value in CUSTOM_STRINGS[:4]]
except ImportError:
    CUSTOM_STRINGS = []

HOTKEY_REFERENCE = [
    ("Ctrl + Shift + Space", "Arm / disarm  (dot turns green)"),
    ("", ""),
    ("N", "Full Name"),
    ("F", "First Name"),
    ("L", "Last Name"),
    ("E", "Email"),
    ("P", "Phone"),
    ("A", "Address"),
    ("Z", "ZIP Code"),
    ("C", "Random Card #"),
] + [
    (str(i), f"{card[0]} test card")
    for i, card in enumerate(TEST_CARDS, start=1)
] + [
    (str(i), label)
    for i, (label, _) in enumerate(CUSTOM_STRINGS, start=5)
] + [
    ("R", "Repeat Last"),
    ("T", "Toggle Notifications"),
]


def make_icon_image(active=False, armed=False):
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if armed:
        color = (30, 180, 30)       # green  = armed
    elif active:
        color = (220, 120, 30)      # orange = notifications on
    else:
        color = (30, 120, 220)      # blue   = idle
    draw.ellipse([1, 1, 30, 30], fill=color)
    return img


def copy(label, value):
    global last_label, last_value
    log(f"copy: {label} ({len(value)} chars)")
    last_label, last_value = label, value
    pyperclip.copy(value)
    if notifications_enabled:
        notification.notify(
            title="qafill",
            message=f"{label}: {value}",
            app_name="qafill",
            timeout=3,
        )
    # Release modifiers in case any are stuck, then send Ctrl+V to paste
    for mod in (Key.ctrl_l, Key.ctrl_r, Key.shift_l, Key.shift_r):
        _controller.release(mod)
    time.sleep(0.05)
    _controller.press(Key.ctrl_l)
    _controller.press('v')
    _controller.release('v')
    _controller.release(Key.ctrl_l)


def repeat_last():
    if last_value is not None:
        copy(last_label, last_value)


def toggle_notifications():
    global notifications_enabled
    notifications_enabled = not notifications_enabled
    icon.icon = make_icon_image(notifications_enabled, _armed)
    notification.notify(
        title="qafill",
        message=f"Notifications {'ON' if notifications_enabled else 'OFF'}",
        app_name="qafill",
        timeout=2,
    )


def disarm_mode():
    global _armed, _arm_timer, _arm_last_time, _chord_map
    if not _armed:
        return
    log("disarm_mode called")
    _armed = False
    _arm_last_time = 0.0
    _chord_map = {}
    icon.icon = make_icon_image(notifications_enabled, armed=False)
    if _arm_timer:
        _arm_timer.cancel()
        _arm_timer = None


def arm_mode():
    global _armed, _arm_timer, _arm_last_time, _chord_map
    log(f"arm_mode called, _armed={_armed}")
    if _armed:
        disarm_mode()
        return
    now = time.time()
    if now - _arm_last_time < 0.5:
        log(f"arm_mode debounced ({now - _arm_last_time:.3f}s since last arm)")
        return
    _arm_last_time = now
    _armed = True
    icon.icon = make_icon_image(notifications_enabled, armed=True)

    _chord_map.update({
        "n": lambda: copy("Name",       fake.name()),
        "f": lambda: copy("First Name", fake.first_name()),
        "l": lambda: copy("Last Name",  fake.last_name()),
        "e": lambda: copy("Email",      fake.email()),
        "p": lambda: copy("Phone",      fake.numerify('###-###-####')),
        "a": lambda: copy("Address",    fake.address().replace("\n", ", ")),
        "z": lambda: copy("ZIP",        fake.zipcode()),
        "c": lambda: copy("Card #",     fake.credit_card_number()),
        "r": repeat_last,
        "t": toggle_notifications,
    })
    for i, (card_type, number, exp, cvv) in enumerate(TEST_CARDS, start=1):
        _chord_map[str(i)] = lambda t=card_type, n=number: copy(t, n)
    for i, (label, value) in enumerate(CUSTOM_STRINGS, start=5):
        _chord_map[str(i)] = lambda l=label, v=value: copy(l, v)

    # Auto-disarm after timeout
    _arm_timer = threading.Timer(ARM_TIMEOUT, disarm_mode)
    _arm_timer.daemon = True
    _arm_timer.start()


def show_hotkeys_window():
    win = tk.Tk()
    win.title("qafill - Hotkeys")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    frame = tk.Frame(win, padx=20, pady=15)
    frame.pack()

    tk.Label(frame, text="Hotkeys", font=("Segoe UI", 12, "bold")).grid(
        row=0, columnspan=2, pady=(0, 8)
    )
    row = 1
    for hotkey, desc in HOTKEY_REFERENCE:
        if hotkey == "":
            row += 1
            continue
        tk.Label(frame, text=hotkey, font=("Consolas", 10), anchor="w", width=22).grid(
            row=row, column=0, sticky="w", pady=1
        )
        tk.Label(frame, text=desc, font=("Segoe UI", 10), anchor="w").grid(
            row=row, column=1, sticky="w", padx=(8, 0)
        )
        row += 1

    tk.Button(frame, text="Close", command=win.destroy, width=10).grid(
        row=row + 1, columnspan=2, pady=(12, 0)
    )
    win.mainloop()


def _on_exit(tray_icon, item):
    if _listener:
        _listener.stop()
    tray_icon.stop()


def build_menu():
    return pystray.Menu(
        pystray.MenuItem(
            "Notifications",
            lambda icon, item: toggle_notifications(),
            checked=lambda item: notifications_enabled,
        ),
        pystray.MenuItem(
            "Show Hotkeys",
            lambda icon, item: threading.Thread(target=show_hotkeys_window, daemon=True).start(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", _on_exit),
    )


icon = None

def main():
    global icon, _listener
    _listener = Listener(
        on_press=_on_press,
        on_release=_on_release,
        win32_event_filter=_win32_event_filter,
    )
    _listener.start()
    log("startup ok")

    # Run tray icon on main thread - keeps process alive
    icon = pystray.Icon("qafill", make_icon_image(notifications_enabled), "qafill", build_menu())
    icon.run()


if __name__ == "__main__":
    main()
