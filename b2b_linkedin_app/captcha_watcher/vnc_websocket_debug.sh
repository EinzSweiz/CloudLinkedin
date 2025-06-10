#!/bin/bash

# VNC WebSocket Data Flow Diagnostic

echo "VNC WebSocket Data Flow Analysis"
echo "===================================="

export DISPLAY=:0
export XAUTHORITY=/tmp/.Xauthority

echo "1. Testing x11vnc data output..."
echo "Checking if x11vnc is actually capturing screen data:"

# Test x11vnc data capture
echo "Creating test movement on screen..."
DISPLAY=:0 xterm -geometry 80x24+100+100 -title "Data Flow Test $(date)" &
TEST_PID=$!
sleep 2

echo "Moving window to generate VNC traffic..."
DISPLAY=:0 wmctrl -r "Data Flow Test" -e 0,200,200,640,480 2>/dev/null || echo "wmctrl not available"

echo -e "\n2. Checking x11vnc output buffer..."
if [ -f "/tmp/x11vnc_full.log" ]; then
    echo "Last 10 lines of x11vnc debug log:"
    tail -10 /tmp/x11vnc_full.log
    
    echo -e "\nSearching for framebuffer updates in log:"
    grep -i "framebuffer\|update\|rect\|damage" /tmp/x11vnc_full.log | tail -5
else
    echo "x11vnc debug log not found at /tmp/x11vnc_full.log"
fi

echo -e "\n3. Testing direct VNC connection..."
echo "Testing if VNC data flows when connecting directly (not through websocket):"

# Kill test window
kill $TEST_PID 2>/dev/null || true

# Try connecting to VNC directly and see if we get data
timeout 10 bash -c '
    echo "Attempting direct VNC connection test..."
    echo "Trying to read VNC protocol handshake..."
    (echo "RFB 003.008"; sleep 1) | nc localhost 5900 | head -c 50 | xxd
' 2>/dev/null || echo "Direct VNC test failed"

echo -e "\n4. WebSocket connection analysis..."
echo "Testing websocket data flow:"

# Check if websockify is properly bridging
ps aux | grep websockify | grep -v grep | while read line; do
    echo "Websockify process: $line"
done

echo -e "\nTesting websocket with curl:"
timeout 5 curl -v \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  "http://localhost:6080/websockify" 2>&1 | head -20

echo -e "\n5. Advanced VNC data flow test..."
echo "Creating active screen content and monitoring VNC data..."

# Create continuously updating content
DISPLAY=:0 xterm -geometry 80x24+50+50 -title "VNC Data Generator" -e "
while true; do 
    echo 'VNC Test - $(date)'
    echo 'Line 1: $(date +%s)'
    echo 'Line 2: Random: $RANDOM'
    echo 'Line 3: Moving content...'
    sleep 1
    clear
done" &
CONTENT_PID=$!

sleep 3

echo "Monitoring VNC port for data activity..."
timeout 10 bash -c '
    echo "Checking if data is flowing on VNC port 5900..."
    netstat -i | head -3
    echo "Network activity before:"
    cat /proc/net/dev | grep lo
    
    sleep 5
    
    echo "Network activity after:"
    cat /proc/net/dev | grep lo
'

kill $CONTENT_PID 2>/dev/null || true

echo -e "\n6. X11 framebuffer inspection..."
echo "Checking if X11 display is actually updating:"

if command -v xwininfo >/dev/null 2>&1; then
    echo "Active windows:"
    DISPLAY=:0 xwininfo -root -children | head -10
else
    echo "Installing xwininfo for window inspection..."
    apt-get update && apt-get install -y x11-utils
fi

echo -e "\n7. VNC server configuration analysis..."
echo "Current x11vnc parameters analysis:"

ps aux | grep x11vnc | grep -v grep | while read line; do
    echo "Command: $line"
    
    # Check for problematic flags
    if echo "$line" | grep -q "\-noxdamage"; then
        echo "Using -noxdamage (good for debugging)"
    fi
    
    if echo "$line" | grep -q "\-noxfixes"; then
        echo "Using -noxfixes (good for debugging)"  
    fi
    
    if echo "$line" | grep -q "\-solid"; then
        echo "Using -solid background (may reduce updates)"
    fi
done

echo -e "\n DIAGNOSIS RESULTS:"
echo "====================="

# Test if the issue is in the websocket bridge
if netstat -ln | grep ":5900 " >/dev/null && netstat -ln | grep ":6080 " >/dev/null; then
    echo "Both VNC (5900) and WebSocket (6080) ports are bound"
    
    # The issue is likely in the data bridge
    echo "LIKELY ISSUE: Data bridging between VNC and WebSocket"
    echo ""
    echo "IMMEDIATE FIXES TO TRY:"
    echo "1. Restart websockify with verbose logging:"
    echo "   supervisorctl stop novnc"
    echo "   /opt/novnc/utils/websockify/websockify.py --verbose --web /opt/novnc 6080 localhost:5900"
    echo ""
    echo "2. Try alternative websockify command:"
    echo "   python3 -m websockify --verbose --heartbeat=30 6080 localhost:5900"
    echo ""
    echo "3. Test with different x11vnc flags:"
    echo "   Remove -solid black and -noxdamage to see if data flows"
    
else
    echo "Port binding issue detected"
fi

echo -e "\n NEXT STEPS:"
echo "1. Run the immediate fixes above"
echo "2. Check websockify logs with: tail -f /var/log/supervisor/novnc.log"
echo "3. Try connecting with verbose VNC client to see raw data flow"