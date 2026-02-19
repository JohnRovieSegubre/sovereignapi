# Antigravity System Analysis & Improvement Plan

## 1. Safety & Security Audit 🛡️
**Current Status:** ⚠️ **High Risk**
*   **Issue:** The `EXEC:` command blindly passes strings to `subprocess.run(..., shell=True)`.
*   **Risk:** If a malicious file drops into `.agent/inbox` (e.g., `EXEC: del /s /q *`), the monitor will execute it without question.
*   **Recommendation:** Implement a **Command Whitelist** or a **Script Registry**.
    *   *Bad:* `EXEC: python script.py`
    *   *Good:* `RUN: moltbook_post` (maps to trusted `scripts/post.py`)

## 2. The "Wake-Up" Mechanism 💤
**Current Status:** 🛠️ **Fragile**
*   **Issue:** reliance on `Alt+Tab` and `SendKeys` works only if the user hasn't clicked around too much. It's a "Happy Path" solution.
*   **Risk:** If you are typing in Word when the monitor finishes, it might type "Task Complete" into your document instead of the chat.
*   **Recommendation:**
    *   **Toast Notifications:** Uses Windows native notifications (visible regardless of focus).
    *   **Sound Cues:** A specific "Task Done" sound.
    *   **Dedicated API:** Ideally, the Chat Agent would have a local server port we could `POST` to, avoiding UI simulation entirely.

## 3. Workflow & Scalability 📈
**Current Status:** 🛑 **Single Threaded**
*   **Issue:** `time.sleep(1800)` in a task file *blocks* the entire monitor for 30 minutes. No other files are processed during that wait.
*   **Risk:** Bottlenecks.
*   **Recommendation:**
    *   **Async Processing:** Verify verification logic shouldn't block the main loop.
    *   **Cron/Scheduler:** Instead of `sleep()`, the monitor should support `SCHEDULE: 2026-02-05T19:00:00`.

## 4. Code Quality & Maintenance 🧹
**Current Status:** 📝 **Script-based**
*   **Issue:** `antigravity_monitor.py` is becoming monolithic.
*   **Recommendation:** Refactor into classes (`InboxWatcher`, `TaskExecutor`, `AgentNotifier`).

---

## 🚀 Proposed "V2" Workflow
1.  **Tasking:** You drop a structured YAML file:
    ```yaml
    task: post_moltbook
    params:
      topic: "AI Economy"
    schedule: "now"
    ```
2.  **Processing:** Monitor sees it validation against strict schema.
3.  **Execution:** Runs in dedicated thread (non-blocking).
4.  **Feedback:**
    *   **Success:** Windows Notification + `_RESULT.md`.
    *   **Failure:** `_ERROR.log`.
