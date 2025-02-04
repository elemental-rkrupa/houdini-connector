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
set PYTHONPATH=%OMNI_ROOT%\python;%OMNI_ROOT%\carb_sdk_plugins\bindings-python;%OMNI_ROOT%\omni_usd_resolver\bindings-python;%OMNI_ROOT%\omni_client_library\bindings-python;%PYTHONPATH%
set PYTHON_EXECUTABLE="%~dp0_build\target-deps\houdini_hdk\python%PY_VER_INT%\python.exe"
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

set TEST_DATA_DIR=%~dp0assets\test-data

:: set TF_DEBUG=SDF_LAYER
set PASSED=1
set RAN=0

if not exist %~dp0_build\Tests\Release\test_*.exe goto HETEST

for /f %%f in ('dir /b %~dp0_build\Tests\Release\test_*.exe') do (
    echo Running test %%f
    %~dp0_build\Tests\Release\%%f
	if errorlevel 1 (
		echo Test %%f failed!
		set PASSED=0
	)
    set RAN=1
)

:HETEST

:: Run the Houdini Engine test executable with all the test HDAs.
for /f %%f in ('dir /b %~dp0assets\test-data\houdini-engine\he_test*.hda') do (
    echo Running Houdini Engine test with %%f
    %~dp0_build\Tests\Release\houdini_engine_test.exe %~dp0assets\test-data\houdini-engine\%%f
	if errorlevel 1 (
		echo Test %%f failed!
		set PASSED=0
	)
    set RAN=1
)

IF /I "%RAN%"=="0" (
	echo Tests did not run.
	exit /b 1
)

IF /I "%PASSED%"=="1" (
	echo All tests passed!
	exit /b 0
) ELSE (
	exit /b 1
)