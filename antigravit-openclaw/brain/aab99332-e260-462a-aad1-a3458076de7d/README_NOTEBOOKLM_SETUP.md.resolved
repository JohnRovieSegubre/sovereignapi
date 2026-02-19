# NotebookLM Agent Setup Guide

This kit allows any Antigravity agent to connect to NotebookLM.

## 1. Installation
Unzip `notebooklm_kit.zip` into your agent's workspace.
Ensure the folder `general-notebooklm` is placed inside `.agent/skills/`.

## 2. Authentication (One-time Setup)
Run this command to log in:
```bash
python .agent/skills/general-notebooklm/scripts/run.py auth_manager.py setup
```
*   A Chrome window will open.
*   Log in to your Google Account.
*   Wait for the window to close automatically.

## 3. Registering Notebooks
Tell the agent:
> "Add this notebook: [PASTE_URL]"

Or run manually:
```bash
python .agent/skills/general-notebooklm/scripts/run.py notebook_manager.py add --url "YOUR_NOTEBOOK_URL" --name "Project 1" --description "My project docs" --topics "research"
```

## 4. Usage
Just tell the agent:
> "Check Project 1 and summarize the character backstories."
