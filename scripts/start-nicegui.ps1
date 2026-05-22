# 交易小算盘 NiceGUI 启动脚本（默认端口 8001）
# 用法: .\scripts\start-nicegui.ps1
#       .\scripts\start-nicegui.ps1 9000
#       $env:PORT=9000; .\scripts\start-nicegui.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Port = 8001
if ($args.Count -gt 0) {
    $Port = $args[0]
}
elseif ($env:PORT) {
    $Port = $env:PORT
}

Write-Host "启动 NiceGUI: http://localhost:$Port" -ForegroundColor Cyan
if ($Port -eq 8001) {
    uv run start-nicegui
}
else {
    uv run start-nicegui $Port
}
