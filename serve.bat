@echo off
cd /d "%~dp0"
echo.
echo  高考选校工具 - 本地服务
echo  浏览器打开: http://127.0.0.1:8765/
echo  按 Ctrl+C 停止
echo.
python -m http.server 8765
pause
