Set-Location $PSScriptRoot
Write-Host ""
Write-Host " 高考选校工具 - 本地服务" -ForegroundColor Yellow
Write-Host " 浏览器打开: http://127.0.0.1:8765/" -ForegroundColor Green
Write-Host " 按 Ctrl+C 停止"
Write-Host ""
python -m http.server 8765
