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

# Start server in background, wait for it to be ready, then open browser
python app.py &
SERVER_PID=$!

echo "  Waiting for server..."
for i in $(seq 1 60); do
    if curl -s http://localhost:8080/api/games > /dev/null 2>&1; then
        echo "  Server ready!"
        open http://localhost:8080 2>/dev/null || xdg-open http://localhost:8080 2>/dev/null
        break
    fi
    sleep 1
done

# Keep running until server exits
wait $SERVER_PID
