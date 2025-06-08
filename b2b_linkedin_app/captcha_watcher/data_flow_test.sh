#!/bin/bash

# VNC Data Flow Test Script
# This script tests if data is actually flowing from X11 -> VNC -> WebSocket

echo "🌊 VNC Data Flow Test"
echo "===================="

export DISPLAY=:0
export XAUTHORITY=/tmp/.Xauthority

# Function to test data flow
test_data_flow() {
    echo "Starting comprehensive data flow test..."
    
    # 1. Stop current services
    echo "1. Stopping services for clean test..."
    supervisorctl stop novnc x11vnc chrome test-window 2>/dev/null || true
    sleep 3
    
    # 2. Start X11vnc with maximum verbosity
    echo "2. Starting x11vnc with verbose logging..."
    /usr/bin/x11vnc \
        -display :0 \
        -auth /tmp/.Xauthority \
        -rfbport 5900 \
        -forever \
        -shared \
        -nopw \
        -listen 0.0.0.0 \
        -verbose \
        -logfile /tmp/x11vnc_test.log \
        -bg
    
    sleep 3
    
    # 3. Create animated content
    echo "3. Creating animated content to generate data..."
    DISPLAY=:0 xterm -geometry 80x24+100+100 -title "Data Flow Test" -e "
        while true; do
            echo '████████████████████████████████████████'
            echo '█ VNC DATA FLOW TEST - $(date +%H:%M:%S) █'
            echo '█ Random: $RANDOM                        █'  
            echo '█ Counter: $((++counter))                 █'
            echo '████████████████████████████████████████'
            echo
            echo 'This content should appear in VNC viewer'
            echo 'and update every second.'
            echo
            sleep 1
            clear
        done
    " &
    XTERM_PID=$!
    
    sleep 5
    
    # 4. Check if VNC is capturing updates
    echo "4. Checking VNC data capture..."
    if [ -f "/tmp/x11vnc_test.log" ]; then
        echo "VNC log exists. Checking for framebuffer activity:"
        grep -i "update\|rect\|fb" /tmp/x11vnc_test.log | tail -5
        
        echo -e "\nChecking for client connections:"
        grep -i "client\|connect" /tmp/x11vnc_test.log | tail -3
    else
        echo "❌ VNC log file not created"
    fi
    
    # 5. Test direct VNC connection
    echo -e "\n5. Testing direct VNC protocol..."
    timeout 5 bash -c '
        echo "Connecting to VNC port 5900..."
        (
            echo "RFB 003.008"
            sleep 1
            echo -e "\x01"  # Shared flag
            sleep 2
        ) | nc localhost 5900 | xxd | head -5
    ' || echo "Direct VNC connection failed"
    
    # 6. Start websockify with verbose logging
    echo -e "\n6. Starting websockify with maximum verbosity..."
    pkill -f websockify 2>/dev/null || true
    sleep 2
    
    python3 -m websockify \
        --verbose \
        --web /opt/novnc \
        --log-file=/tmp/websockify_test.log \
        6080 localhost:5900 &
    WEBSOCKIFY_PID=$!
    
    sleep 5
    
    # 7. Test websocket connection
    echo "7. Testing WebSocket upgrade..."
    curl -v \
        -H "Connection: Upgrade" \
        -H "Upgrade: websocket" \
        -H "Sec-WebSocket-Version: 13" \
        -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
        "http://localhost:6080/websockify" 2>&1 | head -15
    
    # 8. Monitor data flow for 30 seconds
    echo -e "\n8. Monitoring data flow for 30 seconds..."
    echo "Check your VNC client now: http://localhost:6080/vnc.html"
    echo "You should see the animated terminal with updating content."
    
    for i in {1..30}; do
        echo -n "."
        sleep 1
    done
    echo
    
    # 9. Check logs for data activity
    echo -e "\n9. Analyzing logs for data activity..."
    
    if [ -f "/tmp/x11vnc_test.log" ]; then
        echo "X11VNC activity (last 10 lines):"
        tail -10 /tmp/x11vnc_test.log
    fi
    
    echo
    if [ -f "/tmp/websockify_test.log" ]; then
        echo "Websockify activity (last 10 lines):"
        tail -10 /tmp/websockify_test.log
    fi
    
    # 10. Cleanup
    echo -e "\n10. Cleaning up test..."
    kill $XTERM_PID 2>/dev/null || true
    kill $WEBSOCKIFY_PID 2>/dev/null || true
    pkill -f x11vnc 2>/dev/null || true
    
    echo -e "\n🎯 TEST RESULTS:"
    echo "==============="
    
    if grep -q "update" /tmp/x11vnc_test.log 2>/dev/null; then
        echo "✅ X11VNC is capturing screen updates"
    else
        echo "❌ X11VNC is NOT capturing screen updates"
        echo "   This means the issue is between X11 and VNC"
    fi
    
    if grep -q "websocket" /tmp/websockify_test.log 2>/dev/null; then
        echo "✅ WebSocket connections are being established"
    else
        echo "❌ WebSocket connections are failing"
        echo "   This means the issue is in websockify"
    fi
    
    echo -e "\nRestarting normal services..."
    supervisorctl start x11vnc novnc
}

# Function to apply immediate fix
apply_immediate_fix() {
    echo "🔧 Applying immediate data flow fix..."
    
    # Stop all VNC-related services
    supervisorctl stop novnc x11vnc
    sleep 3
    
    # Kill any remaining processes
    pkill -f websockify 2>/dev/null || true
    pkill -f x11vnc 2>/dev/null || true
    sleep 2
    
    echo "Starting x11vnc with optimized settings for data flow..."
    
    # Start x11vnc with settings optimized for data transmission
    /usr/bin/x11vnc \
        -display :0 \
        -auth /tmp/.Xauthority \
        -rfbport 5900 \
        -forever \
        -shared \
        -nopw \
        -listen 0.0.0.0 \
        -threads \
        -noclipboard \
        -nobell \
        -noxdamage \
        -noxfixes \
        -wait 10 \
        -defer 10 \
        -bg \
        -logfile /tmp/x11vnc_optimized.log
    
    sleep 3
    
    echo "Starting websockify with optimized settings..."
    
    # Start websockify with better buffering
    python3 -m websockify \
        --heartbeat=10 \
        --timeout=0 \
        --web /opt/novnc \
        --log-file=/tmp/websockify_optimized.log \
        6080 localhost:5900 &
    
    sleep 3
    
    echo "✅ Services restarted with optimized settings"
    echo "Test your connection now: http://localhost:6080/vnc.html"
}

# Main menu
case "${1:-test}" in
    "test")
        test_data_flow
        ;;
    "fix")
        apply_immediate_fix
        ;;
    "restart")
        echo "🔄 Restarting all VNC services..."
        supervisorctl restart Xvfb fluxbox x11vnc novnc
        ;;
    *)
        echo "Usage: $0 [test|fix|restart]"
        echo "  test    - Run comprehensive data flow test"
        echo "  fix     - Apply immediate data flow fix"
        echo "  restart - Restart all VNC services"
        ;;
esac