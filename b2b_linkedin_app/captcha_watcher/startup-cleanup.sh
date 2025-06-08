#!/bin/bash

# Startup cleanup script to ensure clean environment
# Add this to your Dockerfile or run it before starting supervisor

LOG_PREFIX="[STARTUP-CLEANUP]"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $LOG_PREFIX $1"
}

log "🧹 Starting system cleanup..."


# Kill any existing websockify, x11vnc, chrome, and Xvfb processes
for proc in websockify x11vnc chrome Xvfb fluxbox; do
    log "Killing existing $proc processes..."
    pkill -f $proc 2>/dev/null || true
done

# Kill processes using ports 5900 and 6080
for port in 5900 6080; do
    log "Freeing port $port..."
    fuser -k $port/tcp 2>/dev/null || true
    
    # Wait for port to be freed
    count=0
    while [ $count -lt 10 ] && netstat -ln 2>/dev/null | grep ":$port " >/dev/null; do
        sleep 1
        count=$((count+1))
    done
    
    if netstat -ln 2>/dev/null | grep ":$port " >/dev/null; then
        log "⚠️ Port $port still in use after cleanup"
    else
        log "✅ Port $port is free"
    fi
done

# Remove lock and PID files
log "Removing lock and PID files..."
rm -f /tmp/websockify.lock
rm -f /tmp/websockify.pid
rm -f /tmp/websockify.log

# Clean up any stale X11 locks
log "Cleaning X11 locks..."
rm -f /tmp/.X*-lock 2>/dev/null || true

# Ensure directories exist
log "Creating required directories..."
mkdir -p /tmp/runtime-root
mkdir -p /var/log/supervisor
mkdir -p /var/run/dbus
chmod 700 /tmp/runtime-root

log "Startup cleanup completed"