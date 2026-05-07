try:
    import os
    import ctypes
    import keyboard
    import pyperclip
    import time
    import threading
    import tkinter as tk
    from datetime import datetime
    from faker import Faker
    from plyer import notification
    import pystray
    from PIL import Image, ImageDraw
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
ARM_KEY = "ctrl+shift+space"
ARM_TIMEOUT = 3.0  # seconds before auto-disarm

_armed = False
_arm_timer = None
_armed_hotkeys = []


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
    ("Visa",        "4263982640269299", "02/2026", "837"),
    ("Mastercard",  "5425233430109903", "02/2026", "234"),
    ("Amex",        "374251018720955",  "02/2026", "1234"),
    ("Discover",    "6011000000000004", "02/2026", "123"),
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
    (ARM_KEY.title().replace("+", " + "), "Arm / disarm  (dot turns green)"),
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
    last_label, last_value = label, value
    pyperclip.copy(value)
    if notifications_enabled:
        notification.notify(
            title="qafill",
            message=f"{label}: {value}",
            app_name="qafill",
            timeout=3,
        )
    time.sleep(0.05)
    keyboard.send("ctrl+v")


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
    global _armed, _arm_timer, _armed_hotkeys
    _armed = False
    icon.icon = make_icon_image(notifications_enabled, armed=False)
    if _arm_timer:
        _arm_timer.cancel()
        _arm_timer = None
    for hk in _armed_hotkeys:
        try:
            keyboard.remove_hotkey(hk)
        except Exception:
            pass
    _armed_hotkeys = []


def arm_mode():
    global _armed, _arm_timer, _armed_hotkeys
    if _armed:
        disarm_mode()
        return
    _armed = True
    icon.icon = make_icon_image(notifications_enabled, armed=True)

    # Build chord map now so card/custom values are current
    chord_map = {
        "n": lambda: copy("Name",       fake.name()),
        "f": lambda: copy("First Name", fake.first_name()),
        "l": lambda: copy("Last Name",  fake.last_name()),
        "e": lambda: copy("Email",      fake.email()),
        "p": lambda: copy("Phone",      fake.phone_number()),
        "a": lambda: copy("Address",    fake.address().replace("\n", ", ")),
        "z": lambda: copy("ZIP",        fake.zipcode()),
        "c": lambda: copy("Card #",     fake.credit_card_number()),
        "r": repeat_last,
        "t": toggle_notifications,
    }
    for i, (card_type, number, exp, cvv) in enumerate(TEST_CARDS, start=1):
        chord_map[str(i)] = lambda t=card_type, n=number: copy(t, n)
    for i, (label, value) in enumerate(CUSTOM_STRINGS, start=5):
        chord_map[str(i)] = lambda l=label, v=value: copy(l, v)

    # Register chord keys only while armed
    for key, action in chord_map.items():
        hk = keyboard.add_hotkey(
            key,
            lambda a=action: threading.Thread(target=lambda: (disarm_mode(), a()), daemon=True).start(),
            suppress=True,
        )
        _armed_hotkeys.append(hk)

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
        pystray.MenuItem("Exit", lambda icon, item: icon.stop()),
    )


keyboard.add_hotkey(ARM_KEY, arm_mode, suppress=True)

log("startup ok")

# Run tray icon on main thread - keeps process alive
icon = pystray.Icon("qafill", make_icon_image(notifications_enabled), "qafill", build_menu())
icon.run()
