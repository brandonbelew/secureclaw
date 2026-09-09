#!/bin/bash
# fix_openclaw.sh — Fixes OpenClaw installs that used the legacy system service.
# Removes the manual openclaw.service, re-installs via the official installer,
# and enables linger so the user service starts at boot.
#
# Usage:
#   sudo bash fix_openclaw.sh
#   sudo bash fix_openclaw.sh <username>   # specify user explicitly

set -e

RESET=$'\033[0m'; BOLD=$'\033[1m'; RED=$'\033[0;31m'
GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; CYAN=$'\033[0;36m'

ok()   { echo -e "  ${GREEN}✓${RESET}  $1"; }
info() { echo -e "  ${CYAN}ℹ${RESET}  $1"; }
warn() { echo -e "  ${YELLOW}⚠${RESET}  $1"; }
die()  { echo -e "  ${RED}${BOLD}✗ Error:${RESET} $1"; exit 1; }

if [[ $EUID -ne 0 ]]; then
    die "This script must be run as root. Use: sudo bash fix_openclaw.sh"
fi

echo
echo -e "${BOLD}  OpenClaw Service Fix${RESET}"
echo -e "  ${CYAN}──────────────────────────────────────────${RESET}"
echo

# ── Determine target user ──────────────────────────────────────────────────────
if [[ -n "$1" ]]; then
    TARGET_USER="$1"
else
    # Find users in /home with UID >= 1000
    mapfile -t HOME_USERS < <(
        awk -F: '$3 >= 1000 && $6 ~ /^\/home/ {print $1}' /etc/passwd
    )
    if [[ ${#HOME_USERS[@]} -eq 0 ]]; then
        die "No users found in /home. Pass the username as an argument."
    elif [[ ${#HOME_USERS[@]} -eq 1 ]]; then
        TARGET_USER="${HOME_USERS[0]}"
        info "Target user: ${BOLD}${TARGET_USER}${RESET}"
    else
        echo -e "  Multiple users found: ${HOME_USERS[*]}"
        read -rp "  Enter username to fix OpenClaw for: " TARGET_USER
    fi
fi

id "$TARGET_USER" &>/dev/null || die "User '$TARGET_USER' does not exist."

echo

# ── Step 1: Remove legacy system service ──────────────────────────────────────
info "Checking for legacy system service..."
if systemctl list-unit-files openclaw.service 2>/dev/null | grep -q openclaw; then
    info "Stopping and removing openclaw.service..."
    systemctl stop openclaw 2>/dev/null || true
    systemctl disable openclaw 2>/dev/null || true
    rm -f /etc/systemd/system/openclaw.service
    systemctl daemon-reload
    ok "Legacy system service removed"
else
    ok "No legacy system service found"
fi

# ── Step 2: Kill any orphaned openclaw-gateway processes ──────────────────────
info "Cleaning up any stale gateway processes..."
pkill -u "$TARGET_USER" -f openclaw-gateway 2>/dev/null || true
sleep 1
ok "Stale processes cleared"

# ── Step 3: Ensure Node.js is present and new enough (installer needs it, can't sudo without TTY) ──
# OpenClaw's installer hard-requires Node 24.16.0+ or 26.1.0+ and refuses to
# run on an older active Node (this used to be v22, which it now rejects).
node_is_supported() {
    command -v node &>/dev/null || return 1
    local ver="$(node --version)"; ver="${ver#v}"
    local major="${ver%%.*}"; local rest="${ver#*.}"; local minor="${rest%%.*}"
    [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ ]] || return 1
    (( major > 26 )) && return 0
    (( major == 26 && minor >= 1 )) && return 0
    (( major == 24 && minor >= 16 )) && return 0
    return 1
}

info "Ensuring Node.js is installed and supported (24.16.0+ or 26.1.0+)..."
if ! node_is_supported; then
    if command -v node &>/dev/null; then
        warn "Found Node.js $(node --version), which OpenClaw's installer no longer accepts — upgrading to 26.x"
    fi
    # NodeSource + build toolchain differ by distro family.
    if command -v apt-get &>/dev/null; then
        curl -fsSL https://deb.nodesource.com/setup_26.x | bash -
        apt-get install -y nodejs build-essential cmake make g++ python3
    elif command -v dnf &>/dev/null; then
        curl -fsSL https://rpm.nodesource.com/setup_26.x | bash -
        dnf -y install nodejs gcc gcc-c++ make cmake python3
    else
        die "Unsupported system: need apt (Debian/Ubuntu) or dnf (Fedora/RHEL/Rocky)."
    fi
    ok "Node.js installed ($(node --version))"
else
    ok "Node.js already present and supported ($(node --version))"
fi

# ── Step 4: Re-install via official installer ─────────────────────────────────
info "Running official OpenClaw installer as ${TARGET_USER}..."
echo
su - "$TARGET_USER" -c \
    'curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard'
echo
ok "OpenClaw installed"

# ── Step 5: Enable linger ──────────────────────────────────────────────────────
info "Enabling linger for ${TARGET_USER} (service starts at boot)..."
loginctl enable-linger "$TARGET_USER"
ok "Linger enabled"

# ── Done ──────────────────────────────────────────────────────────────────────
echo
echo -e "  ${CYAN}──────────────────────────────────────────${RESET}"
echo -e "  ${GREEN}${BOLD}Fix complete!${RESET}"
echo
echo -e "  OpenClaw is now managed by its own user service."
echo -e "  To set up Discord (or any other channel), run as ${TARGET_USER}:"
echo
echo -e "    ${YELLOW}openclaw onboard${RESET}"
echo -e "    ${YELLOW}openclaw channels login --channel discord${RESET}"
echo
