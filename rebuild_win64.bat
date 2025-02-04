@echo off
setlocal

call .\parse_args.bat %*
:: Exit due to passing -h --help -? /? flag
if errorlevel 3 exit /b 0

pushd %~dp0

if exist %~dp0_build\ (rmdir %~dp0_build /s /q)
if exist %~dp0_compiler\ (rmdir %~dp0_compiler /s /q)
if exist %~dp0_dependencies\ (rmdir %~dp0_dependencies /s /q)

if NOT "%KEEP_STAGING%" == "true" (
    if exist %~dp0_staging\ (
        rmdir %~dp0_staging /s /q
    )
)

call .\build_win64.bat %*
