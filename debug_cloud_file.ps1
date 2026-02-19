# debug_cloud_file.ps1
# View remote files on the cloud server to verify deployments
# Usage: .\debug_cloud_file.ps1 [filename]

param(
    [string]$Filename = "gateway_server.py"
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

Write-Host ">>> Connecting to $SERVER_IP..." -ForegroundColor Cyan
Write-Host ">>> Inspecting: $REMOTE_PATH/$Filename" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray

if ($SSH_KEY) {
    ssh -i $SSH_KEY $USER@$SERVER_IP "cat $REMOTE_PATH/$Filename"
}
else {
    ssh $USER@$SERVER_IP "cat $REMOTE_PATH/$Filename"
}

Write-Host "`n----------------------------------------" -ForegroundColor Gray
Write-Host ">>> Done."
