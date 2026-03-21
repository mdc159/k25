#!/bin/bash
#
# Karaoke Agent Launcher
# Starts the Docker container and opens the dashboard
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")"

# Terminal for logs
TERMINAL="gnome-terminal"

# Check if Docker is running
if ! docker info &>/dev/null; then
    notify-send "Karaoke Agent" "Docker is not running. Starting Docker..." -i "$SCRIPT_DIR/karaoke-icon.png"
    systemctl --user start docker 2>/dev/null || sudo systemctl start docker
    sleep 3
fi

# Check if container is already running
if docker ps --format '{{.Names}}' | grep -q "karaoke-agent"; then
    notify-send "Karaoke Agent" "Agent is already running" -i "$SCRIPT_DIR/karaoke-icon.png"
else
    # Start the agent
    notify-send "Karaoke Agent" "Starting Karaoke Agent..." -i "$SCRIPT_DIR/karaoke-icon.png"
    cd "$AGENT_DIR"
    docker compose up -d

    if [ $? -eq 0 ]; then
        notify-send "Karaoke Agent" "Agent started successfully!" -i "$SCRIPT_DIR/karaoke-icon.png"
    else
        notify-send "Karaoke Agent" "Failed to start agent" -i "$SCRIPT_DIR/karaoke-icon.png" -u critical
    fi
fi

# Open dashboard in browser
DASHBOARD_URL="http://localhost:5173"
xdg-open "$DASHBOARD_URL" 2>/dev/null || sensible-browser "$DASHBOARD_URL" 2>/dev/null

# Open terminal with logs
$TERMINAL -- bash -c "cd '$AGENT_DIR' && docker compose logs -f; exec bash" &
