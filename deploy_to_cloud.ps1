# deploy_to_cloud.ps1
# Automates the deployment of Sovereign Intelligence Phase 8 to Google Cloud
# Usage: .\deploy_to_cloud.ps1

$SERVER_IP = "34.55.175.24"
$USER = "rovie_segubre"
$REMOTE_PATH = "~/sovereign"
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

Write-Host ">>> Starting Deployment to $SERVER_IP..." -ForegroundColor Cyan

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

# 2a. Update .env with x402 and Gasless Config (Interactive)
Write-Host ">>> Configuring Secrets..." -ForegroundColor Cyan
$enable_x402 = Read-Host "Enable x402 Hybrid Payment? (Y/N) [Default: Y]"
if ($enable_x402 -eq "" -or $enable_x402 -eq "Y" -or $enable_x402 -eq "y") {
    $x402_wallet = Read-Host "Enter your Base Wallet Address for x402 payments (0x...)"
    if ($x402_wallet) {
        $env_cmd = "grep -q 'ENABLE_X402' $REMOTE_PATH/.env || echo 'ENABLE_X402=true' >> $REMOTE_PATH/.env; grep -q 'X402_WALLET_ADDRESS' $REMOTE_PATH/.env || echo 'X402_WALLET_ADDRESS=$x402_wallet' >> $REMOTE_PATH/.env"
        
        if ($SSH_KEY) {
            ssh -i "$SSH_KEY" "$USER@$SERVER_IP" "$env_cmd"
        }
        else {
            ssh "$USER@$SERVER_IP" "$env_cmd"
        }
        Write-Host "   - Updated remote .env with x402 config" -ForegroundColor Green
    }
}

# Legacy Facilitator Key prompt removed (Uses Coinbase Public Facilitator)


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

# 4. Success & Prompt
Write-Host ">>> Deployment Complete!" -ForegroundColor Green
Write-Host "   Server is running Phase 8."

Write-Host "Create API Key? (Y/N)" 
$response = Read-Host
if ($response -eq "Y" -or $response -eq "y") {
    Write-Host "Creating ProductionAgent_01 key..."
    ssh -i $SSH_KEY $USER@$SERVER_IP "cd $REMOTE_PATH && sudo docker-compose exec gateway python api_key_registry.py create ProductionAgent_01"
}

Write-Host ">>> Done."
