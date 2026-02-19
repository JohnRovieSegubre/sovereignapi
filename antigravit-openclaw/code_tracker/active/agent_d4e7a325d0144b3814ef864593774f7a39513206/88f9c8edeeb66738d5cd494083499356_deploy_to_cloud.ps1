”# deploy_to_cloud.ps1
# Automates the deployment of Sovereign Intelligence to a remote server
# Usage: .\deploy_to_cloud.ps1

# --- CONFIGURATION (EDIT THESE) ---
$SERVER_IP = $env:DEPLOY_SERVER_IP
$USER = $env:DEPLOY_USER

if (-not $SERVER_IP -or -not $USER) {
    Write-Host ">>> Error: Set DEPLOY_SERVER_IP and DEPLOY_USER environment variables first." -ForegroundColor Red
    Write-Host "   Example: `$env:DEPLOY_SERVER_IP='1.2.3.4'; `$env:DEPLOY_USER='myuser'"
    exit 1
}

$REMOTE_PATH = "~/sovereign"

Write-Host ">>> Starting Deployment to $SERVER_IP" -ForegroundColor Cyan

# 1. Stop the Cloud Server
Write-Host ">>> Stopping remote server..." -ForegroundColor Yellow
ssh $USER@$SERVER_IP "sudo docker-compose down"

# 2. Upload Files
Write-Host ">>> Uploading Files..." -ForegroundColor Cyan

$files = @("gateway_server.py", "api_key_registry.py", "autonomous_core.py")

foreach ($file in $files) {
    Write-Host "   - Uploading $file"
    scp $file "$USER@$SERVER_IP`:$REMOTE_PATH/"
}

Write-Host "   - Uploading SDK folder..."
scp -r sdk "$USER@$SERVER_IP`:$REMOTE_PATH/"

# 3. Rebuild and Restart
Write-Host ">>> Rebuilding and Starting..." -ForegroundColor Cyan
ssh $USER@$SERVER_IP "sudo docker-compose up -d --build"

if ($LASTEXITCODE -ne 0) {
    Write-Host ">>> Error: Deployment failed." -ForegroundColor Red
    exit 1
}

Write-Host ">>> Deployment Complete!" -ForegroundColor Green
Write-Host "   Server is running the latest version."

Write-Host "Create API Key? (Y/N)"
$response = Read-Host
if ($response -eq "Y" -or $response -eq "y") {
    Write-Host "Creating ProductionAgent_01 key..."
    ssh $USER@$SERVER_IP "sudo docker-compose exec gateway python api_key_registry.py create ProductionAgent_01"
}

Write-Host ">>> Done."
”*cascade08"(d4e7a325d0144b3814ef864593774f7a395132062Hfile:///c:/Users/rovie%20segubre/agent/sovereign_api/deploy_to_cloud.ps1:&file:///c:/Users/rovie%20segubre/agent