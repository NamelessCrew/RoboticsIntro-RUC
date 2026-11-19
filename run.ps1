Set-Location $PSScriptRoot
if (-not (Test-Path "$PSScriptRoot/.venv/Scripts/python.exe")) {
    Write-Error "请先运行 .\setup.cmd 安装课程环境。"
    exit 1
}
& "$PSScriptRoot/.venv/Scripts/python.exe" run.py @args
exit $LASTEXITCODE
