#!/bin/bash
# Karaoke Agent Installation Script
#
# This script installs and configures the karaoke-agent systemd service.
# Run as root or with sudo.
#
# Usage:
#   sudo ./install.sh
#   sudo ./install.sh --uninstall

set -e

# Configuration
INSTALL_DIR="/opt/karaoke-agent"
DATA_DIR="/var/lib/karaoke-agent"
SERVICE_USER="hammer"
SERVICE_GROUP="hammer"
SERVICE_NAME="karaoke-agent"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

check_dependencies() {
    log_info "Checking dependencies..."

    # Check for uv
    if ! command -v /home/${SERVICE_USER}/.local/bin/uv &> /dev/null; then
        log_error "uv not found. Install it first:"
        log_error "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi

    # Check for yt-dlp
    if ! command -v /home/${SERVICE_USER}/.local/bin/yt-dlp &> /dev/null; then
        log_warn "yt-dlp not found in user's .local/bin"
        log_warn "Install with: pip install --user yt-dlp"
    fi

    log_info "Dependencies OK"
}

install() {
    log_info "Installing ${SERVICE_NAME}..."

    # Create directories
    log_info "Creating directories..."
    mkdir -p "${INSTALL_DIR}"
    mkdir -p "${DATA_DIR}/spool"

    # Copy package files
    log_info "Copying package files..."
    cp -r ../src "${INSTALL_DIR}/"
    cp ../pyproject.toml "${INSTALL_DIR}/"

    # Copy env example if .env doesn't exist
    if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
        cp env.example "${INSTALL_DIR}/.env"
        log_warn "Created ${INSTALL_DIR}/.env from template"
        log_warn "Please edit this file with your configuration!"
    fi

    # Set ownership
    log_info "Setting permissions..."
    chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${INSTALL_DIR}"
    chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${DATA_DIR}"
    chmod 600 "${INSTALL_DIR}/.env"

    # Create virtual environment and install dependencies
    log_info "Installing Python dependencies..."
    sudo -u "${SERVICE_USER}" bash -c "cd ${INSTALL_DIR} && /home/${SERVICE_USER}/.local/bin/uv venv && /home/${SERVICE_USER}/.local/bin/uv pip install -e ."

    # Install systemd service
    log_info "Installing systemd service..."
    cp karaoke-agent.service /etc/systemd/system/${SERVICE_NAME}.service
    systemctl daemon-reload

    log_info "Installation complete!"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Edit ${INSTALL_DIR}/.env with your configuration"
    log_info "  2. Enable the service: systemctl enable ${SERVICE_NAME}"
    log_info "  3. Start the service: systemctl start ${SERVICE_NAME}"
    log_info "  4. Check status: systemctl status ${SERVICE_NAME}"
    log_info "  5. View logs: journalctl -u ${SERVICE_NAME} -f"
}

uninstall() {
    log_info "Uninstalling ${SERVICE_NAME}..."

    # Stop and disable service
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        log_info "Stopping service..."
        systemctl stop "${SERVICE_NAME}"
    fi

    if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
        log_info "Disabling service..."
        systemctl disable "${SERVICE_NAME}"
    fi

    # Remove service file
    if [[ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]]; then
        log_info "Removing service file..."
        rm "/etc/systemd/system/${SERVICE_NAME}.service"
        systemctl daemon-reload
    fi

    # Ask about data
    read -p "Remove installation directory ${INSTALL_DIR}? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "${INSTALL_DIR}"
        log_info "Removed ${INSTALL_DIR}"
    fi

    read -p "Remove data directory ${DATA_DIR}? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "${DATA_DIR}"
        log_info "Removed ${DATA_DIR}"
    fi

    log_info "Uninstallation complete!"
}

# Main
check_root

case "${1:-}" in
    --uninstall)
        uninstall
        ;;
    *)
        check_dependencies
        install
        ;;
esac
