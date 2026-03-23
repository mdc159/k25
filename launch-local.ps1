# Launch Local Karaoke Stem Splitter
# Starts GPU backend (Docker) and Vite dev server, then opens browser

$root = $PSScriptRoot

Write-Host "=== Local Karaoke Stem Splitter ===" -ForegroundColor Cyan
Write-Host ""

# Start FastAPI backend in Docker with GPU
Write-Host "Starting backend (Docker + GPU)..." -ForegroundColor Yellow
docker compose -f "$root\docker-compose.yml" up --build -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker compose failed! Is Docker Desktop running with GPU support?" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "Backend ready: http://localhost:8001" -ForegroundColor Green

# Start Vite frontend in its own terminal
Write-Host "Starting frontend (Vite)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\ui'; npm run dev"

# Wait for Vite to bind port 5173
$tcp = $false
for ($i = 0; $i -lt 30; $i++) {
    $tcp = Test-NetConnection -ComputerName localhost -Port 5173 -WarningAction SilentlyContinue -InformationLevel Quiet
    if ($tcp) { break }
    Start-Sleep -Seconds 1
}

if (-not $tcp) {
    Write-Host "Vite didn't start -- check the frontend window for errors." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Frontend ready: http://localhost:5173" -ForegroundColor Green
Write-Host ""

# Open browser
Start-Process "http://localhost:5173"

Write-Host "Press '/' to open the file drop zone" -ForegroundColor Yellow
Write-Host ""
$composeFile = "$root\docker-compose.yml"
Write-Host "Stop backend:  docker compose -f `"$composeFile`" down" -ForegroundColor DarkGray
Write-Host "Backend logs:  docker compose -f `"$composeFile`" logs -f" -ForegroundColor DarkGray
