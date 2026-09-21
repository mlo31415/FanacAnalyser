@echo off
rem ---------------------------------------------------------------------------------------------------------------
rem Build FanacAnalyzer.exe.
rem
rem --windowed, because FanacAnalyzer now puts up its own log window: a scrollable one you can minimise, with a
rem Cancel button, carrying the program's icon in the taskbar.  A console build would put a bare black rectangle
rem beside it.  The old reasons for keeping the console no longer apply -- it was the only thing giving a taskbar
rem entry, and sys.stdout being None mattered, but the log window replaces stdout with its own writer before any
rem work begins and copes with there being no console behind it.
rem
rem --add-data FanacAnalyzer.ico: the window needs the icon at RUN time, not just stamped on the exe by --icon, so
rem it has to travel inside the one-file bundle as well.  IconPathname() finds it in either place.
rem
rem Nothing else needs bundling.  The control files, templates and APA material are read from disk at run time, out
rem of the folders named by the Input Directory and Report Directory settings, so they must sit beside the exe
rem exactly as they sit beside FanacAnalyzer.py.
rem ---------------------------------------------------------------------------------------------------------------

setlocal
cd /d "%~dp0"

rem PyInstaller is run as a module rather than through .venv12\Scripts\pyinstaller.exe.  Those little .exe launchers
rem have the interpreter's full path baked into them, so renaming the project folder leaves every one of them --
rem pip.exe included -- pointing at a directory which no longer exists.  They then fail with exit code 1 and print
rem nothing whatever, which looks exactly like a broken build script.  Running the module sidesteps all of that.
if not exist ".venv12\Scripts\python.exe" (
    echo.
    echo Cannot find .venv12\Scripts\python.exe -- is the virtual environment there?
    echo.
    exit /b 1
)
.\.venv12\Scripts\python.exe -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo.
    echo PyInstaller is not installed in .venv12.  Install the pinned set first:
    echo     .venv12\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    exit /b 1
)

rem An orphaned dist-info folder next to the real one stops PyInstaller finding ANY of its hooks, and it says nothing
rem about it.  The exe then builds happily and fails only at run time, having quietly lost the TLS certificates and
rem one of unidecode's character tables.  That cost a long afternoon once, so check for it before building.
set HOOKDIRS=0
for /f %%c in ('dir /b /ad ".venv12\Lib\site-packages\pyinstaller_hooks_contrib-*.dist-info" 2^>nul ^| find /c /v ""') do set HOOKDIRS=%%c
if not "%HOOKDIRS%"=="1" (
    echo.
    echo WARNING: found %HOOKDIRS% pyinstaller_hooks_contrib-*.dist-info folders, expected exactly 1.
    echo A leftover one disables every PyInstaller hook silently.  Delete the stale folder before trusting this build.
    echo.
    pause
)

echo Building FanacAnalyzer.exe ...
if exist "FanacAnalyzer.ico" (
    .\.venv12\Scripts\python.exe -m PyInstaller --onefile --windowed --log-level=INFO --icon=FanacAnalyzer.ico --add-data "FanacAnalyzer.ico;." FanacAnalyzer.py
) else (
    echo No FanacAnalyzer.ico found -- building without one, so the log window will show Tk's default icon.
    .\.venv12\Scripts\python.exe -m PyInstaller --onefile --windowed --log-level=INFO FanacAnalyzer.py
)

if errorlevel 1 (
    echo.
    echo BUILD FAILED.  See the messages above; build\FanacAnalyzer\warn-FanacAnalyzer.txt lists what PyInstaller
    echo could not resolve.
    exit /b 1
)

if not exist "dist\FanacAnalyzer.exe" (
    echo.
    echo PyInstaller reported success but dist\FanacAnalyzer.exe is not there.
    exit /b 1
)

echo.
for %%f in ("dist\FanacAnalyzer.exe") do echo Built dist\FanacAnalyzer.exe  --  %%~zf bytes, %%~tf
echo.
echo Copy it to wherever it is to run, alongside "FanacAnalyzer Parameters.txt", "FanacAnalyzer - Inputs\" and
echo "People Canonical Names.txt".  Then run it once and read the error log before trusting it: a build which has
echo lost its hooks fails only at run time.
endlocal
