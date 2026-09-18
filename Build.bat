@echo off
rem Build FanacAnalyser.exe.  If FanacAnalyser.ico is present it becomes the exe's icon.
rem (Unlike FanzinesEditor, FanacAnalyser has no main window of its own -- only occasional message
rem boxes -- so there is nothing to set a runtime window icon on and the .ico is not bundled inside.)
rem If the icon is absent, the build proceeds with the default icon.
rem
rem Deliberately NOT --windowed.  A windowed build gets no console, and since FanacAnalyser never
rem creates a lasting window it then shows nothing at all in the taskbar for the whole ~20 minute run.
rem Worse, --windowed leaves sys.stdout as None, so every line Log() prints is silently discarded and
rem only the log files get written.  Building for the console gives a taskbar entry carrying the icon
rem and puts the running commentary back on the screen.
if exist FanacAnalyser.ico (
    .\.venv12\Scripts\pyinstaller.exe --onefile --log-level=DEBUG --icon=FanacAnalyser.ico FanacAnalyser.py
) else (
    echo No FanacAnalyser.ico found -- building with the default icon.
    .\.venv12\Scripts\pyinstaller.exe --onefile --log-level=DEBUG FanacAnalyser.py
)
