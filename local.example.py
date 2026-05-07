# Copy this file to local.py and fill in your own strings.
# local.py is gitignored - safe for credentials and environment-specific values.
#
# Mapped to Ctrl+Alt+5 through Ctrl+Alt+8. Up to 4 entries: (label, value)
#
# Value can be a literal string or any callable (lambda/function).
# The callable is invoked once at startup.

import os
import subprocess

CUSTOM_STRINGS = [
    # Literal string
    ("Test Email",    "testuser@example.com"),

    # 1Password CLI
    ("Password",      lambda: subprocess.run(
                          ["op", "read", "op://Personal/My Test Account/password"],
                          capture_output=True, text=True
                      ).stdout.strip()),

    # Environment variable
    ("API Key",       lambda: os.environ.get("MY_API_KEY", "")),

    # Plain text file
    ("Token",         lambda: open("secret.txt").read().strip()),
]
