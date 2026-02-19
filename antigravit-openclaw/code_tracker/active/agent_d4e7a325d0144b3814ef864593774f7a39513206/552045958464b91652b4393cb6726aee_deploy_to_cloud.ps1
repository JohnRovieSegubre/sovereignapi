Ó# deploy_to_cloud.ps1
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

# 2a. Update .env with x402 Config (Interactive)
Write-Host ">>> Configuring x402..." -ForegroundColor Cyan
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
Û *cascade08ÛÜ *cascade08Üï*cascade08ï *cascade08Ø*cascade08ØÚ *cascade08Úç *cascade08çë*cascade08ëÿ *cascade08ÿ*cascade08*cascade08‘*cascade08‘­ *cascade08­í*cascade08í… *cascade08…’*cascade08’Ÿ *cascade08Ÿ£*cascade08£º *cascade08º½ *cascade08½¾*cascade08¾Ü *cascade08Üà *cascade08àâ*cascade08âä *cascade08äç*cascade08çè *cascade08èú *cascade08ú*cascade08¥ *cascade08¥Ò*cascade08Òõ *cascade08õù*cascade08ùŒ	 *cascade08Œ		*cascade08	²	 *cascade08²	¸	*cascade08¸	Í	 *cascade08Í	Ó	*cascade08Ó	ê	 *cascade08ê	ğ	*cascade08ğ	„
 *cascade08„
†
 *cascade08†
Œ
*cascade08Œ
¢
 *cascade08¢
¨
*cascade08¨
´
 *cascade08´
¶
 *cascade08¶
¼
*cascade08¼
Î
 *cascade08Î
*cascade08§ *cascade08§Ç*cascade08ÇÒ *cascade08Òè *cascade08èî *cascade08îò*cascade08òö *cascade08öú *cascade08úü*cascade08üş *cascade08ş*cascade08‚ *cascade08‚Š *cascade08Š‹*cascade08‹ *cascade08*cascade08’ *cascade08’“*cascade08“œ *cascade08œ*cascade08Ÿ *cascade08Ÿ *cascade08 « *cascade08«¬*cascade08¬® *cascade08®› *cascade08›¢ *cascade08¢§*cascade08§¨ *cascade08¨°*cascade08°· *cascade08·¸*cascade08¸Â *cascade08Âé*cascade08éõ *cascade08õö*cascade08ö÷ *cascade08÷ø*cascade08øù *cascade08ùˆ*cascade08ˆŒ *cascade08Œ*cascade08 *cascade08*cascade08© *cascade08©´*cascade08´‹ *cascade08‹’ *cascade08’È *cascade08ÈÉ*cascade08Éå *cascade08åæ*cascade08æï *cascade08ïó *cascade08óõ*cascade08õ÷ *cascade08÷ú*cascade08úû *cascade08û *cascade08‚*cascade08‚† *cascade08†‡*cascade08‡‰ *cascade08‰Š*cascade08Š“ *cascade08“”*cascade08”– *cascade08–—*cascade08—¢ *cascade08¢£*cascade08£« *cascade08«´*cascade08´× *cascade08×Û*cascade08Ûó *cascade08óó*cascade08óö *cascade08ö÷*cascade08÷’ *cascade08’— *cascade08—™*cascade08™› *cascade08›*cascade08± *cascade08±Ä*cascade08Äº *cascade08º¾*cascade08¾× *cascade08××*cascade08×Ø *cascade08ØÙ*cascade08Ù£ *cascade08£§*cascade08§¼ *cascade08¼½*cascade08½á *cascade08áâ*cascade08âå *cascade08åæ*cascade08æÿ *cascade08ÿ€*cascade08€ *cascade08‘*cascade08‘¥ *cascade08¥¬ *cascade08¬± *cascade08±³*cascade08³µ *cascade08µ¸*cascade08¸Ë *cascade08ËŞ*cascade08ŞÇ *cascade08ÇÊ*cascade08ÊÓ *cascade08"(d4e7a325d0144b3814ef864593774f7a395132062:file:///c:/Users/rovie%20segubre/agent/deploy_to_cloud.ps1:&file:///c:/Users/rovie%20segubre/agent