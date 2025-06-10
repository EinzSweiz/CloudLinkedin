#!/bin/bash

# Enhanced websockify wrapper with proper locking and cleanup
# Prevents multiple instances and ensures clean startup/shutdown

WEBSOCKIFY_PID_FILE="/tmp/websockify.pid"
WEBSOCKIFY_PORT=6080
VNC_PORT=5900
LOCK_FILE="/tmp/websockify.lock"
LOG_PREFIX="[WEBSOCKIFY]"

# Enhanced logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $LOG_PREFIX $1"
}

# Atomic lock acquisition with timeout
acquire_lock() {
    local timeout=30
    local count=0
    
    while [ $count -lt $timeout ]; do
        if (set -C; echo $$ > "$LOCK_FILE") 2>/dev/null; then
            log "Lock acquired successfully (PID: $$)"
            return 0
        fi
        
        # Check if lock holder is still alive
        if [ -f "$LOCK_FILE" ]; then
            local lock_pid=$(cat "$LOCK_FILE" 2>/dev/null)
            if [ -n "$lock_pid" ] && ! kill -0 "$lock_pid" 2>/dev/null; then
                log "Removing stale lock file (dead PID: $lock_pid)"
                rm -f "$LOCK_FILE"
                continue
            fi
        fi
        
        log "Waiting for lock... (attempt $((count+1))/$timeout)"
        sleep 1
        count=$((count+1))
    done
    
    log "Failed to acquire lock after ${timeout}s"
    return 1
}

# Release lock safely
release_lock() {
    if [ -f "$LOCK_FILE" ]; then
        local lock_pid=$(cat "$LOCK_FILE" 2>/dev/null)
        if [ "$lock_pid" = "$$" ]; then
            rm -f "$LOCK_FILE"
            log "Lock released"
        else
            log "Lock file PID mismatch: expected $$, found $lock_pid"
        fi
    fi
}

