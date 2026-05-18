$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = $projectRoot
$env:PYTHONIOENCODING = "utf-8"

python "$PSScriptRoot\build_dashboard_data.py"
python "$PSScriptRoot\server.py" --host 127.0.0.1 --port 8000
