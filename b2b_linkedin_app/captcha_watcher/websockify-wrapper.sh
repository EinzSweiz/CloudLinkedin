#!/bin/bash

WEBSOCKIFY_PID_FILE="/tmp/websockify.pid"
WEBSOCKIFY_PORT=6080
VNC_PORT=5900

LOCK_FILE="/tmp/websockify.lock"
exec 200>$LOCK_FILE
flock -n 200 || {
    echo "❌ Another instance is already running, exiting."
    exit 1
}
cleanup() {
    echo "🧹 Cleaning up websockify processes..."
    if [ -f "$WEBSOCKIFY_PID_FILE" ]; then
        PID=$(cat "$WEBSOCKIFY_PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Killing websockify process $PID"
            kill -TERM "$PID" 2>/dev/null || kill -KILL "$PID" 2>/dev/null
        fi
        rm -f "$WEBSOCKIFY_PID_FILE"
    fi
    
    # Kill any remaining websockify processes on our port
    pkill -f "websockify.*${WEBSOCKIFY_PORT}" 2>/dev/null || true
    
    # Wait a moment for cleanup
    sleep 2
}

check_port() {
    if netstat -ln | grep ":${WEBSOCKIFY_PORT} " > /dev/null 2>&1; then
        echo "❌ Port ${WEBSOCKIFY_PORT} is already in use"
        return 1
    fi
    return 0
}

wait_for_vnc() {
    echo "⏳ Waiting for VNC server on port ${VNC_PORT}..."
    for i in {1..30}; do
        if netstat -ln | grep ":${VNC_PORT} " > /dev/null 2>&1; then
            echo "✅ VNC server is ready on port ${VNC_PORT}"
            return 0
        fi
        echo "Waiting... ($i/30)"
        sleep 1
    done
    echo "❌ VNC server is not ready after 30 seconds"
    return 1
}

start_websockify() {
    echo "🚀 Starting websockify on port ${WEBSOCKIFY_PORT}..."
    
    # Start websockify in background and capture PID
    /opt/novnc/utils/websockify/websockify.py \
        --web /opt/novnc \
        --heartbeat=30 \
        --timeout=60 \
        --idle-timeout=60 \
        --wrap-mode=ignore \
        ${WEBSOCKIFY_PORT} \
        127.0.0.1:${VNC_PORT} &
    
    WEBSOCKIFY_PID=$!
    echo $WEBSOCKIFY_PID > "$WEBSOCKIFY_PID_FILE"
    
    echo "✅ Websockify started with PID: $WEBSOCKIFY_PID"
    
    # Wait a moment to see if it starts successfully
    sleep 3
    
    if ! ps -p "$WEBSOCKIFY_PID" > /dev/null 2>&1; then
        echo "❌ Websockify failed to start"
        rm -f "$WEBSOCKIFY_PID_FILE"
        return 1
    fi
    
    echo "✅ Websockify is running successfully"
    return 0
}

# Trap signals for cleanup
trap cleanup EXIT INT TERM

# Main execution
echo "🔍 Checking for existing websockify processes..."
cleanup

if ! wait_for_vnc; then
    echo "❌ Cannot start websockify without VNC server"
    exit 1
fi

if ! check_port; then
    echo "❌ Port conflict detected"
    cleanup
    exit 1
fi

if ! start_websockify; then
    echo "❌ Failed to start websockify"
    exit 1
fi

# Monitor the process
echo "👁️ Monitoring websockify process..."
while true; do
    if [ -f "$WEBSOCKIFY_PID_FILE" ]; then
        PID=$(cat "$WEBSOCKIFY_PID_FILE")
        if ! ps -p "$PID" > /dev/null 2>&1; then
            echo "❌ Websockify process died, exiting..."
            break
        fi
    else
        echo "❌ PID file missing, exiting..."
        break
    fi
    sleep 10
done

echo "👋 Websockify wrapper exiting"
cleanup