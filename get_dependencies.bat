@echo off
setlocal

call .\parse_args.bat %*
:: Exit due to passing -h --help -? /? flag
if errorlevel 3 exit /b 0

pushd "%~dp0"
mkdir .\_build

:: fetch
echo .\repo.bat --set-token hdkversion:%HDK_PACKAGE_VER% --set-token pyver:py%PY_VER_INT% --set-token usd_flavor:%USD_FLAVOR% build --fetch-only -r
.\repo.bat --set-token hdkversion:%HDK_PACKAGE_VER% --set-token pyver:py%PY_VER_INT% --set-token usd_flavor:%USD_FLAVOR% build --fetch-only -r
if errorlevel 1 exit /B
