#!/bin/bash

# Simple display diagnostic script - ADD TO YOUR EXISTING PROJECT
# File: captcha_watcher/debug_display.sh

echo "🔍 VNC Display Debug - Checking what's blocking visual content"
echo "=============================================================="

# Set environment
export DISPLAY=:0
export XAUTHORITY=/tmp/.Xauthority

echo "1. Basic Process Check:"
echo "- Xvfb: $(pgrep -f 'Xvfb.*:0' >/dev/null && echo 'RUNNING' || echo 'NOT RUNNING')"
echo "- x11vnc: $(pgrep -f 'x11vnc.*5900' >/dev/null && echo 'RUNNING' || echo 'NOT RUNNING')"
echo "- fluxbox: $(pgrep -f 'fluxbox' >/dev/null && echo 'RUNNING' || echo 'NOT RUNNING')"

echo -e "\n2. X11 Display Test:"
if command -v xdpyinfo >/dev/null 2>&1; then
    if DISPLAY=:0 xdpyinfo >/dev/null 2>&1; then
        echo "✅ X11 display :0 is accessible"
        echo "Screen info: $(DISPLAY=:0 xdpyinfo | grep 'dimensions:' | awk '{print $2}')"
    else
        echo "❌ X11 display :0 NOT accessible - THIS IS THE PROBLEM!"
        echo "Fix: supervisorctl restart Xvfb"
    fi
else
    echo "⚠️ xdpyinfo not available - installing..."
    apt-get update && apt-get install -y x11-utils
fi

echo -e "\n3. What's Actually Running on Display:"
if command -v xlsclients >/dev/null 2>&1; then
    clients=$(DISPLAY=:0 xlsclients 2>/dev/null | wc -l)
    echo "Active X11 clients: $clients"
    if [ $clients -eq 0 ]; then
        echo "❌ NO APPLICATIONS RUNNING - This is why VNC shows black screen!"
        echo "Creating test window..."
        DISPLAY=:0 xterm -geometry 80x24+100+100 -title "VNC TEST - $(date)" &
        echo "✅ Test window created - check VNC now"
    else
        echo "✅ Applications are running:"
        DISPLAY=:0 xlsclients 2>/dev/null
    fi
else
    echo "Installing xlsclients..."
    apt-get update && apt-get install -y x11-utils
fi

echo -e "\n4. X11 Authentication Check:"
if [ -f "/tmp/.Xauthority" ]; then
    echo "✅ Xauthority file exists"
    ls -la /tmp/.Xauthority
else
    echo "❌ Xauthority missing - creating..."
    touch /tmp/.Xauthority
    chmod 600 /tmp/.Xauthority
fi

echo -e "\n5. VNC Server Details:"
if pgrep -f "x11vnc.*5900" >/dev/null; then
    echo "VNC command line:"
    ps aux | grep "x11vnc.*5900" | grep -v grep
    
    echo -e "\nVNC log (last 5 lines):"
    if [ -f "/var/log/supervisor/x11vnc.log" ]; then
        tail -5 /var/log/supervisor/x11vnc.log
    else
        echo "No VNC log found"
    fi
else
    echo "❌ x11vnc not running!"
fi

echo -e "\n6. Quick Fix Test:"
echo "Testing if we can create a visible window..."
DISPLAY=:0 xterm -geometry 80x24+200+200 -title "Debug Test $(date)" -e "echo 'If you see this in VNC, display is working!'; echo 'Window will stay open for 60 seconds'; sleep 60" &
TEST_PID=$!
echo "✅ Test window PID: $TEST_PID"
echo "🎯 Check your VNC client NOW - you should see a terminal window"
echo "   If you see it, the problem is that no applications are running by default"

echo -e "\n7. Port Check:"
echo "VNC port 5900: $(netstat -ln | grep ':5900 ' >/dev/null && echo 'BOUND' || echo 'NOT BOUND')"
echo "WebSocket port 6080: $(netstat -ln | grep ':6080 ' >/dev/null && echo 'BOUND' || echo 'NOT BOUND')"

echo -e "\n🔧 DIAGNOSIS COMPLETE"
echo "Most likely issues:"
echo "1. No applications running on X11 display (black screen)"
echo "2. Xvfb not properly started"
echo "3. X11 authentication problems"
echo ""
echo "Quick fixes to try:"
echo "- supervisorctl restart Xvfb"
echo "- supervisorctl restart fluxbox" 
echo "- Create test window: DISPLAY=:0 xterm &"