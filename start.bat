@echo off
setlocal enabledelayedexpansion
for /f "usebackq tokens=*" %%P in (`python -c "import sys,os; p=sys.executable; pw=p[:-10]+'pythonw.exe'; print(pw if os.path.exists(pw) else p)"`) do set PYTHONW=%%P
start "" "!PYTHONW!" "%~dp0testdata.py"
