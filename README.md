# Universal Ubuntu VPS Interactive Setup

Complete automation for setting up a secure Ubuntu desktop VPS with RDP access, Tailscale VPN, and applications - **works with both SSH and RDP initial access**.

## Overview

This universal setup system automatically detects your access method and provides the appropriate setup experience for:

- **SSH Users**: Traditional command-line setup with connection testing before lockdown
- **RDP Users**: GUI-enhanced setup with dialog boxes and notifications
- **Console Users**: Direct terminal access setup

### Features Included

- **RDP Server** with session persistence (browser stays open after disconnect)
- **Tailscale VPN** for secure remote access with interactive authentication
- **Security lockdown** (connections only via Tailscale network)
- **OpenClaw** game engine installation with complete build process
- **Google Chrome** browser installation
- **Automated testing** and verification
- **GUI notifications** for RDP users
- **Comprehensive error handling** for both environments

## Files Included

- `universal_vps_setup.py` - Smart setup script (handles both SSH and RDP)
- `post_lockdown_setup.py` - Continuation script for SSH users after lockdown  
- `install.sh` - Quick installer script
- `README.md` - This documentation

## Prerequisites

- Ubuntu Desktop installation (20.04+ recommended)
- Root/sudo access
- Internet connectivity
- Tailscale account (free at https://tailscale.com)
- **Either SSH or RDP access** to start

## Quick Start

### Option 1: One-Command Install
```bash
wget -O - https://raw.githubusercontent.com/brandonbelew/secure-vps/main/install.sh | sudo bash
```

### Option 2: Manual Installation

1. **Download the scripts:**
```bash
wget https://raw.githubusercontent.com/brandonbelew/secure-vps/main/ubuntu/universal_vps_setup.py
wget https://raw.githubusercontent.com/brandonbelew/secure-vps/main/ubuntu/post_lockdown_setup.py
chmod +x *.py
```

2. **Run the universal setup:**
```bash
sudo python3 universal_vps_setup.py
```

3. **SSH users only**: After server lockdown, reconnect via Tailscale and run:
```bash
sudo python3 post_lockdown_setup.py
```

## Setup Process by Access Method

### SSH Users (Command Line Access)

**Phase 1: Initial Setup**
1. **Environment Detection** - Script detects SSH access automatically
2. **System Update** - Updates packages and installs dependencies
3. **RDP Installation** - Installs XRDP server with session persistence
4. **Tailscale Setup** - Interactive authentication and configuration
5. **Connection Testing** - You test RDP and SSH via Tailscale from another device
6. **Server Lockdown** - Restricts access to Tailscale-only (connection lost)

**Phase 2: Post-Lockdown (after reconnecting via Tailscale)**
7. **Connection Verification** - Confirms secure Tailscale connectivity
8. **Application Installation** - Installs OpenClaw and Chrome
9. **Desktop Integration** - Creates shortcuts and final configuration

### RDP Users (Already Connected via RDP)

**Single Phase: Complete Setup**
1. **Environment Detection** - Script detects RDP access and enables GUI
2. **Enhanced Setup Experience** - Progress dialogs and confirmation boxes
3. **RDP Enhancement** - Improves existing RDP configuration for persistence
4. **Tailscale Setup** - Interactive authentication with GUI prompts
5. **Connection Verification** - Confirms Tailscale is working
6. **Server Lockdown** - Secures server (no connection loss for RDP users)
7. **Application Installation** - Installs OpenClaw and Chrome immediately
8. **Completion Notification** - GUI notification of successful setup

## Key Differences by Access Method

| Feature | SSH Users | RDP Users |
|---------|-----------|-----------|
| **Interface** | Terminal only | Terminal + GUI dialogs |
| **Connection Testing** | Manual from another device | Automatic verification |
| **Server Lockdown** | Connection lost, must reconnect | Continuous session |
| **Setup Phases** | 2 phases (before/after lockdown) | 1 continuous phase |
| **Progress Feedback** | Console messages | GUI + console |
| **Error Handling** | Console warnings | Pop-up dialogs |

## Environment Detection

The script automatically detects your environment by checking:
- SSH environment variables (`SSH_CLIENT`, `SSH_CONNECTION`)
- Desktop environment indicators (`DISPLAY`, `XDG_CURRENT_DESKTOP`)
- GUI availability (can create tkinter windows)
- X11/Wayland display servers

## Installation Details

### RDP with Session Persistence
- XRDP server with optimized configuration
- Sessions persist when you disconnect and reconnect
- Browsers and applications continue running
- Multi-user desktop support

### Tailscale Security Integration
- Automatic repository setup and GPG key installation
- Interactive authentication flow (works in both SSH and RDP)
- IP detection and network validation
- Cross-platform client compatibility

### Application Installation
- **OpenClaw**: Complete source build with all SDL2 dependencies
- **Google Chrome**: Latest stable with fallback installation methods
- Desktop integration with proper .desktop files
- User shortcuts created automatically

### Server Lockdown
- UFW firewall with deny-by-default policy
- SSH restricted to Tailscale interface only
- RDP limited to Tailscale subnet (100.64.0.0/10)
- All internet-facing services blocked

## Usage After Setup

### Connection Methods
```bash
# RDP connection via Tailscale
# Use your RDP client with: [tailscale-ip]:3389

# SSH connection via Tailscale
ssh username@[tailscale-ip]
```

### Application Access
- **OpenClaw**: Available in Applications menu and desktop shortcut
- **Chrome**: Available in Applications menu and desktop shortcut
- **Terminal**: For command-line access when needed

## Troubleshooting by Access Method

### SSH Users
**Issue**: Lost connection after lockdown
**Solution**: 
1. Install Tailscale on your local computer
2. Login with same account used on server
3. Connect via RDP: `[tailscale-ip]:3389`
4. Run post-lockdown script: `sudo vps-post-setup`

### RDP Users
**Issue**: Script appears to freeze during build process
**Solution**: 
1. Check terminal output for progress messages
2. OpenClaw compilation takes 5-10 minutes
3. GUI progress dialogs auto-close, terminal shows details

### Both Access Methods
**Issue**: Tailscale authentication fails
**Solution**:
1. Visit https://tailscale.com and create account
2. Script will retry authentication automatically
3. Check firewall isn't blocking Tailscale traffic

## Advanced Configuration

### GUI Customization (RDP Users)
```python
# Modify dialog behavior in universal_vps_setup.py
# Look for messagebox.* calls to customize notifications
```

### SSH Optimization (SSH Users)
```bash
# Add to ~/.ssh/config for easier connection
Host my-vps
    HostName [tailscale-ip]
    User [username]
```

### Application Customization
```bash
# Custom Chrome flags
google-chrome --no-sandbox --disable-gpu

# OpenClaw with specific settings
openclaw --fullscreen --volume 50
```

## Security Considerations

### Universal Security Model
- **Network Isolation**: All access via Tailscale VPN only
- **Service Binding**: SSH/RDP bound to Tailscale interface
- **Firewall Protection**: UFW with restrictive rules
- **Authentication**: Tailscale account-based access control

### Access Method Specific
- **SSH Users**: More secure initial setup (no GUI attack surface)
- **RDP Users**: GUI components increase potential attack surface but are mitigated by network isolation

## Support and Troubleshooting

### Log Files
- `/var/log/universal_vps_setup.log` - Complete setup log
- `/var/log/vps_post_setup.log` - Post-lockdown log (SSH users)

### Getting Help
1. Check log files for detailed error messages
2. Verify Tailscale connectivity: `tailscale ping [device-name]`
3. Test network access: `curl -I http://google.com`
4. Check service status: `systemctl status xrdp tailscaled`

### Common Solutions
```bash
# Reset UFW if locked out
sudo ufw --force reset

# Restart Tailscale
sudo systemctl restart tailscaled
sudo tailscale up

# Check RDP status
sudo systemctl status xrdp
sudo netstat -tlnp | grep :3389
```

## License

These scripts are provided for educational and personal use. Review all commands before execution on production systems.

## Contributing

Improvements welcome! Key areas:
- Additional Linux distribution support
- More application installers
- Enhanced GUI components for RDP users
- Better error recovery mechanisms
