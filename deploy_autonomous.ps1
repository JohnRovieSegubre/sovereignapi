
# deploy_autonomous.ps1
# Automates the deployment of Sovereign Intelligence Phase 8 to Google Cloud
# Usage: .\deploy_autonomous.ps1

$SERVER_IP = "34.55.175.24"
$USER = "rovie_segubre"
$REMOTE_PATH = "~/sovereign"

# Use default SSH key if not specified
if (-not $env:SSH_AUTH_SOCK) {
    if (Test-Path "$HOME\.ssh\id_ed25519") { $SSH_KEY = "$HOME\.ssh\id_ed25519" }
    elseif (Test-Path "$HOME\.ssh\id_rsa") { $SSH_KEY = "$HOME\.ssh\id_rsa" }
    else { Write-Error "No SSH key found in $HOME\.ssh"; exit 1 }
}
else {
    $SSH_KEY = $null # Rely on Agent
}

Write-Host ">>> Starting Autonomous Deployment to $SERVER_IP..." -ForegroundColor Cyan

# 0. Create remote directory if it doesn't exist
Write-Host ">>> Ensuring remote directory exists..." -ForegroundColor Yellow
ssh -i $SSH_KEY $USER@$SERVER_IP "mkdir -p $REMOTE_PATH/sdk"

# 1. Stop the Cloud Server (if running)
Write-Host ">>> Stopping remote server..." -ForegroundColor Yellow
ssh -i $SSH_KEY $USER@$SERVER_IP "cd $REMOTE_PATH && sudo docker-compose down 2>/dev/null || echo 'No containers running.'"

# 2. Upload Files
Write-Host ">>> Uploading Files..." -ForegroundColor Cyan

$files = @(
    "gateway_server.py", 
    "api_key_registry.py", 
    "autonomous_core.py", 
    "docker-compose.yml", 
    "Dockerfile", 
    "requirements.txt",
    "polygon_watcher.py",
    "cloud_mint.py"
)

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "   - Uploading $file"
        scp -i $SSH_KEY $file "${USER}@${SERVER_IP}:${REMOTE_PATH}/"
    }
    else {
        Write-Host "   - Skipping $file (not found locally)" -ForegroundColor DarkYellow
    }
}

# 2a. Update .env with x402 Config (Non-Interactive)
Write-Host ">>> Configuring Secrets (Autonomous)..." -ForegroundColor Cyan

# Parse local .env for values
$local_env_content = Get-Content ".env" -Raw
$x402_wallet = ""
if ($local_env_content -match "X402_PAY_TO_ADDRESS=(.+)") {
    $x402_wallet = $matches[1].Trim()
}

if ($x402_wallet) {
    Write-Host "   - Found x402 Wallet: $x402_wallet"
    $env_cmd = "grep -q 'ENABLE_X402' $REMOTE_PATH/.env || echo 'ENABLE_X402=true' >> $REMOTE_PATH/.env; grep -q 'X402_WALLET_ADDRESS' $REMOTE_PATH/.env || echo 'X402_WALLET_ADDRESS=$x402_wallet' >> $REMOTE_PATH/.env; grep -q 'X402_NETWORK' $REMOTE_PATH/.env || echo 'X402_NETWORK=eip155:84532' >> $REMOTE_PATH/.env"
    
    ssh -i $SSH_KEY "$USER@$SERVER_IP" "$env_cmd"
    Write-Host "   - Updated remote .env with x402 config" -ForegroundColor Green
}
else {
    Write-Host "   - Warning: X402_PAY_TO_ADDRESS not found in local .env. Skipping." -ForegroundColor Yellow
}

# Upload SDK Directory (Recursive)
Write-Host "   - Uploading SDK folder..."
scp -r -i $SSH_KEY sdk "${USER}@${SERVER_IP}:${REMOTE_PATH}/"

# Upload Landing Page
Write-Host "   - Uploading Landing page..."
scp -r -i $SSH_KEY landing "${USER}@${SERVER_IP}:${REMOTE_PATH}/"

# 3. Rebuild and Restart
Write-Host ">>> Rebuilding and Starting..." -ForegroundColor Cyan
ssh -i $SSH_KEY $USER@$SERVER_IP "cd $REMOTE_PATH && sudo docker-compose up -d --build"

# Check if the start command worked
if ($LASTEXITCODE -ne 0) {
    Write-Host ">>> Error: Deployment failed." -ForegroundColor Red
    exit 1
}

Write-Host ">>> Deployment Complete!" -ForegroundColor Green
