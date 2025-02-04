@echo off
setlocal

call .\parse_args.bat %*
:: Exit due to passing -h --help -? /? flag
if errorlevel 3 exit /b 0

pushd %~dp0

call .\get_dependencies.bat %*
if errorlevel 1 ( goto Error )

call .\generate_projects.bat
if errorlevel 1 ( goto Error )

echo Building project for %CONFIG% configuration.

pushd _compiler
call "..\_build\host-deps\cmake\bin\cmake.exe" --build . --config %CONFIG% -- /m:%NUMBER_OF_PROCESSORS%
if errorlevel 1 ( goto Error )

popd

call .\install.bat %*
if errorlevel 1 ( goto Error )

:Success
echo Build script succeeded
exit /b 0

:Error
echo Build script failed
exit /b %errorlevel%
