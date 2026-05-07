# qafill

A Windows background tool that generates and auto-pastes test data via global hotkeys. Click into any field, press a hotkey, data is pasted instantly.

## Requirements

- Windows 10/11
- Python 3.8+

## Setup

```
git clone https://github.com/YOUR_USERNAME/qafill.git
cd qafill
setup.bat
```

`setup.bat` installs all dependencies and registers qafill to auto-start on login.

## Starting

Double-click `start.bat`, or restart Windows if you ran setup.

A blue dot appears in the system tray to confirm it is running.

## Hotkeys

| Hotkey | Output |
|--------|--------|
| `Ctrl+Alt+N` | Full name |
| `Ctrl+Alt+E` | Email address |
| `Ctrl+Alt+P` | Phone number |
| `Ctrl+Alt+A` | Full address (single line) |
| `Ctrl+Alt+Z` | ZIP code |
| `Ctrl+Alt+C` | Random credit card number |
| `Ctrl+Alt+1` | Test card 1 |
| `Ctrl+Alt+2` | Test card 2 |
| `Ctrl+Alt+3` | Test card 3 |
| `Ctrl+Alt+4` | Test card 4 |
| `Ctrl+Alt+R` | Repeat last generated value |
| `Ctrl+Alt+T` | Toggle toast notifications on/off |

All hotkeys copy to clipboard and auto-paste into the focused field.

## System Tray

Right-click the blue dot to:

- Toggle notifications on/off
- Open the hotkey reference window
- Exit

## Local Custom Strings

Create `local.py` (gitignored) using `local.example.py` as a template. Define up to 4 personal strings - test credentials, environment URLs, frequently used values, anything you paste repeatedly.

```python
CUSTOM_STRINGS = [
    ("Test Email",    "testuser@example.com"),
    ("Test Password", "Password123!"),
    ("Base URL",      "https://staging.example.com"),
    ("API Key",       "sk-test-abc123"),
]
```

Mapped to `Ctrl+Alt+5` through `Ctrl+Alt+8`. Only the hotkeys with defined values are registered - unused slots are ignored.

## Customizing Test Cards

Edit `TEST_CARDS` in `testdata.py` to use your payment processor's test card numbers:

```python
TEST_CARDS = [
    ("Visa",       "4111111111111111", "12/2026", "123"),
    ("Mastercard", "5500005555555559", "12/2026", "123"),
    ("Amex",       "378282246310005",  "12/2026", "1234"),
    ("Discover",   "6011111111111117", "12/2026", "123"),
]
```

## Adding More Data Types

Add an entry to `HOTKEYS` in `testdata.py`:

```python
"ctrl+alt+x": ("Label", lambda: fake.some_method()),
```

Common Faker methods: `fake.ssn()`, `fake.date_of_birth()`, `fake.user_name()`, `fake.company()`, `fake.iban()`

Full reference: https://faker.readthedocs.io

## Notes

- The `keyboard` library uses a low-level Windows hook. In rare cases it may not capture hotkeys inside windows running as Administrator.
- Notifications are off by default. Turn on with `Ctrl+Alt+T` when debugging.
