$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:MODEL_MODE = 'demo'
$env:DATA_DIR = 'data/demo'
$env:EMBEDDING_DIM = '256'
$env:QDRANT_URL = ''
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
