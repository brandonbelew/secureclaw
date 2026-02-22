#!/bin/bash
# Ubuntu VPS Setup Installer

set -e

# ── Colors ────────────────────────────────────────────────────────────────────
RESET=$'\033[0m'
BOLD=$'\033[1m'
DIM=$'\033[2m'
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[0;33m'
BLUE=$'\033[0;34m'
CYAN=$'\033[0;36m'
WHITE=$'\033[1;37m'

# ── Helpers ───────────────────────────────────────────────────────────────────
print_banner() {
    clear
    echo
    echo -e "${BLUE}${BOLD}  ╔══════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${BLUE}${BOLD}  ║                                                              ║${RESET}"
    echo -e "${BLUE}${BOLD}  ║           🦞  SecureClaw Setup Installer                     ║${RESET}"
    echo -e "${BLUE}${BOLD}  ║           Secure Remote Desktop Environment                 ║${RESET}"
    echo -e "${BLUE}${BOLD}  ║                                By: Brandon Belew            ║${RESET}"
    echo -e "${BLUE}${BOLD}  ║                                                              ║${RESET}"
    echo -e "${BLUE}${BOLD}  ╚══════════════════════════════════════════════════════════════╝${RESET}"
    echo
    echo -e "  ${YELLOW}${BOLD}  ⚠  WARNING${RESET}"
    echo -e "  ${YELLOW}  This script is intended for use on a fresh virtual private server only.${RESET}"
    echo -e "  ${YELLOW}  It will modify firewall policies and system configuration in ways that${RESET}"
    echo -e "  ${YELLOW}  may lock you out or require a full server reinstall if something goes${RESET}"
    echo -e "  ${YELLOW}  wrong. By continuing, you accept all responsibility for any data loss${RESET}"
    echo -e "  ${YELLOW}  or damages. Proceed only if you know what you are doing.${RESET}"
    echo
}

print_divider() {
    echo -e "${DIM}  ──────────────────────────────────────────────────────────────${RESET}"
}

print_step() {
    local num=$1
    local total=$2
    local msg=$3
    printf "  ${CYAN}${BOLD}[%s/%s]${RESET}  %s" "$num" "$total" "$msg"
}

print_ok() {
    echo -e "  ${GREEN}${BOLD}✓ Done${RESET}"
}

print_info() {
    echo -e "  ${WHITE}ℹ${RESET}  $1"
}

print_warn() {
    echo -e "  ${YELLOW}⚠${RESET}  $1"
}

print_error() {
    echo -e "  ${RED}${BOLD}✗ Error:${RESET} $1"
}

# ── Checks ────────────────────────────────────────────────────────────────────
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root."
        echo
        echo -e "  Please run:  ${YELLOW}sudo bash install.sh${RESET}"
        echo
        exit 1
    fi
}

check_ubuntu() {
    if ! command -v apt &> /dev/null; then
        print_error "This installer only supports Ubuntu/Debian systems."
        exit 1
    fi
}

# ── Steps ─────────────────────────────────────────────────────────────────────
install_python() {
    print_step 2 4 "Installing Python and dependencies...    "
    if ! command -v python3 &> /dev/null; then
        apt-get update -qq
        apt-get install -y -qq python3 python3-pip python3-tk > /dev/null 2>&1
    else
        # Ensure tkinter is present even if python3 was pre-installed
        apt-get install -y -qq python3-tk > /dev/null 2>&1
    fi
    print_ok
}

install_scripts() {
    print_step 3 4 "Installing setup scripts...              "

    # Locate scripts — check ubuntu/ subdirectory first, then current directory
    SCRIPT_DIR=""
    if [[ -f "ubuntu/universal_vps_setup.py" && -f "ubuntu/post_lockdown_setup.py" ]]; then
        SCRIPT_DIR="ubuntu"
    elif [[ -f "universal_vps_setup.py" && -f "post_lockdown_setup.py" ]]; then
        SCRIPT_DIR="."
    fi

    if [[ -n "$SCRIPT_DIR" ]]; then
        cp "$SCRIPT_DIR/universal_vps_setup.py" /usr/local/bin/
        cp "$SCRIPT_DIR/post_lockdown_setup.py" /usr/local/bin/
        chmod +x /usr/local/bin/universal_vps_setup.py
        chmod +x /usr/local/bin/post_lockdown_setup.py
    else
        # Repo not available locally — download from GitHub
        REPO_BASE="https://raw.githubusercontent.com/brandonbelew/secureclaw/main"
        if command -v curl &> /dev/null; then
            curl -fsSL "$REPO_BASE/ubuntu/universal_vps_setup.py" -o /usr/local/bin/universal_vps_setup.py
            curl -fsSL "$REPO_BASE/ubuntu/post_lockdown_setup.py" -o /usr/local/bin/post_lockdown_setup.py
        else
            apt-get install -y -qq curl > /dev/null 2>&1
            curl -fsSL "$REPO_BASE/ubuntu/universal_vps_setup.py" -o /usr/local/bin/universal_vps_setup.py
            curl -fsSL "$REPO_BASE/ubuntu/post_lockdown_setup.py" -o /usr/local/bin/post_lockdown_setup.py
        fi
        chmod +x /usr/local/bin/universal_vps_setup.py
        chmod +x /usr/local/bin/post_lockdown_setup.py
    fi

    print_ok
}

