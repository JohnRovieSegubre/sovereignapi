ßimport subprocess
import time
import logging
import sys
from pathlib import Path

# Config
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
MONITOR_SCRIPT = WORKSPACE_DIR / "scripts" / "antigravity_monitor.py"

logging.basicConfig(level=logging.INFO, format='%(asctime)s [WATCHDOG] %(message)s')

def wake_up_alert(message):
    ps_script = f"""
    Add-Type -AssemblyName System.Windows.Forms
    Start-Sleep -Milliseconds 1000
    [System.Windows.Forms.SendKeys]::SendWait('%{{TAB}}')
    Start-Sleep -Milliseconds 500
    [System.Windows.Forms.SendKeys]::SendWait('{message}')
    [System.Windows.Forms.SendKeys]::SendWait('{{ENTER}}')
    """
    try:
        subprocess.run(["powershell", "-Command", ps_script], check=True)
    except:
        pass

def run_monitor():
    import requests

    def check_website():
        url = "https://api.sovereign-api.com/v1/models"
        try:
            resp = requests.get(url, timeout=5)
            logging.info(f"üåê Website Health: {resp.status_code} OK | {len(resp.content)} bytes")
            if resp.status_code != 200:
                logging.error(f"‚ö†Ô∏è Website returned {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            logging.error(f"‚ùå Website Poll Failed: {e}")

    while True:
        # Check website first
        check_website()

        logging.info("Starting Monitor V2...")
        
        # Start the process
        process = subprocess.Popen([sys.executable, str(MONITOR_SCRIPT)], cwd=WORKSPACE_DIR)
        
        # Wait for it to finish (crash)
        exit_code = process.wait()
        
        logging.warning(f"Monitor exited with code {exit_code}")
        
        if exit_code != 0:
            logging.error("Detected CRASH. Triggering Alert...")
            wake_up_alert(f"‚ö†Ô∏è SYSTEM ALERT: Monitor crashed (Code {exit_code}). Retrying in 5s...")
        else:
            logging.info("Monitor exited normally (User stop?). Restarting anyway...")
            
        time.sleep(5)

if __name__ == "__main__":
    try:
        run_monitor()
    except KeyboardInterrupt:
        logging.info("Watchdog killed.")
¨ *cascade08¨¢
*cascade08¢
≠
 *cascade08≠
Á
*cascade08Á
ß *cascade08"(d4e7a325d0144b3814ef864593774f7a395132062:file:///c:/Users/rovie%20segubre/agent/scripts/watchdog.py:&file:///c:/Users/rovie%20segubre/agent