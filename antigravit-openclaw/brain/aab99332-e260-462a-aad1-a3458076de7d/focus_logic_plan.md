# Hybrid Focus Logic

We need to know if the Monitor is the "Active Window" before we decide to push it back.

## PowerShell Logic
```powershell
$code = @"
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
"@
Add-Type -MemberDefinition $code -Name Win32 -Namespace Native
$hwnd = [Native.Win32]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 256
[Native.Win32]::GetWindowText($hwnd, $sb, 256)
$title = $sb.ToString()

# If title contains "Antigravity V2 Watchdog" or "python", get out of the way
if ($title -match "Watchdog" -or $title -match "python") {
    [System.Windows.Forms.SendKeys]::SendWait('%{ESC}')
    Start-Sleep -Milliseconds 500
}

# Now safe to type
[System.Windows.Forms.SendKeys]::SendWait($Message)
```
