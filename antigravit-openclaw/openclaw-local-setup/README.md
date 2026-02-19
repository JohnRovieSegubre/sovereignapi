# OpenClaw Local Installer (Windows)

This installer automates the setup of a fully local, privacy-focused AI agent on your Windows machine.

It installs:
1.  **Ollama**: The engine to run AI models locally.
2.  **Qwen 2.5 (7B)**: A high-performance AI model optimized for coding and reasoning.
3.  **OpenClaw (Clawdbot)**: The AI agent interface.

## Prerequisites

*   **Windows 10 or 11**
*   **Administrator Privileges** (required to install software)
*   **~10GB Free Disk Space** (for the model and tools)
*   **Internet Connection**

## How to Install

1.  Right-click the `install.ps1` file.
2.  Select **"Run with PowerShell"**.
3.  Follow the on-screen prompts.
    *   You may be asked to approve administrative privileges.
    *   The script will download the AI model (~4.7 GB), which may take time depending on your internet speed.

## Post-Installation

Once the installation is complete:

1.  Open a new terminal (PowerShell or Command Prompt).
2.  Run the agent:
    ```powershell
    clawdbot start
    ```
3.  The agent will now be running locally, powered by your Qwen 2.5 model!

## Troubleshooting

*   **"Script is not digitally signed"**: If you see this error, run the following command in PowerShell as Administrator to allow script execution:
    ```powershell
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    ```
    Then try running the installer again.
