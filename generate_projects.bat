@echo off
setlocal

if not exist "_compiler" ( mkdir _compiler )
pushd _compiler

call "../_build/host-deps/cmake/bin/cmake.exe"  -G "Visual Studio 17 2022" -A x64 ../
if errorlevel 1 goto cmakeError

:Success
exit /B 0

:cmakeError
echo Error generating projects
exit /B 1

