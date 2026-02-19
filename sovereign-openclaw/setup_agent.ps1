param(
    [string]$Name,
    [string]$ApiKey,
    [string]$GatewayWallet,
    [string]$PrivateKey,
    [string]$GatewayUrl, # Added CLI param for override
    [switch]$NewWallet
)

$ErrorActionPreference = "Stop"

function Print-Header {
    Clear-Host
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host "   SOVEREIGN OPENCLAW - AGENT SETUP WIZARD    " -ForegroundColor Cyan
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host ""
}

function Safe-Run {
    param([string]$Command, [string]$Arguments)
    $p = Start-Process -FilePath $Command -ArgumentList $Arguments -NoNewWindow -Wait -PassThru
    return $p.ExitCode
}

function Check-Python {
    Write-Host "Checking prerequisites..." -ForegroundColor Gray
    if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
        Write-Host "❌ Python not found! Please install Python 3.11+" -ForegroundColor Red
        exit 1
    }
    
    # Check dependencies silently first
    $code = Safe-Run "python" "-c `"import eth_account`""
    
    if ($code -ne 0) {
        Write-Host "Installing setup dependencies..." -ForegroundColor Yellow
        $installCode = Safe-Run "python" "-m pip install eth-account"
        if ($installCode -ne 0) {
            Write-Host "❌ Failed to install dependencies. Try running as Admin." -ForegroundColor Red
            exit 1
        }
    }
}

function Get-Input {
    param([string]$Prompt, [bool]$Mask = $false)
    if ($Mask) {
        $Secure = Read-Host -Prompt $Prompt -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
        return [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    }
    return Read-Host -Prompt $Prompt
}

Print-Header
Check-Python

# 1. Identity & Auto-Registration
Write-Host "1. IDENTITY" -ForegroundColor Green

if (-not $Name) {
    $Name = Get-Input "Agent Name (default: OpenClaw-001)"
}
if ([string]::IsNullOrWhiteSpace($Name)) { $Name = "OpenClaw-001" }
# Sanitize Name (Replace spaces with hyphens to prevent server errors)
$Name = $Name.Replace(" ", "-")

# Default to official API if not overridden by CLI
$DefaultGateway = "https://api.sovereign-api.com/v1"
if ([string]::IsNullOrWhiteSpace($GatewayUrl)) { 
    $GatewayUrl = $DefaultGateway
    Write-Host "Using Sovereign Gateway: $GatewayUrl" -ForegroundColor Gray
}

# Try Auto-Registration (with retry logic for name collisions)
Write-Host "Attempting auto-registration with $GatewayUrl..." -ForegroundColor Gray

function Register-Agent {
    param($AgentName)
    try {
        $RegBody = @{ name = $AgentName } | ConvertTo-Json
        $Response = Invoke-RestMethod -Method Post -Uri "$GatewayUrl/register" -Body $RegBody -ContentType "application/json" -ErrorAction Stop
        return $Response
    }
    catch {
        # Extract detailed error message from response stream if available
        if ($_.Exception.Response) {
            $Stream = $_.Exception.Response.GetResponseStream()
            $Reader = New-Object System.IO.StreamReader($Stream)
            $Details = $Reader.ReadToEnd()
            Write-Host "[DEBUG] Server Error Details: $Details" -ForegroundColor DarkGray
        }
        return $null
    }
}

$Response = Register-Agent -AgentName $Name

# If failed, try appending a random suffix (handle name collisions)
if (-not $Response) {
    $RandomSuffix = -join ((48..57) + (97..102) | Get-Random -Count 4 | ForEach-Object { [char]$_ })
    $pcName = "$Name-$RandomSuffix"
    Write-Host "[INFO] Standard name taken/invalid. Retrying as '$pcName'..." -ForegroundColor Yellow
    $Response = Register-Agent -AgentName $pcName
    if ($Response) { $Name = $pcName }
}

if ($Response -and $Response.api_key) {
    $ApiKey = $Response.api_key
    Write-Host "[OK] Auto-Registered Successfully as '$Name'!" -ForegroundColor Green
    Write-Host "   API Key: $ApiKey" -ForegroundColor Gray
    
    if ($Response.gateway_wallet) {
        $GatewayWallet = $Response.gateway_wallet
        Write-Host "   Gateway Wallet: $GatewayWallet" -ForegroundColor Gray
    }
}
else {
    Write-Host "[WARN] Auto-registration failed. You may need to create a key manually." -ForegroundColor Yellow
}

if (-not $ApiKey) {
    Write-Host "Enter Sovereign API Key (or press Enter to skip for now)" -ForegroundColor Gray
    $ApiKey = Get-Input "Sovereign API Key (sk-sov-xxx)" -Mask $true
}

if ([string]::IsNullOrWhiteSpace($ApiKey) -or $ApiKey -eq "SKIP") {
    Write-Host "[WARN] Skipping API Key. Agent will need configuration later." -ForegroundColor Yellow
    $ApiKey = ""
}
else {
    while (-not $ApiKey.StartsWith("sk-sov-")) {
        Write-Host "[ERROR] Invalid API Key format (must start with sk-sov-)" -ForegroundColor Red
        $ApiKey = Get-Input "Sovereign API Key (or 'SKIP')" -Mask $true
        if ($ApiKey -eq "SKIP" -or [string]::IsNullOrWhiteSpace($ApiKey)) {
            $ApiKey = ""
            break
        }
    }
}

if (-not $GatewayWallet) {
    # Default to official X402 wallet if server didn't provide one
    $DefaultWallet = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
    $GatewayWallet = $DefaultWallet
    Write-Host "[OK] using Official Sovereign Gateway ($DefaultWallet)" -ForegroundColor Gray
}
while ([string]::IsNullOrWhiteSpace($GatewayWallet) -or -not $GatewayWallet.StartsWith("0x")) {
    Write-Host "[ERROR] Invalid Wallet Address" -ForegroundColor Red
    $GatewayWallet = Get-Input "Gateway Wallet Address"
}

# 2. Wallet
Write-Host "`n2. WALLET SETUP" -ForegroundColor Green
$AgentPrivateKey = ""
$WalletAddress = ""

