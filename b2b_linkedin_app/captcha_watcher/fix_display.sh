#!/bin/bash

# Simple display fix script - ADD TO YOUR EXISTING PROJECT
# File: captcha_watcher/fix_display.sh

echo "🔧 VNC Display Fix - Solving visual content issues"
echo "=================================================="

export DISPLAY=:0
export XAUTHORITY=/tmp/.Xauthority

echo "Step 1: Restarting X11 services..."
supervisorctl stop captcha_watcher 2>/dev/null || true
supervisorctl stop novnc 2>/dev/null || true
supervisorctl stop x11vnc 2>/dev/null || true
supervisorctl stop fluxbox 2>/dev/null || true

# Kill any hanging processes
pkill -f chrome 2>/dev/null || true
pkill -f x11vnc 2>/dev/null || true
pkill -f fluxbox 2>/dev/null || true

sleep 3

echo "Step 2: Checking Xvfb..."
if ! pgrep -f "Xvfb.*:0" >/dev/null; then
    echo "Restarting Xvfb..."
    supervisorctl start Xvfb
    sleep 5
fi

echo "Step 3: Setting up X11 auth..."
touch /tmp/.Xauthority
chmod 600 /tmp/.Xauthority

echo "Step 4: Testing X11 connection..."
if ! DISPLAY=:0 xdpyinfo >/dev/null 2>&1; then
    echo "X11 still not working, manual restart..."
    pkill Xvfb 2>/dev/null || true
    sleep 2
    Xvfb :0 -screen 0 1280x800x24 -ac -extension GLX +render -noreset &
    sleep 5
fi

echo "Step 5: Starting window manager..."
supervisorctl start fluxbox
sleep 3

echo "Step 6: Creating visible test applications..."
# Create multiple test windows to ensure something is visible
DISPLAY=:0 xterm -geometry 80x24+50+50 -title "VNC Test 1 - $(date)" -e "echo 'VNC Display is working!'; echo 'This confirms visual content transmission'; echo 'You can close this window'; sleep 300" &

DISPLAY=:0 xterm -geometry 80x24+300+100 -title "VNC Test 2 - Background Task" -e "while true; do echo 'VNC alive at $(date)'; sleep 10; done" &

# Try to create a simple GUI if available
if command -v xclock >/dev/null 2>&1; then
    DISPLAY=:0 xclock -geometry 150x150+500+50 &
fi

echo "Step 7: Restarting VNC server..."
supervisorctl start x11vnc
sleep 5

echo "Step 8: Restarting WebSocket..."
supervisorctl start novnc
sleep 3

echo "✅ Fix complete! Check these:"
echo "1. VNC client: vncviewer localhost:5900"
echo "2. Web VNC: http://localhost:6080/vnc.html" 
echo "3. You should see test windows and a desktop"

echo -e "\nIf you still see black screen:"
echo "- The issue is likely in Docker port mapping or network"
echo "- Check: docker ps (ports should show 5900:5900 and 6080:6080)"
echo "- Check: docker logs container_name"