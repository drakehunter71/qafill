"""
qafill setup - run once to install dependencies and register auto-start.
"""
import sys
import os
import subprocess
import tempfile

script_dir = os.path.dirname(os.path.abspath(__file__))


def install_deps():
    print("Installing dependencies...")
    requirements = os.path.join(script_dir, "requirements.txt")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements])
    print("Dependencies installed.")


def create_startup_shortcut():
    print("Creating startup shortcut...")

    startup_dir = os.path.join(
        os.environ["APPDATA"],
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
    )
    lnk_path = os.path.join(startup_dir, "qafill.lnk")
    script_path = os.path.join(script_dir, "testdata.py")

    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    # Write to a temp PS1 file to safely handle paths with spaces
    ps = f"""
$sh = New-Object -ComObject WScript.Shell
$sc = $sh.CreateShortcut('{lnk_path}')
$sc.TargetPath = '{pythonw}'
$sc.Arguments = '"{script_path}"'
$sc.WorkingDirectory = '{script_dir}'
$sc.Save()
Write-Output 'Startup shortcut created.'
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ps1", delete=False, encoding="utf-8") as f:
        f.write(ps)
        ps_file = f.name

    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_file],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"Warning: could not create startup shortcut.\n{result.stderr.strip()}")
            print("You can still run qafill manually with start.bat.")
    finally:
        os.unlink(ps_file)


if __name__ == "__main__":
    install_deps()
    create_startup_shortcut()
    print()
    print("Setup complete.")
    print("Run start.bat to launch qafill now, or restart Windows to auto-start.")
