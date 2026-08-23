#!/usr/bin/env bash
# install_widget.sh — Standalone AI agent Control Panel installer
# Installs openclaw-widget, which self-detects OpenClaw vs Hermes Agent at
# runtime (see detect_agent() in openclaw_widget.py) and adapts.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/brandonbelew/secureclaw/main/ubuntu/install_widget.sh | sudo bash
#   curl -fsSL https://raw.githubusercontent.com/brandonbelew/secureclaw/dev/ubuntu/install_widget.sh  | sudo bash -s -- dev

set -euo pipefail

REPO_OWNER="brandonbelew"
REPO_NAME="secureclaw"
INSTALL_BIN="/usr/local/bin/openclaw-widget"
DESKTOP_DIR="/usr/local/share/applications"
SUDOERS_FILE="/etc/sudoers.d/openclaw-widget"

# Which agent's branding to show in the desktop entry / banner. Mirrors
# detect_agent()/find_hermes_binary() in openclaw_widget.py; the widget
# itself re-detects at launch regardless, so this only affects the static
# Name=/Comment= text and this script's own output.
#
# This script runs as root (sudo), but the agent is typically installed for
# a separate non-root RDP/admin user — so `command -v hermes` as root alone
# is unreliable (root's PATH never includes another user's ~/.local/bin).
# Check the known install locations directly, across every real user home,
# same as the Python setup scripts do.
_agent_binary_exists() {
    local bin_name="$1"
    [[ -x "/usr/local/bin/${bin_name}" ]] && return 0
    command -v "$bin_name" &>/dev/null && return 0
    local user_dir
    for user_dir in /home/*/; do
        [[ -x "${user_dir}.local/bin/${bin_name}" ]] && return 0
    done
    return 1
}

if _agent_binary_exists hermes && ! _agent_binary_exists openclaw; then
    AGENT_LABEL="Hermes Agent"
else
    AGENT_LABEL="OpenClaw"
fi

# ── Detect branch ──────────────────────────────────────────────────────────────
detect_branch() {
    # If a branch argument was passed, use it
    if [[ -n "${1:-}" ]]; then
        echo "$1"
        return
    fi
    # If we're inside the repo, use git
    if git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
        local branch
        branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
        if [[ "$branch" == "main" || "$branch" == "dev" ]]; then
            echo "$branch"
            return
        fi
    fi
    echo "main"
}

BRANCH=$(detect_branch "${1:-}")
echo "Using branch: $BRANCH"

RAW_BASE="https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${BRANCH}"

# ── Detect package manager / distro family ─────────────────────────────────────
if command -v apt-get &>/dev/null; then
    PKG_FAMILY="debian"
elif command -v dnf &>/dev/null; then
    PKG_FAMILY="rhel"
else
    echo "Unsupported system: need apt (Debian/Ubuntu) or dnf (Fedora/RHEL/Rocky)." >&2
    exit 1
fi

# ── Install GTK3 dependencies ──────────────────────────────────────────────────
echo "[1/8] Installing dependencies..."
if [[ "$PKG_FAMILY" == "rhel" ]]; then
    dnf -y install python3-gobject gtk3 wget >/dev/null
    ADMIN_GROUP="wheel"
    FW_STATUS_CMD="/usr/bin/firewall-cmd --state"
else
    apt-get install -y python3-gi gir1.2-gtk-3.0 wget >/dev/null
    ADMIN_GROUP="sudo"
    FW_STATUS_CMD="/usr/sbin/ufw status"
fi

# ── Download widget script + shared platform module ───────────────────────────
echo "[2/8] Downloading openclaw-widget..."
# platform_support.py must sit beside the widget — it imports it to choose the
# firewall command (ufw vs firewall-cmd).
wget -q -O /usr/local/bin/platform_support.py "${RAW_BASE}/ubuntu/platform_support.py?$(date +%s)" || true
wget -q -O "$INSTALL_BIN" "${RAW_BASE}/ubuntu/openclaw_widget.py?$(date +%s)"
chmod +x "$INSTALL_BIN"
# Inject branch so widget can fetch manifest from the correct branch at runtime
sed -i "s/^REPO_BRANCH_OVERRIDE = None.*$/REPO_BRANCH_OVERRIDE = \"${BRANCH}\"/" "$INSTALL_BIN"

# ── Sudoers entry for firewall status ──────────────────────────────────────────
echo "[3/8] Writing sudoers entry..."
cat > "$SUDOERS_FILE" <<EOF
# Allow admins to check firewall status without a password (used by openclaw-widget)
%${ADMIN_GROUP} ALL=(ALL) NOPASSWD: ${FW_STATUS_CMD}
EOF
chmod 440 "$SUDOERS_FILE"

# ── System-wide .desktop file ──────────────────────────────────────────────────
echo "[4/8] Installing application menu entry..."
mkdir -p "$DESKTOP_DIR"
cat > "${DESKTOP_DIR}/openclaw-widget.desktop" <<EOF
[Desktop Entry]
Name=${AGENT_LABEL} Control Panel
Comment=${AGENT_LABEL} service status and launcher
Exec=/usr/local/bin/openclaw-widget
Icon=network-server
Terminal=false
Type=Application
Categories=Network;System;
StartupNotify=true
X-GNOME-Autostart-enabled=true
EOF

# ── Per-user autostart + desktop shortcut ─────────────────────────────────────
echo "[5/8] Creating per-user autostart and desktop entries..."

DESKTOP_CONTENT="[Desktop Entry]
Name=${AGENT_LABEL} Control Panel
Comment=${AGENT_LABEL} service status and launcher
Exec=/usr/local/bin/openclaw-widget
Icon=network-server
Terminal=false
Type=Application
Categories=Network;System;
StartupNotify=true
X-GNOME-Autostart-enabled=true"

for user_dir in /home/*/; do
    [[ -d "$user_dir" ]] || continue
    username=$(basename "$user_dir")
    uid=$(id -u "$username" 2>/dev/null || echo 0)
    (( uid < 1000 )) && continue

    # Autostart
    autostart_dir="${user_dir}.config/autostart"
    mkdir -p "$autostart_dir"
    echo "$DESKTOP_CONTENT" > "${autostart_dir}/openclaw-widget.desktop"
    chown -R "${username}:${username}" "$autostart_dir"

    # Desktop shortcut
    desktop_dir="${user_dir}Desktop"
    mkdir -p "$desktop_dir"
    echo "$DESKTOP_CONTENT" > "${desktop_dir}/openclaw-widget.desktop"
    chmod +x "${desktop_dir}/openclaw-widget.desktop"
    chown "${username}:${username}" "${desktop_dir}/openclaw-widget.desktop"

    echo "  -> autostart + desktop shortcut created for $username"
done

echo "[6/8] Updating desktop database..."
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

# ── Restart any running instance ────────────────────────────────────────────
# It's a long-running GTK app, so a re-fetched file alone doesn't pick up
# until the process restarts. Kill any stale instance, then best-effort
# relaunch it in each real user's active desktop session, so an admin
# re-running this script doesn't need to know to do this manually.
echo "[7/8] Restarting the widget in active sessions..."
pkill -f "$INSTALL_BIN" 2>/dev/null || true
sleep 1

restarted=0
for user_dir in /home/*/; do
    [[ -d "$user_dir" ]] || continue
    username=$(basename "$user_dir")
    uid=$(id -u "$username" 2>/dev/null || echo 0)
    (( uid < 1000 )) && continue

    # Find an X display this user owns (xrdp/X11, or Xwayland spawned for an
    # X11 app under a Wayland session like gnome-remote-desktop) by reading
    # the DISPLAY argument off a running Xorg/Xwayland process of theirs.
    # A pure-Wayland session with no Xwayland running yet isn't detected
    # here — it falls through to the "next login" message below, which is
    # still correct since the autostart entry is already in place.
    display=""
    for pid in $(pgrep -u "$username" -f 'Xorg|Xwayland' 2>/dev/null || true); do
        # The process can race away between pgrep and this read (or the pipe
        # itself can fail); under `set -e -o pipefail` a plain `var=$(...)`
        # assignment DOES abort the script on a non-zero exit, unlike the
        # `for x in $(...)` above — so this needs its own `|| true` guard.
        display=$(tr '\0' '\n' < "/proc/$pid/cmdline" 2>/dev/null | grep -E '^:[0-9]+$' | head -1 || true)
        [[ -n "$display" ]] && break
    done
    [[ -z "$display" ]] && continue

    xauth="${user_dir}.Xauthority"
    if [[ -f "$xauth" ]]; then
        sudo -u "$username" env DISPLAY="$display" XAUTHORITY="$xauth" setsid "$INSTALL_BIN" >/dev/null 2>&1 &
    else
        sudo -u "$username" env DISPLAY="$display" setsid "$INSTALL_BIN" >/dev/null 2>&1 &
    fi
    disown
    restarted=1
    echo "  -> restarted for $username (display $display)"
done

if [[ "$restarted" -eq 0 ]]; then
    echo "  -> no active X session found; it will start automatically on next login"
fi

echo "[8/8] Done!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ${AGENT_LABEL} Control Panel installed successfully!"
echo ""
echo " To launch manually:  openclaw-widget &"
echo " Auto-starts on:      next RDP session login"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
