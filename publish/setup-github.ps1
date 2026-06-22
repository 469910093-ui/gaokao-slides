# 一键初始化 Git 并提示推送步骤（不自动 push）
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "未检测到 git，请先安装 Git: https://git-scm.com/" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path .git)) {
    git init
    git branch -M main
    Write-Host "已初始化 git 仓库" -ForegroundColor Green
} else {
    Write-Host "git 仓库已存在" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host "1. 在 GitHub 新建空仓库 xiaohongshu-gaokao-slides"
Write-Host "2. 执行："
Write-Host '   git add .'
Write-Host '   git commit -m "发布高考选专业工具站"'
Write-Host '   git remote add origin https://github.com/你的用户名/xiaohongshu-gaokao-slides.git'
Write-Host '   git push -u origin main'
Write-Host "3. GitHub → Settings → Pages → Source 选 GitHub Actions"
Write-Host "4. 等部署完成后访问：https://你的用户名.github.io/xiaohongshu-gaokao-slides/"
Write-Host ""
Write-Host "小红书文案见：publish\小红书发布指南.txt" -ForegroundColor Green
