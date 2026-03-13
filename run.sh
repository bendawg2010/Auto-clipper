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

# Start server in background
python app.py &
SERVER_PID=$!

# Wait for server to actually bind the port before opening browser
echo "  Waiting for server..."
for i in $(seq 1 30); do
    if (echo > /dev/tcp/localhost/8080) 2>/dev/null || curl -s http://localhost:8080/ > /dev/null 2>&1; then
        echo "  Server ready!"
        open http://localhost:8080 2>/dev/null || xdg-open http://localhost:8080 2>/dev/null
        break
    fi
    sleep 1
done

wait $SERVER_PID
