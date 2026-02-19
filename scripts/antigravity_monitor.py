import os
import time
import shutil
import logging
import json
import threading
import subprocess
from pathlib import Path

# --- Configuration ---
# Detect workspace dynamically or use hardcoded if needed
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
INBOX_DIR = WORKSPACE_DIR / ".agent" / "inbox"
COMPLETED_DIR = INBOX_DIR / "completed"
FAILED_DIR = INBOX_DIR / "failed"
LOGS_DIR = INBOX_DIR / "logs"
ACTIONS_FILE = WORKSPACE_DIR / ".agent" / "actions.json"

POLL_INTERVAL = 3  # Faster polling since we are async

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "monitor_v2.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class AntigravityMonitor:
    def __init__(self):
        self.actions = {}
        self.load_actions()
        self.ensure_dirs()

    def load_actions(self):
        """Loads the whitelist of allowed actions."""
        try:
            if ACTIONS_FILE.exists():
                with open(ACTIONS_FILE, 'r', encoding='utf-8') as f:
                    self.actions = json.load(f)
                logging.info(f"Loaded {len(self.actions)} actions from registry.")
            else:
                logging.warning("actions.json not found. Only internal commands available.")
        except Exception as e:
            logging.error(f"Failed to load actions: {e}")

    def ensure_dirs(self):
        for d in [COMPLETED_DIR, FAILED_DIR, LOGS_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    def wake_up_antigravity(self, message):
        """Injects a message into the active window (Thread-Safeish)."""
        logging.info(f"Triggering Wake-Up: '{message}'")
        
        # Escape single quotes for PowerShell
        # ' becomes '' in PowerShell string literals
        safe_message = message.replace("'", "''")
        
        # PowerShell script: Hybrid Focus Strategy
        # 1. Check if the Active Window is the Monitor/Watchdog.
        # 2. If YES: Push it to back (%{ESC}) to reveal the previous window (Chat).
        # 3. If NO: Assume we are already in the right place (or background), just type.
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms

$code = @"
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);
"@
Add-Type -MemberDefinition $code -Name Win32 -Namespace Native

$hwnd = [Native.Win32]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 256
[Native.Win32]::GetWindowText($hwnd, $sb, 256)
$title = $sb.ToString()

# If we (the python script) are holding focus, get out of the way!
if ($title -match "Watchdog" -or $title -match "python" -or $title -match "Antigravity") {{
        # Alt+Esc pushes current window to bottom
        [System.Windows.Forms.SendKeys]::SendWait('%{{ESC}}')
        Start-Sleep -Milliseconds 500
}}

[System.Windows.Forms.SendKeys]::SendWait('{safe_message}')
[System.Windows.Forms.SendKeys]::SendWait('{{ENTER}}')
"""
        try:
            subprocess.run(["powershell", "-Command", ps_script], check=True)
            logging.info("Wake-up signal sent.")
        except Exception as e:
            logging.error(f"Wake-up failed: {e}")

    def run_task(self, task_name, command, result_file_path):
        """Executes the task in a separate thread."""
        try:
            logging.info(f"Starting execution: {command}")
            
            # Execute
            start_time = time.time()
            result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=WORKSPACE_DIR)
            duration = time.time() - start_time
            
            # Log Result
            with open(result_file_path, 'w', encoding='utf-8') as rf:
                rf.write(f"# Result: {task_name}\n\n")
                rf.write(f"**Command:** `{command}`\n")
                rf.write(f"**Duration:** {duration:.2f}s\n")
                rf.write(f"**Exit Code:** {result.returncode}\n\n")
                rf.write("## Output\n```text\n")
                rf.write(result.stdout)
                rf.write("\n```\n")
                if result.stderr:
                    rf.write("## Errors\n```text\n")
                    rf.write(result.stderr)
                    rf.write("\n```\n")

            logging.info(f"Finished {task_name} (Exit: {result.returncode})")
            
            # Wake up IS allowed from threads
            # Wake up logic: Efficient but Essential
            essential_keywords = ["INPUT REQUIRED", "ACTION NEEDED", "PLEASE SIGN", "AUTHENTICATION PENDING"]
            action_needed = any(kw in result.stdout.upper() for kw in essential_keywords)

            if result.returncode == 0:
                if action_needed:
                    self.wake_up_antigravity(f"Monitor: Task '{task_name}' succeeded, but ACTION IS REQUIRED. Check logs.")
                else:
                    # Silent success
                    pass 
            else:
                self.wake_up_antigravity(f"Monitor: Task '{task_name}' FAILED (Code {result.returncode}). Check logs.")

        except Exception as e:
            logging.error(f"Thread execution failed: {e}")

    def process_file(self, task_file):
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            command_to_run = None
            task_name = task_file.stem

            # Parse Lines
            lines = content.splitlines()
            for line in lines:
                line = line.strip()
                if not line: continue
                
                command_to_run = None
                action_key = None

                if line.startswith("RUN:"):
                    action_key = line.replace("RUN:", "").strip()
                    if action_key in self.actions:
                        command_to_run = self.actions[action_key]
                    else:
                        logging.warning(f"Action '{action_key}' not in whitelist.")
                        with open(INBOX_DIR / f"{task_name}_ERROR.md", 'a') as f:
                            f.write(f"Error: Action '{action_key}' is not in actions.json whitelist.\n")
                
                elif line.startswith("EXEC:"):
                     logging.warning("EXEC: command ignored by V2 Security Protocol.")

                if command_to_run:
                    # Spawn Thread for EACH command found
                    # Use a unique suffix if multiple commands exist? 
                    # Actually, run_task writes to {task_name}_RESULT.md. 
                    # If multiple run, they overwrite each other race-condition style.
                    # Fix: Append timestamp or index to result file.
                    
                    import uuid
                    unique_id = str(uuid.uuid4())[:8]
                    result_path = INBOX_DIR / f"{task_name}_{action_key}_{unique_id}_RESULT.md"
                    
                    t = threading.Thread(target=self.run_task, args=(f"{task_name}:{action_key}", command_to_run, result_path))
                    t.start()
                    logging.info(f"Spawning thread for: {action_key}")
                    
                    # Small delay to ensure launch order (e.g. server before client)
                    time.sleep(1.0)
            
            # Move to Completed after processing ALL lines
            try:
                logging.info(f"Moving {task_file} to completed.")
                shutil.move(str(task_file), str(COMPLETED_DIR / task_file.name))
            except Exception as move_err:
                logging.error(f"Failed to move {task_file}: {move_err}")

        except Exception as e:
            logging.error(f"Failed to process file {task_file}: {e}")
            try:
                shutil.move(str(task_file), str(FAILED_DIR / task_file.name))
            except:
                pass

    def run(self):
        logging.info("Antigravity Monitor V2 (Async) Started.")
        logging.info(f"Watching {INBOX_DIR}")
        
        try:
            while True:
                # Reload actions periodically (optional, but good for dev)
                # self.load_actions() 
                
                tasks = list(INBOX_DIR.glob("*.md")) + list(INBOX_DIR.glob("*.txt"))
                for task in tasks:
                    if "_RESULT" in task.name or "_ERROR" in task.name:
                        continue
                    self.process_file(task)
                
                time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            logging.info("Stopping Monitor.")

if __name__ == "__main__":
    app = AntigravityMonitor()
    app.run()
