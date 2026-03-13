#!/bin/bash
# Auto-Clipper - Quick Launcher

echo ""
echo "  Starting Auto-Clipper..."
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "  Not installed yet! Run install.sh first:"
    echo "    chmod +x install.sh"
    echo "    ./install.sh"
    exit 1
fi

# Activate and run
source venv/bin/activate

# Open browser quickly — the web UI shows a loading screen
# that waits for the backend to fully respond before showing content
(sleep 1 && open http://localhost:8080 2>/dev/null || xdg-open http://localhost:8080 2>/dev/null) &

python app.py
