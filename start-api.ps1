$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
# Remove process-level overrides left by start-demo.ps1; load .env instead.
foreach ($name in @('MODEL_MODE', 'DATA_DIR', 'EMBEDDING_DIM', 'QDRANT_URL')) {
    [Environment]::SetEnvironmentVariable($name, $null, 'Process')
}
$env:MODEL_MODE = 'api'
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
