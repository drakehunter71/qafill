try:
    import keyboard
    import pyperclip
    import time
    import threading
    import tkinter as tk
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

fake = Faker()
notifications_enabled = False
last_label = None
last_value = None

# Payment processor test cards
# Ctrl+Alt+1 through Ctrl+Alt+4
# Add or swap out cards for your processor - format: (label, number, expiry, cvv)
TEST_CARDS = [
    ("Visa",        "4263982640269299", "02/2026", "837"),
    ("Mastercard",  "5425233430109903", "02/2026", "234"),
    ("Amex",        "374251018720955",  "02/2026", "1234"),
    ("Discover",    "6011000000000004", "02/2026", "123"),
]

HOTKEYS = {
    "ctrl+alt+n": ("Name",    lambda: fake.name()),
    "ctrl+alt+e": ("Email",   lambda: fake.email()),
    "ctrl+alt+p": ("Phone",   lambda: fake.phone_number()),
    "ctrl+alt+a": ("Address", lambda: fake.address().replace("\n", ", ")),
    "ctrl+alt+z": ("ZIP",     lambda: fake.zipcode()),
    "ctrl+alt+c": ("Card #",  lambda: fake.credit_card_number()),
}

# Local custom strings - Ctrl+Alt+5 through Ctrl+Alt+8
# Create local.py (gitignored) using local.example.py as a template
try:
    from local import CUSTOM_STRINGS
    CUSTOM_STRINGS = CUSTOM_STRINGS[:4]
except ImportError:
    CUSTOM_STRINGS = []

HOTKEY_REFERENCE = [
    ("Ctrl+Alt+N", "Full Name"),
    ("Ctrl+Alt+E", "Email"),
    ("Ctrl+Alt+P", "Phone"),
    ("Ctrl+Alt+A", "Address"),
    ("Ctrl+Alt+Z", "ZIP Code"),
    ("Ctrl+Alt+C", "Random Card #"),
] + [
    (f"Ctrl+Alt+{i}", f"{card[0]} test card")
    for i, card in enumerate(TEST_CARDS, start=1)
] + [
    (f"Ctrl+Alt+{i}", label)
    for i, (label, _) in enumerate(CUSTOM_STRINGS, start=5)
] + [
    ("Ctrl+Alt+R", "Repeat Last"),
    ("Ctrl+Alt+T", "Toggle Notifications"),
]


def make_icon_image():
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([1, 1, 30, 30], fill=(30, 120, 220))
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
    time.sleep(0.05)  # let hotkey modifier keys release before pasting
    keyboard.send("ctrl+v")


def repeat_last():
    if last_value is not None:
        copy(last_label, last_value)


def toggle_notifications():
    global notifications_enabled
    notifications_enabled = not notifications_enabled
    notification.notify(
        title="qafill",
        message=f"Notifications {'ON' if notifications_enabled else 'OFF'}",
        app_name="qafill",
        timeout=2,
    )


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
    for i, (hotkey, desc) in enumerate(HOTKEY_REFERENCE, start=1):
        tk.Label(frame, text=hotkey, font=("Consolas", 10), anchor="w", width=22).grid(
            row=i, column=0, sticky="w", pady=1
        )
        tk.Label(frame, text=desc, font=("Segoe UI", 10), anchor="w").grid(
            row=i, column=1, sticky="w", padx=(8, 0)
        )
    tk.Button(frame, text="Close", command=win.destroy, width=10).grid(
        row=len(HOTKEY_REFERENCE) + 1, columnspan=2, pady=(12, 0)
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


# Register hotkeys
keyboard.add_hotkey("ctrl+alt+t", toggle_notifications)
keyboard.add_hotkey("ctrl+alt+r", repeat_last)

for hotkey, (label, generator) in HOTKEYS.items():
    keyboard.add_hotkey(hotkey, lambda lbl=label, gen=generator: copy(lbl, gen()))

for i, (card_type, number, exp, cvv) in enumerate(TEST_CARDS, start=1):
    keyboard.add_hotkey(
        f"ctrl+alt+{i}",
        lambda t=card_type, n=number: copy(f"{t}", n),
    )

for i, (label, value) in enumerate(CUSTOM_STRINGS, start=5):
    keyboard.add_hotkey(
        f"ctrl+alt+{i}",
        lambda lbl=label, val=value: copy(lbl, val),
    )

# Run tray icon on main thread - keeps process alive
icon = pystray.Icon("qafill", make_icon_image(), "qafill", build_menu())
icon.run()
