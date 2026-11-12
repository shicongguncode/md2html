@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0.."

python -m unittest discover -s tests
if errorlevel 1 goto :fail
python -m compileall -q md2html
if errorlevel 1 goto :fail

popd
endlocal & exit /b 0

:fail
popd
endlocal & exit /b 1
