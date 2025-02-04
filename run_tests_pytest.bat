@echo off
setlocal
pushd %~dp0

call .\parse_args.bat %*

:: We don't want the user custom settings to override the OMNI_*
:: and other environment variables we must define below,
:: so don't load houdini.env.
set HOUDINI_NO_ENV_FILE=1

:: Disable the omniverse.json package, so we can set all variables
:: and paths in this script.
set HOMNI_DISABLE_PACKAGE="1"

:: We don't want the user custom settings to override the OMNI_*
:: environment variables we must define for the test below,
:: so don't load houdini.env.
set HOUDINI_NO_ENV_FILE=1

set HOMNI=%~dp0_staging\houdini%HOUDINI_VER:~0,4%
set OMNI_ROOT=%HOMNI%\omni
set HOUDINI_PATH=%HOMNI%\houdini;%OMNI_ROOT%;^&
set PYTHONPATH="%HOUDINI_INSTALL%\%PY_VER_INT%";%OMNI_ROOT%\python;%OMNI_ROOT%\carb_sdk_plugins\bindings-python;%OMNI_ROOT%\omni_usd_resolver\bindings-python;%OMNI_ROOT%\omni_client_library\bindings-python;%PYTHONPATH%
set PYTHONHOME="%HOUDINI_BIN%\hython.exe"
set HOUDINI_USD_DSO_PATH=%OMNI_ROOT%\omni_usd_resolver\usd\omniverse\resolver\resources;%HOUDINI_USD_DSO_PATH%;^&
set PATH=%OMNI_ROOT%\lib;%OMNI_ROOT%\omni_usd_resolver;%OMNI_ROOT%\omni_client_library;%PATH%

set HOMNI_ENABLE_EXPERIMENTAL=1
set HOMNI_DEFAULT_CONNECTIONS=localhost
set HOMNI_ENABLE_LOGFILE=1

set HOUDINI_DSO_ERROR=2

:: When editing some test HDAs, $TEST_ID
:: may be used to generate unique output directories.
set TEST_ID=%RANDOM%

set HOMNI_LOGLEVEL=0

:: echo Init pytest "%~dp0repo.bat test --suite init_pytest"
:: call %~dp0repo.bat test --suite init_pytest

set PM_PYTHON_EXT=%HOUDINI_BIN%\hython.exe

echo Running pytest "%~dp0repo.bat test --coverage --suite pytests"
call %~dp0repo.bat test --suite pytests
