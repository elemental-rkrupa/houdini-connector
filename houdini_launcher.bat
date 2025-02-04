@echo off
setlocal

call .\parse_args.bat %*

pushd %~dp0

:: We don't want the user custom settings to override the OMNI_*
:: and other environment variables we must define below,
:: so don't load houdini.env.
set HOUDINI_NO_ENV_FILE=1

set CLIENT_LIB_CONFIG=release

:: optional argument sets PATH to debug client library binaries.
if "%1" equ "--debug" ( set "CLIENT_LIB_CONFIG=debug" )

:: Disable the omniverse.json package, so we can set all variables
:: and paths in this script.
set HOMNI_DISABLE_PACKAGE="1"
::set HOUDINI_PACKAGE_VERBOSE="1"

set HOMNI=%~dp0_staging\houdini%HOUDINI_VER:~0,4%
set OMNI_ROOT=%HOMNI%\omni
set CARB_APP_PATH=%OMNI_ROOT%
set HOUDINI_PATH=%HOMNI%\houdini;%OMNI_ROOT%;^&
set PYTHONPATH=%OMNI_ROOT%\python;%OMNI_ROOT%\carb_sdk_plugins\bindings-python;%OMNI_ROOT%\omni_usd_resolver\bindings-python;%OMNI_ROOT%\omni_client_library\bindings-python;%PYTHONPATH%
set HOUDINI_USD_DSO_PATH=%OMNI_ROOT%\omni_usd_resolver\usd\omniverse\resolver\resources;%HOUDINI_USD_DSO_PATH%;^&
set PATH=%OMNI_ROOT%\lib;%OMNI_ROOT%\omni_usd_resolver;%OMNI_ROOT%\omni_client_library;%PATH%

set HOMNI_ENABLE_EXPERIMENTAL=1
set HOMNI_DEFAULT_CONNECTIONS=localhost
set HOMNI_ENABLE_LOGFILE=1

set HOUDINI_DSO_ERROR=2

:: set HOMNI_CARB_SETTINGS_TOML_PATH=%userprofile%\Documents\houdini20.0;%userprofile%\Documents\houdini20.0\omniverse

:: Enable TF_DEBUG to tell Houdini to print the plugin.json it loads
:: set TF_DEBUG=OMNI_USD_*
:: set TF_DEBUG=SDF_LAYER

:: set OMNI_CONN_LOG=C:\logs\debugOut.log
:: set HOMNI_LOGLEVEL=0

:: When editing some test HDAs, $TEST_ID
:: may be used to generate unique output directories.
set TEST_ID=%RANDOM%

@echo on
call "%HOUDINI_BIN%\houdini.exe"
