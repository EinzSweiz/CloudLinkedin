#!/bin/bash

# Test VNC from outside Docker - RUN THIS ON YOUR HOST MACHINE
# File: captcha_watcher/test_vnc_outside.sh

echo "🔍 Testing VNC Access from Outside Docker"
echo "=========================================="

DOCKER_IP="localhost"  # Change this if Docker is on different IP
VNC_PORT="5900"
WEB_PORT="6080"

echo "1. Testing Docker container ports..."
echo "Checking if ports are exposed:"
docker ps | grep -E "(5900|6080)" || echo "❌ Ports not visible in docker ps"

echo -e "\n2. Testing network connectivity..."
if command -v nc >/dev/null 2>&1; then
    echo "VNC port 5900: $(nc -z $DOCKER_IP $VNC_PORT && echo 'REACHABLE' || echo 'NOT REACHABLE')"
    echo "Web port 6080: $(nc -z $DOCKER_IP $WEB_PORT && echo 'REACHABLE' || echo 'NOT REACHABLE')"
else
    echo "netcat not available, using telnet test..."
    timeout 3 telnet $DOCKER_IP $VNC_PORT 2>/dev/null && echo "VNC port reachable" || echo "VNC port NOT reachable"
fi

echo -e "\n3. Testing HTTP endpoint..."
if command -v curl >/dev/null 2>&1; then
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://$DOCKER_IP:$WEB_PORT/ 2>/dev/null)
    echo "HTTP status: $HTTP_STATUS"
    if [ "$HTTP_STATUS" = "200" ]; then
        echo "✅ WebSocket server is responding"
        echo "Try: http://$DOCKER_IP:$WEB_PORT/vnc.html"
    else
        echo "❌ WebSocket server not responding properly"
    fi
else
    echo "curl not available for HTTP testing"
fi

echo -e "\n4. Testing VNC viewer connection..."
if command -v vncviewer >/dev/null 2>&1; then
    echo "Attempting VNC connection (will timeout in 10 seconds)..."
    timeout 10 vncviewer -ViewOnly $DOCKER_IP:$VNC_PORT &
    VNC_PID=$!
    sleep 3
    if ps -p $VNC_PID >/dev/null 2>&1; then
        echo "✅ VNC viewer connected successfully"
        kill $VNC_PID 2>/dev/null
    else
        echo "❌ VNC viewer failed to connect"
    fi
else
    echo "vncviewer not available"
    echo "Install with: apt-get install tigervnc-viewer"
fi

echo -e "\n5. Docker diagnostics..."
echo "Running containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo -e "\nContainer logs (last 10 lines):"
CONTAINER_NAME=$(docker ps --format "{{.Names}}" | head -1)
if [ -n "$CONTAINER_NAME" ]; then
    docker logs --tail 10 $CONTAINER_NAME
else
    echo "No containers found"
fi

echo -e "\n🎯 TROUBLESHOOTING GUIDE:"
echo "If VNC connects but shows black screen:"
echo "  - Run inside container: docker exec -it CONTAINER_NAME /app/captcha_watcher/debug_display.sh"
echo "  - Run inside container: docker exec -it CONTAINER_NAME /app/captcha_watcher/fix_display.sh"
echo ""
echo "If VNC doesn't connect at all:"
echo "  - Check Docker run command includes: -p 5900:5900 -p 6080:6080"
echo "  - Check firewall: sudo ufw allow 5900 && sudo ufw allow 6080"
echo "  - Check Docker logs: docker logs CONTAINER_NAME"