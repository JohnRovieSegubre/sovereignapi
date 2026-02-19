# Antigravity Sentinel (Windows Version)
# Checks for new files in the watch directory every 3 seconds.

$watchDir = ".agent/watchdir"
$logFile = ".agent/sentinel.log"

# Ensure directories exist
if (-not (Test-Path -Path $watchDir)) {
    New-Item -ItemType Directory -Path $watchDir -Force | Out-Null
    Write-Host "Created watch directory: $watchDir"
}

Write-Host "Sentinel started at $(Get-Date)"
"Sentinel started at $(Get-Date)" | Add-Content $logFile

while ($true) {
    # Get files in watch directory
    $files = Get-ChildItem -Path $watchDir

    foreach ($file in $files) {
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        $msg = "[$timestamp] DETECTED: $($file.Name)"
        
        Write-Host $msg
        $msg | Add-Content $logFile
        
        # Process the file (Mock processing: Move to 'processed' folder would go here)
        # For now, just remove it to reset state
        Remove-Item $file.FullName
        "[$timestamp] PROCESSED: $($file.Name)" | Add-Content $logFile
    }

    Start-Sleep -Seconds 3
}
