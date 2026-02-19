<#
.SYNOPSIS
    OpenClaw Local setup script for Windows.
    Installs Node.js, Ollama, pulls the Qwen 2.5 model, and configures OpenClaw.

.DESCRIPTION
    This script automates the deployment of a local AI agent environment.
    It checks for dependencies (Node.js, Ollama) and installs them using winget if missing.
    It then pulls the specified LLM model via Ollama and installs the OpenClaw CLI.
    Finally, it sets up the OpenClaw configuration to use the local Ollama instance.
#>

param (
    [string]$ModelName = "qwen2.5:7b"
)

function Write-Log {
    param(
        [string]$Text,
        [ConsoleColor]$Color = "Cyan"
    )
    Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] $Text" -ForegroundColor $Color
}

function Test-Command {
    param([string]$Name)
    if (Get-Command $Name -ErrorAction SilentlyContinue) {
        return $true
    }
    return $false
}

# --- Check Elevation ---
$Principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Log "[WARN] This script requires Administrator privileges to install software." "Yellow"
    Write-Log "Attempting to restart with elevated privileges..." "Yellow"
    Start-Process powershell.exe "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

Clear-Host
Write-Log "==========================================" "Cyan"
Write-Log "      OpenClaw Local Installer (Windows)  " "Cyan"
Write-Log "==========================================" "Cyan"
Write-Log "Target Model: $ModelName" "Gray"
Write-Host ""

# --- 1. Install Node.js ---
if (-not (Test-Command "node")) {
    Write-Log "[INFO] Node.js not found. Installing via winget..." "Yellow"
    try {
        winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
        Write-Log "[OK] Node.js installed." "Green"
        
        $MachinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        $UserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
        $env:Path = "$MachinePath;$UserPath"
    }
    catch {
        Write-Log "[ERROR] Failed to install Node.js. Please install it manually from https://nodejs.org/" "Red"
        exit 1
    }
}
else {
    Write-Log "[OK] Node.js is already installed." "Green"
}

# --- 2. Install Ollama ---
if (-not (Test-Command "ollama")) {
    Write-Log "[INFO] Ollama not found. Installing via winget..." "Yellow"
    try {
        winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
        Write-Log "[OK] Ollama installed." "Green"
        
        $MachinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        $UserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
        $env:Path = "$MachinePath;$UserPath"
    }
    catch {
        Write-Log "[ERROR] Failed to install Ollama. Please install it manually from https://ollama.com/" "Red"
        exit 1
    }
}
else {
    Write-Log "[OK] Ollama is already installed." "Green"
}

# --- 3. Start Ollama Service ---
Write-Log "[INFO] Ensuring Ollama service is running..." "Cyan"
try {
    $null = Invoke-WebRequest -Uri "http://localhost:11434" -Method Head -TimeoutSec 1 -ErrorAction SilentlyContinue
    Write-Log "[OK] Ollama service is reachable." "Green"
}
catch {
    Write-Log "[WARN] Ollama service not responding. Starting it..." "Yellow"
    Start-Process "ollama" "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
}

# --- 4. Pull Model ---
Write-Log "[INFO] Pulling AI Model '$ModelName' (this may take a while)..." "Cyan"
try {
    ollama pull $ModelName
    if ($LASTEXITCODE -eq 0) {
        Write-Log "[OK] Model '$ModelName' ready." "Green"
    }
    else {
        throw "Ollama exited with error code $LASTEXITCODE"
    }
}
catch {
    Write-Log "[ERROR] Failed to pull model. Check your internet connection." "Red"
    exit 1
}

# --- 5. Install OpenClaw (Clawdbot) ---
Write-Log "[INFO] Installing OpenClaw CLI..." "Cyan"
try {
    npm install -g clawdbot@latest
    Write-Log "[OK] OpenClaw installed." "Green"
}
catch {
    Write-Log "[ERROR] Failed to install OpenClaw via npm." "Red"
    exit 1
}

# --- 6. Configure OpenClaw ---
Write-Log "[INFO] Configuring OpenClaw..." "Cyan"
$ConfigDir = "$env:USERPROFILE\.clawdbot"
$ConfigFile = "$ConfigDir\clawdbot.json"

if (-not (Test-Path $ConfigDir)) {
    New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
}

$ConfigContent = @{
    "provider" = "openai";
    "openai"   = @{
        "baseUrl" = "http://localhost:11434/v1";
        "apiKey"  = "ollama";
        "model"   = $ModelName
    };
    "server"   = @{
        "port" = 3000
    }
}

try {
    $ConfigContent | ConvertTo-Json -Depth 5 | Out-File -FilePath $ConfigFile -Encoding utf8 -Force
    Write-Log "[OK] Configuration saved to $ConfigFile" "Green"
}
catch {
    Write-Log "[ERROR] Failed to write configuration file." "Red"
}

Write-Host ""
Write-Log "[DONE] Installation Complete!" "Green"
Write-Log "To start your agent, run:" "White"
Write-Log "    clawdbot start" "Green"
Write-Host ""

Read-Host "Press Enter to exit..."
