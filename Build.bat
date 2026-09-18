@echo off
rem Build FanacAnalyser.exe.  If FanacAnalyser.ico is present it becomes the exe's icon.
rem (Unlike FanzinesEditor, FanacAnalyser has no main window of its own -- only occasional message
rem boxes -- so there is nothing to set a runtime window icon on and the .ico is not bundled inside.)
rem If the icon is absent, the build proceeds with the default icon.
if exist FanacAnalyser.ico (
    .\.venv12\Scripts\pyinstaller.exe --onefile --log-level=DEBUG --windowed --icon=FanacAnalyser.ico FanacAnalyser.py
) else (
    echo No FanacAnalyser.ico found -- building with the default icon.
    .\.venv12\Scripts\pyinstaller.exe --onefile --log-level=DEBUG --windowed FanacAnalyser.py
)