if ($NewWallet) {
    $Choice = "1"
}
elseif ($PrivateKey) {
    $Choice = "2"
    $AgentPrivateKey = $PrivateKey
}
else {
    Write-Host "[1] Create New Wallet"
    Write-Host "[2] Use Existing Private Key"
    $Choice = Get-Input "Select option (1/2)"
}

if ($Choice -eq "1") {
    Write-Host "`nGenerating new wallet..." -ForegroundColor Yellow
    # Run python helper to capture output
    $Output = python setup_helper.py --create
    Write-Host $Output
    
    # Parse the output for key/address
    $KeyLine = $Output | Where-Object { $_ -match "PRIVATE_KEY=(.*)" } | Select-Object -First 1
    if ($KeyLine -match "PRIVATE_KEY=(.*)") {
        $AgentPrivateKey = $matches[1]
    }
    
    $AddrLine = $Output | Where-Object { $_ -match "ADDRESS=(.*)" } | Select-Object -First 1
    if ($AddrLine -match "ADDRESS=(.*)") {
        $WalletAddress = $matches[1]
    }
    
    Write-Host "`nPlease scan the QR code above and send ~$5 USDC (Polygon)." -ForegroundColor Cyan
    if (-not $NewWallet) {
        # Only pause if interactive
        Read-Host "Press Enter after you have sent the funds..."
    }
}
elseif ($Choice -eq "2") {
    if (-not $AgentPrivateKey) {
        $KeyInput = Get-Input "Enter Private Key (0x...)" -Mask $true
        $AgentPrivateKey = $KeyInput
    }
    
    try {
        $Output = python setup_helper.py --validate "$AgentPrivateKey"
        if ($LASTEXITCODE -ne 0) { throw "Invalid Key" }
        
        $Output -match "PRIVATE_KEY=(.*)" | Out-Null
        $AgentPrivateKey = $matches[1]
        $Output -match "ADDRESS=(.*)" | Out-Null
        $WalletAddress = $matches[1]
        Write-Host "[OK] Wallet Verified: $WalletAddress" -ForegroundColor Green
    }
    catch {
        Write-Host "[ERROR] Invalid Private Key!" -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "[ERROR] Invalid choice" -ForegroundColor Red
    exit 1
}

# 3. Configuration
Write-Host "`n3. CONFIGURATION" -ForegroundColor Green
$EnvContent = @"
# Sovereign OpenClaw Config
# Generated by setup_agent.ps1

SOVEREIGN_API_KEY=$ApiKey
GATEWAY_URL=$GatewayUrl
GATEWAY_WALLET=$GatewayWallet
AGENT_PRIVATE_KEY=$AgentPrivateKey
AGENT_NAME=$Name
POLYGON_RPC=https://polygon-rpc.com
MOLTBOOK_API_KEY=
MOLTBOOK_BASE_URL=https://www.moltbook.com/api/v1
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
MISSION_INTERVAL_SECONDS=1800
BRAIN_DIR=$BrainDir
"@

Set-Content -Path $ConfigFile -Value $EnvContent
Write-Host "[OK] $ConfigFile file created!" -ForegroundColor Green

# 4. Install & Launch
Write-Host "`n4. LAUNCH" -ForegroundColor Green
Write-Host "Installing dependencies..." -ForegroundColor Gray
Safe-Run "python" "-m pip install -r requirements.txt" | Out-Null

Write-Host "`n[DONE] Setup Complete! Starting Agent..." -ForegroundColor Cyan
Start-Sleep -Seconds 2
python sovereign_openclaw.py --env $ConfigFile
