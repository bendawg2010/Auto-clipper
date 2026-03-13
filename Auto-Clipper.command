#!/bin/bash
# ============================================================
#  Auto-Clipper — Double-click to install & run
#  Works on Mac. Just double-click this file from Finder.
# ============================================================

# cd into the folder this script lives in (handles any download location)
cd "$(dirname "$0")"

clear
echo ""
echo "  ╔════════════════════════════════════════════╗"
echo "  ║          Auto-Clipper                      ║"
echo "  ╚════════════════════════════════════════════╝"
echo ""

# ---------- Already installed? Just launch ----------
if [ -d "venv" ] && [ -f "venv/bin/python" ]; then
    echo "  Already installed! Starting..."
    echo ""
    source venv/bin/activate

    # Open browser after short delay
    (sleep 2 && open http://localhost:8080 2>/dev/null) &

    python app.py
    exit 0
fi

# ---------- First time: install everything ----------
echo "  First time setup — this takes a few minutes."
echo "  (You may need to enter your Mac password)"
echo ""

# 1. Homebrew
echo "[1/4] Homebrew..."
if ! command -v brew &> /dev/null; then
    echo "  Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add brew to PATH
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile 2>/dev/null
    elif [ -f /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi

    if ! command -v brew &> /dev/null; then
        echo ""
        echo "  Homebrew needs a Terminal restart."
        echo "  Close this window and double-click Auto-Clipper.command again."
        echo ""
        read -p "  Press Enter to close..."
        exit 1
    fi
fi
echo "  OK"

# 2. Python, Git, FFmpeg
echo "[2/4] Python, Git, FFmpeg..."
brew install python git ffmpeg 2>/dev/null

MISSING=""
command -v python3 &> /dev/null || MISSING="$MISSING python3"
command -v ffmpeg &> /dev/null || MISSING="$MISSING ffmpeg"

if [ -n "$MISSING" ]; then
    echo ""
    echo "  ERROR: Could not install:$MISSING"
    echo "  Try: brew install python ffmpeg"
    read -p "  Press Enter to close..."
    exit 1
fi
echo "  OK"

# 3. Python virtual environment
echo "[3/4] Python environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "  Failed to create Python environment."
    read -p "  Press Enter to close..."
    exit 1
fi
echo "  OK"

# 4. Dependencies
echo "[4/4] Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo "  Failed to install dependencies."
    read -p "  Press Enter to close..."
    exit 1
fi
echo "  OK"

# ---------- Done! Launch the app ----------
echo ""
echo "  ============================================"
echo "    Installation complete! Starting app..."
echo "  ============================================"
echo ""
echo "  Next time just double-click Auto-Clipper.command again."
echo ""

# Start server in background
python app.py &
SERVER_PID=$!

# Wait for server to bind the port before opening browser
echo "  Waiting for server..."
for i in $(seq 1 60); do
    if (echo > /dev/tcp/localhost/8080) 2>/dev/null || curl -s http://localhost:8080/ > /dev/null 2>&1; then
        echo "  Server ready!"
        open http://localhost:8080
        break
    fi
    sleep 1
done

wait $SERVER_PID
