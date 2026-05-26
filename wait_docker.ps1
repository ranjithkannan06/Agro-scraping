Write-Host "Waiting for Docker engine to start..."
$ready = $false
for ($i = 1; $i -le 36; $i++) {
    $output = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "DOCKER_READY after $i attempts"
        $ready = $true
        break
    }
    Write-Host "Attempt $i/36 - engine not yet up, retrying in 5s..."
    Start-Sleep -Seconds 5
}
if (-not $ready) {
    Write-Host "TIMEOUT - Docker did not start within 3 minutes"
    exit 1
}
Write-Host "Launching docker-compose stack..."
docker-compose up --build -d
Write-Host "COMPOSE_DONE"