# Comprehensive cleanup function
cleanup() {
    log "Starting cleanup process..."
    
    # Kill our websockify process if running
    if [ -f "$WEBSOCKIFY_PID_FILE" ]; then
        local pid=$(cat "$WEBSOCKIFY_PID_FILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log "Stopping websockify process $pid"
            kill -TERM "$pid" 2>/dev/null
            
            # Wait for graceful shutdown
            local count=0
            while [ $count -lt 10 ] && kill -0 "$pid" 2>/dev/null; do
                sleep 1
                count=$((count+1))
            done
            
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                log "Force killing websockify process $pid"
                kill -KILL "$pid" 2>/dev/null
            fi
        fi
        rm -f "$WEBSOCKIFY_PID_FILE"
    fi
    
    # Kill ALL websockify processes on our port (nuclear option)
    log "Killing all websockify processes on port $WEBSOCKIFY_PORT"
    pkill -f "websockify.*${WEBSOCKIFY_PORT}" 2>/dev/null || true
    
    # Wait for port to be freed
    local count=0
    while [ $count -lt 10 ] && netstat -ln 2>/dev/null | grep ":${WEBSOCKIFY_PORT} " >/dev/null; do
        log "Waiting for port $WEBSOCKIFY_PORT to be freed..."
        sleep 1
        count=$((count+1))
    done
    
    # Force kill anything still using the port
    local port_pid=$(netstat -tulpn 2>/dev/null | grep ":${WEBSOCKIFY_PORT} " | awk '{print $7}' | cut -d'/' -f1)
    if [ -n "$port_pid" ] && [ "$port_pid" != "-" ]; then
        log "Force killing process $port_pid using port $WEBSOCKIFY_PORT"
        kill -KILL "$port_pid" 2>/dev/null || true
    fi
    
    release_lock
    log "Cleanup completed"
}

# Check if port is available
check_port_available() {
    if netstat -ln 2>/dev/null | grep ":${WEBSOCKIFY_PORT} " >/dev/null; then
        local port_pid=$(netstat -tulpn 2>/dev/null | grep ":${WEBSOCKIFY_PORT} " | awk '{print $7}' | cut -d'/' -f1)
        log "Port $WEBSOCKIFY_PORT is already in use by PID $port_pid"
        return 1
    fi
    return 0
}

# Wait for VNC server with enhanced checking
wait_for_vnc() {
    log "Waiting for VNC server on port $VNC_PORT..."
    local count=0
    local max_attempts=30
    
    while [ $count -lt $max_attempts ]; do
        # Check if VNC port is open AND responsive
        if netstat -ln 2>/dev/null | grep ":${VNC_PORT} " >/dev/null; then
            # Try to actually connect to VNC
            if timeout 3 bash -c "echo >/dev/tcp/127.0.0.1/$VNC_PORT" 2>/dev/null; then
                log "VNC server is ready on port $VNC_PORT"
                return 0
            fi
        fi
        
        count=$((count+1))
        if [ $((count % 5)) -eq 0 ]; then
            log "Still waiting for VNC server... ($count/$max_attempts)"
        fi
        sleep 1
    done
    
    log "VNC server is not ready after ${max_attempts}s"
    return 1
}

# Start websockify with enhanced monitoring
start_websockify() {
    log "🚀 Starting websockify on port $WEBSOCKIFY_PORT..."
    
    # Ensure we have a clean start
    cleanup
    
    if ! check_port_available; then
        log "Cannot start - port conflict"
        return 1
    fi
    
    # Start websockify in background with output capture
    local cmd="/opt/novnc/utils/websockify/websockify.py \
        --web /opt/novnc \
        --heartbeat=30 \
        --timeout=0 \
        --idle-timeout=0 \
        --wrap-mode=ignore \
        --log-file=/tmp/websockify.log \
        $WEBSOCKIFY_PORT \
        127.0.0.1:$VNC_PORT"
    
    log "Executing: $cmd"
    $cmd &
    
    local websockify_pid=$!
    echo $websockify_pid > "$WEBSOCKIFY_PID_FILE"
    
    log "Websockify started with PID: $websockify_pid"
    
    # Verify it started successfully
    sleep 3
    
    if ! kill -0 "$websockify_pid" 2>/dev/null; then
        log "Websockify failed to start or died immediately"
        cat /tmp/websockify.log 2>/dev/null | tail -10 | while read line; do
            log "LOG: $line"
        done
        return 1
    fi
    
    # Check if port is now bound
    if ! netstat -ln 2>/dev/null | grep ":${WEBSOCKIFY_PORT} " >/dev/null; then
        log "Websockify started but port $WEBSOCKIFY_PORT is not bound"
        return 1
    fi
    
    log "Websockify is running successfully on port $WEBSOCKIFY_PORT"
    return 0
}

# Monitor websockify process
monitor_websockify() {
    local check_interval=10
    local failure_count=0
    local max_failures=3
    
    log "Starting websockify monitoring (checking every ${check_interval}s)"
    
    while true; do
        if [ -f "$WEBSOCKIFY_PID_FILE" ]; then
            local pid=$(cat "$WEBSOCKIFY_PID_FILE")
            
            if kill -0 "$pid" 2>/dev/null; then
                # Process is alive, check if port is still bound
                if netstat -ln 2>/dev/null | grep ":${WEBSOCKIFY_PORT} " >/dev/null; then
                    failure_count=0
                    log "💚 Websockify health check OK (PID: $pid)"
                else
                    failure_count=$((failure_count+1))
                    log "Websockify process alive but port not bound (failure $failure_count/$max_failures)"
                fi
            else
                failure_count=$((failure_count+1))
                log "Websockify process died (failure $failure_count/$max_failures)"
            fi
        else
            failure_count=$((failure_count+1))
            log "Websockify PID file missing (failure $failure_count/$max_failures)"
        fi
        
        # Exit if too many failures
        if [ $failure_count -ge $max_failures ]; then
            log "💀 Too many failures, exiting monitor"
            break
        fi
        
        sleep $check_interval
    done
}

# Signal handlers
trap 'log "Received SIGTERM"; cleanup; exit 0' TERM
trap 'log "Received SIGINT"; cleanup; exit 0' INT
trap 'log "Received EXIT"; cleanup' EXIT

# Main execution
main() {
    log "Enhanced websockify wrapper starting..."
    
    # Acquire exclusive lock
    if ! acquire_lock; then
        log "Could not acquire lock - another instance may be running"
        exit 1
    fi
    
    # Initial cleanup
    cleanup
    
    # Wait for VNC server
    if ! wait_for_vnc; then
        log "Cannot start without VNC server"
        exit 1
    fi
    
    # Start websockify
    if ! start_websockify; then
        log "Failed to start websockify"
        exit 1
    fi
    
    # Monitor the process
    monitor_websockify
    
    log "Websockify wrapper exiting"
}

# Execute main function
main "$@"