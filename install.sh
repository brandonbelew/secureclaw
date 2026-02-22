#!/bin/bash
# Ubuntu VPS Setup Installer
# Downloads and executes the interactive setup scripts

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# GitHub repository (update with your actual repo)
REPO_BASE_URL="https://raw.githubusercontent.com/brandonbelew/secure-vps/main"

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}     Ubuntu VPS Interactive Setup      ${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo
}

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        echo "Please run: sudo $0"
        exit 1
    fi
}

check_ubuntu() {
    if ! command -v apt &> /dev/null; then
        print_error "This script is designed for Ubuntu/Debian systems"
        exit 1
    fi
    
    # Check Ubuntu version
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        print_status "Detected: $PRETTY_NAME"
    fi
}

install_python() {
    if ! command -v python3 &> /dev/null; then
        print_status "Installing Python 3..."
        apt update
        apt install -y python3 python3-pip
    else
        print_status "Python 3 is already installed"
    fi
}

download_scripts() {
    print_status "Downloading setup scripts..."
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    
    # Download main scripts
    if command -v wget &> /dev/null; then
        wget -q "$REPO_BASE_URL/ubuntu/universal_vps_setup.py" -O universal_vps_setup.py
        wget -q "$REPO_BASE_URL/ubuntu/post_lockdown_setup.py" -O post_lockdown_setup.py
    elif command -v curl &> /dev/null; then
        curl -s "$REPO_BASE_URL/ubuntu/universal_vps_setup.py" -o universal_vps_setup.py
        curl -s "$REPO_BASE_URL/ubuntu/post_lockdown_setup.py" -o post_lockdown_setup.py
    else
        print_error "Neither wget nor curl is available"
        apt update && apt install -y wget
        wget -q "$REPO_BASE_URL/ubuntu/universal_vps_setup.py" -O universal_vps_setup.py
        wget -q "$REPO_BASE_URL/ubuntu/post_lockdown_setup.py" -O post_lockdown_setup.py
    fi
    
    # Make scripts executable
    chmod +x *.py
    
    # Copy to permanent location
    cp universal_vps_setup.py /usr/local/bin/
    cp post_lockdown_setup.py /usr/local/bin/
    
    print_status "Scripts installed to /usr/local/bin/"
}

create_shortcuts() {
    print_status "Creating command shortcuts..."
    
    # Create wrapper scripts
    cat > /usr/local/bin/vps-setup << 'EOF'
#!/bin/bash
cd /usr/local/bin
python3 universal_vps_setup.py "$@"
EOF

    cat > /usr/local/bin/vps-post-setup << 'EOF'
#!/bin/bash
cd /usr/local/bin
python3 post_lockdown_setup.py "$@"
EOF

    chmod +x /usr/local/bin/vps-setup
    chmod +x /usr/local/bin/vps-post-setup
    
    print_status "Command shortcuts created:"
    echo "  - vps-setup (universal setup script)"
    echo "  - vps-post-setup (post-lockdown script for SSH users)"
}

show_usage() {
    echo -e "${GREEN}Installation complete!${NC}"
    echo
    echo "Usage:"
    echo "  1. Run the universal setup: ${YELLOW}sudo vps-setup${NC}"
    echo "     • Works for both SSH and RDP initial access"
    echo "     • Automatically detects your environment"
    echo "  2. For SSH users: after server lockdown, reconnect via Tailscale"
    echo "  3. SSH users then run: ${YELLOW}sudo vps-post-setup${NC}"
    echo "     • RDP users get full setup in one go"
    echo
    echo "For manual execution:"
    echo "  - ${YELLOW}sudo python3 /usr/local/bin/universal_vps_setup.py${NC}"
    echo "  - ${YELLOW}sudo python3 /usr/local/bin/post_lockdown_setup.py${NC}"
    echo
    echo -e "${BLUE}Ready to start? Run: sudo vps-setup${NC}"
}

main() {
    print_header
    
    check_root
    check_ubuntu
    install_python
    download_scripts
    create_shortcuts
    show_usage
    
    # Ask if user wants to start setup immediately
    echo
    read -p "Would you like to start the setup now? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Starting VPS setup..."
        exec /usr/local/bin/vps-setup
    else
        print_status "Setup ready. Run 'sudo vps-setup' when ready to begin."
    fi
}

# For local development/testing
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # If we're running locally, use local files instead of downloading
    if [[ -f "universal_vps_setup.py" && -f "post_lockdown_setup.py" ]]; then
        print_header
        print_status "Using local scripts for development"
        
        check_root
        check_ubuntu
        install_python
        
        # Copy local files
        cp universal_vps_setup.py /usr/local/bin/
        cp post_lockdown_setup.py /usr/local/bin/
        chmod +x /usr/local/bin/*.py
        
        create_shortcuts
        show_usage
        
        echo
        read -p "Would you like to start the setup now? (y/N): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Starting VPS setup..."
            exec /usr/local/bin/vps-setup
        fi
    else
        main
    fi
else
    main
fi