create_shortcuts() {
    print_step 4 4 "Creating shortcuts...                    "

    cat > /usr/local/bin/vps-setup << 'EOF'
#!/bin/bash
REPO_BASE="https://raw.githubusercontent.com/brandonbelew/secureclaw/main"
curl -fsSL "$REPO_BASE/ubuntu/universal_vps_setup.py" -o /usr/local/bin/universal_vps_setup.py 2>/dev/null \
    && chmod +x /usr/local/bin/universal_vps_setup.py \
    || echo "  Warning: could not fetch latest script, running cached version"
python3 /usr/local/bin/universal_vps_setup.py "$@"
EOF

    cat > /usr/local/bin/vps-post-setup << 'EOF'
#!/bin/bash
REPO_BASE="https://raw.githubusercontent.com/brandonbelew/secureclaw/main"
curl -fsSL "$REPO_BASE/ubuntu/post_lockdown_setup.py" -o /usr/local/bin/post_lockdown_setup.py 2>/dev/null \
    && chmod +x /usr/local/bin/post_lockdown_setup.py \
    || echo "  Warning: could not fetch latest script, running cached version"
python3 /usr/local/bin/post_lockdown_setup.py "$@"
EOF

    chmod +x /usr/local/bin/vps-setup
    chmod +x /usr/local/bin/vps-post-setup
    print_ok
}

show_complete() {
    echo
    print_divider
    echo
    echo -e "  ${GREEN}${BOLD}  Installation complete!${RESET}"
    echo
    echo -e "  This installer will set up your server with:"
    echo -e "  ${GREEN}  ✓${RESET}  Remote Desktop (RDP) access"
    echo -e "  ${GREEN}  ✓${RESET}  A dedicated user account with sudo access"
    echo -e "  ${GREEN}  ✓${RESET}  Tailscale VPN — secure remote access from anywhere"
    echo -e "  ${GREEN}  ✓${RESET}  OpenClaw AI assistant — running as a background service"
    echo -e "  ${GREEN}  ✓${RESET}  Google Chrome browser"
    echo
    print_divider
    echo
    echo -e "  ${BOLD}What happens next:${RESET}"
    echo
    echo -e "  ${CYAN}  1.${RESET}  The setup wizard will guide you step by step"
    echo -e "  ${CYAN}  2.${RESET}  You will create your RDP login username and password"
    echo -e "  ${CYAN}  3.${RESET}  You will be asked to authenticate Tailscale"
    echo -e "       ${DIM}(a link will appear — open it in your browser)${RESET}"
    echo -e "  ${CYAN}  4.${RESET}  After lockdown, SSH will drop — reconnect via Tailscale"
    echo -e "  ${CYAN}  5.${RESET}  Run ${YELLOW}sudo vps-post-setup${RESET} to finish the installation"
    echo
    print_divider
    echo
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    print_banner

    check_root
    check_ubuntu

    echo -e "  ${BOLD}Preparing your server...${RESET}"
    echo
    print_step 1 4 "Checking system...                       "
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        print_ok
        print_info "Detected: ${PRETTY_NAME}"
    else
        print_ok
    fi

    install_python
    install_scripts
    create_shortcuts
    show_complete

    read -rp "$(echo -e "  ${BOLD}Start setup now?${RESET} (Y/n): ")" reply
    echo

    reply=${reply:-y}
    if [[ "$reply" =~ ^[Yy]$ ]]; then
        echo -e "  ${GREEN}${BOLD}Starting setup wizard...${RESET}"
        echo
        exec /usr/local/bin/vps-setup
    else
        echo -e "  ${YELLOW}Ready when you are.${RESET}  Run: ${BOLD}sudo vps-setup${RESET}"
        echo
    fi
}

main
