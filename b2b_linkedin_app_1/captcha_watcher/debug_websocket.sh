#!/bin/bash

# WebSocket Debug Script for VNC Connection
# Run this inside the container to diagnose websockify issues

echo "🔍 WebSocket/Websockify Debug Analysis"
echo "======================================"

# 1. Check if websockify is actually running and responding
echo "1. Checking websockify process..."
ps aux | grep websockify | grep -v grep

echo -e "\n2. Checking port bindings..."
netstat -tulpn | grep -E "(5900|6080)"

echo -e "\n3. Testing websockify HTTP endpoint..."
curl -v http://localhost:6080/ 2>&1 | head -20

echo -e "\n4. Testing websockify WebSocket upgrade..."
curl -v \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  http://localhost:6080/websockify 2>&1 | head -30

echo -e "\n5. Check websockify logs..."
if [ -f /tmp/websockify.log ]; then
    echo "Websockify log (last 20 lines):"
    tail -20 /tmp/websockify.log
else
    echo "No websockify log found at /tmp/websockify.log"
fi

echo -e "\n6. Check if websockify can reach VNC server..."
timeout 5 bash -c 'cat < /dev/null > /dev/tcp/127.0.0.1/5900' && echo "✅ VNC server reachable" || echo "❌ VNC server NOT reachable"

echo -e "\n7. Check websockify process arguments..."
ps aux | grep websockify | grep -v grep | while read line; do
    echo "Process: $line"
done

echo -e "\n8. Test manual websockify connection..."
echo "Manual test - starting websockify on different port..."
pkill -f websockify || true
sleep 2

echo "Starting websockify manually on port 6081..."
/opt/novnc/utils/websockify/websockify.py --web /opt/novnc 6081 127.0.0.1:5900 &
MANUAL_PID=$!
sleep 3

echo "Testing manual websockify..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:6081/
echo " (HTTP status for manual websockify)"

kill $MANUAL_PID 2>/dev/null || true

echo -e "\n9. Check noVNC files..."
ls -la /opt/novnc/ | head -10

echo -e "\n10. Test WebSocket with curl..."
echo "Testing WebSocket handshake:"
(echo -e "GET /websockify HTTP/1.1\r\nHost: localhost:6080\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n"; sleep 1) | nc localhost 6080

echo -e "\n🎯 ANALYSIS COMPLETE"
echo "================================"
echo "If you see 'Connection refused' or empty responses above,"
echo "the issue is websockify not properly starting or binding to port 6080."
echo ""
echo "If you see HTTP 200 responses but WebSocket upgrade fails,"
echo "the issue is in the WebSocket protocol handling."
echo ""
echo "Next steps based on findings above:"
echo "1. If websockify not running: Check supervisord config"
echo "2. If port not bound: Check for port conflicts"  
echo "3. If WebSocket fails: Check websockify version/compatibility"