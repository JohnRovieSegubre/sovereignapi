# create_remote_key.ps1
# Creates an API key on the remote server non-interactively
# Usage: .\create_remote_key.ps1 [AgentName]

param(
    [string]$AgentName = "SimUser_01"
)

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

Write-Host ">>> Creating Key for $AgentName..." -ForegroundColor Cyan

$cmd = "cd $REMOTE_PATH && sudo docker-compose exec -T gateway python api_key_registry.py create $AgentName"

if ($SSH_KEY) {
    ssh -i $SSH_KEY $USER@$SERVER_IP $cmd
}
else {
    ssh $USER@$SERVER_IP $cmd
}

Write-Host ">>> Done."
