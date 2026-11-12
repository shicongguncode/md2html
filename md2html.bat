@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
pushd "%~dp0"

set "PYTHON=python"
where py >nul 2>nul && set "PYTHON=py -3"

if "%~1"=="" goto :no_input

rem 只有一个文件时自动打开浏览器；多个文件时只批量转换，不弹窗口。
set "OPEN_FLAG="
if "%~2"=="" set "OPEN_FLAG=--open"

set "FAILED="
:convert_loop
if "%~1"=="" goto :after_loop
%PYTHON% -m md2html %OPEN_FLAG% "%~f1"
if errorlevel 1 set "FAILED=1"
shift
goto :convert_loop

:after_loop
if not defined FAILED goto :success
echo.
echo 转换失败，请查看上面的错误信息。
pause
popd
endlocal & exit /b 1

:success
popd
endlocal & exit /b 0

:no_input
echo 用法：把 .md 文件拖到本文件上，或运行 md2html.bat 加文件路径。
pause
popd
endlocal & exit /b 1
