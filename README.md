# Antigravity Always-On Monitor 🌌

A background daemon for AI Agents that enables 24/7 operation and "Wake-on-Complete" capabilities.

## Features
*   **Persistent Monitor:** A Python script that watches a file-based inbox (`.agent/inbox/`) 24/7.
*   **Moltbook Integration:** Social media automation for AI agents (posting, verifying, checking feed).
*   **Wake-on-Complete:** Uses `SendKeys` (Alt-Tab + Type) to verify task completion by typing directly into the active chat window, waking up the AI model.

## Setup
1.  **Start:** Run `START_MONITOR.bat` (Windows).
2.  **Tasking:** Drop text files into `.agent/inbox/`.
    *   Example: `EXEC: python post_and_verify_moltbook.py`
3.  **Auto-Wake:** Ensure your chat window is the "Previous Window" (Alt-Tab away from the Monitor) so the agent can type back to you.

## Component Scripts
*   `scripts/antigravity_monitor.py`: The core daemon.
*   `post_and_verify_moltbook.py`: Handles API posts + Math Challenge verification.
*   `check_moltbook_status.py`: Verifies agent status.

## Security
Credentials are stored in `.agent/secure/` (Gitignored).
