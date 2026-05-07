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

**Double-click** `start.bat`, or restart Windows after running setup for auto-start.

**PowerShell:**
```powershell
Start-Process -FilePath (Get-Command pythonw.exe).Source -ArgumentList "$PWD\testdata.py" -WorkingDirectory $PWD
```

**From anywhere:**
```powershell
$q = "C:\path\to\qafill"
Start-Process -FilePath (Get-Command pythonw.exe).Source -ArgumentList "$q\testdata.py" -WorkingDirectory $q
```

A blue dot appears in the system tray overflow (`^` near the clock) to confirm it is running. Startup is also logged to `qafill.log` in the project folder.

**Stopping:** Right-click the tray icon > Exit.

## Hotkeys

| Hotkey | Output |
|--------|--------|
| `Ctrl+Alt+N` | Full name |
| `Ctrl+Alt+F` | First name |
| `Ctrl+Alt+L` | Last name |
| `Ctrl+Alt+E` | Email address |
| `Ctrl+Alt+P` | Phone number |
| `Ctrl+Alt+A` | Full address (single line) |
| `Ctrl+Alt+Z` | ZIP code |
| `Ctrl+Alt+C` | Random credit card number |
| `Ctrl+Alt+1` | Test card 1 |
| `Ctrl+Alt+2` | Test card 2 |
| `Ctrl+Alt+3` | Test card 3 |
| `Ctrl+Alt+4` | Test card 4 |
| `Ctrl+Alt+5-8` | Custom strings (local.py) |
| `Ctrl+Alt+R` | Repeat last generated value |
| `Ctrl+Alt+T` | Toggle toast notifications on/off |

All hotkeys copy to clipboard and auto-paste into the focused field.

## System Tray

The tray icon changes color to reflect notification state:
- **Blue dot** - notifications off
- **Orange dot** - notifications on

The app appears as **qafill** in Settings > Personalization > Taskbar > Other system tray icons (not "python").

Right-click to toggle notifications, open the hotkey reference window, or exit.

## Local Custom Strings

Create `local.py` (gitignored) using `local.example.py` as a template. Mapped to `Ctrl+Alt+5` through `Ctrl+Alt+8`. Values resolve once at startup.

Values can be a **literal string** or any **callable** - use a lambda to pull from any source:

```python
import os
import subprocess

CUSTOM_STRINGS = [
    ("Test Email",    "testuser@example.com"),                   # literal
    ("Password",      lambda: os.environ.get("MY_PASS", "")),    # Windows env var
    ("OP Secret",     lambda: subprocess.run(                    # 1Password CLI
                          ["op", "read", "op://vault/item/field"],
                          capture_output=True, text=True
                      ).stdout.strip()),
    ("From File",     lambda: open("secret.txt").read().strip()), # file
]
```

### Windows environment variables

```powershell
# Set (persists across reboots)
[System.Environment]::SetEnvironmentVariable("MY_PASS", 'value$here', "User")

# Verify
[System.Environment]::GetEnvironmentVariable("MY_PASS", "User")
```

Use **single quotes** in PowerShell if the value contains `$` - double quotes will expand it as a variable.

Restart qafill after adding new variables.

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
