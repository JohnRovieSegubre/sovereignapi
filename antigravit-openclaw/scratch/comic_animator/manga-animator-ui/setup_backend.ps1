
# Setup Python Backend for Manga Animator UI

Write-Host "Setting up Python Backend Environment..."

$VENV_DIR = "venv"

# 1. Create venv if it doesn't exist
if (-not (Test-Path $VENV_DIR)) {
    Write-Host "Creating virtual environment..."
    python -m venv $VENV_DIR
}

# 2. Activate venv
$VENV_ACTIVATE = ".\$VENV_DIR\Scripts\Activate.ps1"
if (Test-Path $VENV_ACTIVATE) {
    . $VENV_ACTIVATE
} else {
    Write-Error "Could not find activation script at $VENV_ACTIVATE"
    exit 1
}

# 3. Install Requirements
# Ensure we have the base requirements plus any new ones
Write-Host "Installing dependencies..."
pip install --upgrade pip
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt
} else {
    Write-Warning "requirements.txt not found!"
}

# 4. Check MediaPipe
Write-Host "Verifying MediaPipe..."
python -c "import mediapipe; print('MediaPipe is ready.')"

Write-Host "Backend Setup Complete!"
