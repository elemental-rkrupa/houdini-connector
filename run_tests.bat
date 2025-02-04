@echo off
setlocal
pushd %~dp0

echo "Running HDA (Houdini Engine)"
echo "%~dp0repo.bat test --suite he_hdas"
call %~dp0repo.bat test --suite he_hdas


echo "Running pytests"
echo "%~dp0run_tests_pytest.bat %*"
call %~dp0run_tests_pytest.bat %*
