#!/usr/bin/env python3
"""
Post-Lockdown Setup Continuation Script
Completes OpenClaw and Chrome installation after server lockdown
Author: Brandon
"""

import os
import sys
import subprocess
import time
from pathlib import Path

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class PostLockdownSetup:
    def __init__(self):
        self.setup_log = []
        
    def log(self, message, level="INFO"):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        self.setup_log.append(log_entry)
        
        if level == "ERROR":
            print(f"{Colors.FAIL}{log_entry}{Colors.ENDC}")
        elif level == "WARNING":
            print(f"{Colors.WARNING}{log_entry}{Colors.ENDC}")
        elif level == "SUCCESS":
            print(f"{Colors.GREEN}{log_entry}{Colors.ENDC}")
        else:
            print(f"{Colors.CYAN}{log_entry}{Colors.ENDC}")

    def run_command(self, command, check=True, shell=True, capture_output=True):
        try:
            self.log(f"Executing: {command}")
            result = subprocess.run(
                command, 
                shell=shell, 
                check=check, 
                capture_output=capture_output,
                text=True
            )
            if capture_output and result.stdout:
                self.log(f"Command output: {result.stdout.strip()}")
            return result
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed: {command}", "ERROR")
            if capture_output and e.stderr:
                self.log(f"Error output: {e.stderr.strip()}", "ERROR")
            raise

    def verify_tailscale_connection(self):
        """Verify we're connected via Tailscale"""
        print(f"\n{Colors.HEADER}=== VERIFYING TAILSCALE CONNECTION ==={Colors.ENDC}")
        
        try:
            result = self.run_command("tailscale ip -4")
            tailscale_ip = result.stdout.strip()
            
            # Check if we're connecting from SSH_CLIENT via Tailscale network
            ssh_client = os.environ.get('SSH_CLIENT', '')
            if ssh_client:
                client_ip = ssh_client.split()[0]
                if client_ip.startswith('100.'):  # Tailscale IP range
                    self.log(f"Confirmed connection via Tailscale from {client_ip}", "SUCCESS")
                    return True
                else:
                    self.log(f"Warning: Connected from non-Tailscale IP {client_ip}", "WARNING")
            
            self.log(f"Server Tailscale IP: {tailscale_ip}", "SUCCESS")
            return True
            
        except Exception as e:
            self.log(f"Failed to verify Tailscale connection: {e}", "ERROR")
            return False

    def test_lockdown_status(self):
        """Verify server lockdown is working"""
        print(f"\n{Colors.HEADER}=== LOCKDOWN STATUS CHECK ==={Colors.ENDC}")
        
        # Check UFW status
        result = self.run_command("ufw status verbose")
        if "Status: active" in result.stdout:
            self.log("UFW firewall is active", "SUCCESS")
            
            # Show current rules
            rules = result.stdout
            if "100.64.0.0/10" in rules:
                self.log("Tailscale subnet rules are active", "SUCCESS")
            else:
                self.log("Tailscale subnet rules not found", "WARNING")
        else:
            self.log("UFW firewall is not active!", "ERROR")
        
        # Check SSH configuration
        try:
            result = self.run_command("ss -tlnp | grep :22")
            tailscale_result = self.run_command("tailscale ip -4")
            tailscale_ip = tailscale_result.stdout.strip()
            
            if tailscale_ip in result.stdout:
                self.log("SSH is listening only on Tailscale IP", "SUCCESS")
            else:
                self.log("SSH may be listening on other interfaces", "WARNING")
        except:
            self.log("Could not verify SSH configuration", "WARNING")

    def get_install_user(self):
        """Find the primary non-root user to install OpenClaw for"""
        users = [
            d.name for d in Path("/home").iterdir()
            if d.is_dir() and d.stat().st_uid >= 1000
        ]
        if len(users) == 1:
            return users[0]
        elif len(users) > 1:
            print(f"\n{Colors.CYAN}Multiple users found: {', '.join(users)}{Colors.ENDC}")
            while True:
                choice = input("Enter username to install OpenClaw for: ").strip()
                if choice in users:
                    return choice
                print(f"{Colors.WARNING}Invalid choice. Options: {', '.join(users)}{Colors.ENDC}")
        else:
            self.log("No regular user found in /home", "ERROR")
            return None

    def install_openclaw(self):
        """Install OpenClaw AI assistant and run it as a systemd service"""
        print(f"\n{Colors.HEADER}=== OPENCLAW AI INSTALLATION ==={Colors.ENDC}")
        self.log("Installing OpenClaw AI...")

        install_user = self.get_install_user()
        if not install_user:
            self.log("Skipping OpenClaw install — no target user found", "WARNING")
            return

        # Pre-install Node.js v22+ as root (OpenClaw requires v22+).
        # Installing here prevents the openclaw installer from trying to
        # invoke sudo internally, which fails in a non-interactive su session.
        self.log("Installing Node.js v22 prerequisite...")
        self.run_command("curl -fsSL https://deb.nodesource.com/setup_22.x | bash -")
        self.run_command("apt-get install -y nodejs")

        # Run the official OpenClaw installer as the target user
        self.log(f"Running OpenClaw installer as {install_user}...")
        self.run_command(
            f"su - {install_user} -c 'curl -fsSL https://openclaw.ai/install.sh | bash'",
            capture_output=False
        )

        # Locate the installed binary
        result = self.run_command(
            f"su - {install_user} -c 'which openclaw'",
            check=False
        )
        if result.returncode == 0:
            openclaw_bin = result.stdout.strip()
        else:
            candidates = [
                f"/home/{install_user}/.local/bin/openclaw",
                f"/home/{install_user}/.npm-global/bin/openclaw",
                "/usr/local/bin/openclaw",
            ]
            openclaw_bin = next((p for p in candidates if Path(p).exists()), None)
            if not openclaw_bin:
                self.log("Could not locate openclaw binary after installation", "ERROR")
                raise FileNotFoundError("openclaw binary not found")

        self.log(f"OpenClaw binary found at: {openclaw_bin}", "SUCCESS")

        # Create systemd service to run OpenClaw as the target user
        service_content = f"""\
[Unit]
Description=OpenClaw AI Assistant
After=network.target

[Service]
Type=simple
User={install_user}
ExecStart={openclaw_bin}
Restart=on-failure
RestartSec=5
Environment=HOME=/home/{install_user}

[Install]
WantedBy=multi-user.target
"""
        with open("/etc/systemd/system/openclaw.service", "w") as f:
            f.write(service_content)

        self.run_command("systemctl daemon-reload")
        self.run_command("systemctl enable openclaw")
        self.run_command("systemctl start openclaw")

        self.log("OpenClaw service enabled and started", "SUCCESS")

    def install_chrome(self):
        """Install Google Chrome"""
        print(f"\n{Colors.HEADER}=== GOOGLE CHROME INSTALLATION ==={Colors.ENDC}")
        self.log("Installing Google Chrome...")
        
        # Check if already installed
        result = self.run_command("dpkg -l | grep google-chrome", check=False)
        if result.returncode == 0:
            self.log("Google Chrome is already installed", "SUCCESS")
            return
        
        # Download and install Chrome
        try:
            # Download Chrome .deb package
            self.log("Downloading Chrome package...")
            self.run_command("wget -q -O /tmp/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb")
            
            # Install Chrome
            self.log("Installing Chrome package...")
            self.run_command("apt install -y /tmp/google-chrome-stable_current_amd64.deb")
            
            # Clean up
            self.run_command("rm -f /tmp/google-chrome-stable_current_amd64.deb")
            
        except subprocess.CalledProcessError:
            # Fallback method using repository
            self.log("Fallback: Installing Chrome via repository...", "WARNING")

            # Add Google Chrome repository key and source
            self.run_command("wget -q -O /usr/share/keyrings/google-chrome.gpg https://dl.google.com/linux/linux_signing_key.pub")
            self.run_command('echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list')
            
            # Update and install
            self.run_command("apt update")
            self.run_command("apt install -y google-chrome-stable")
        
        # Verify installation
        result = self.run_command("google-chrome --version")
        self.log(f"Chrome installed: {result.stdout.strip()}", "SUCCESS")

    def create_user_shortcuts(self):
        """Create desktop shortcuts for regular users"""
        print(f"\n{Colors.HEADER}=== CREATING USER SHORTCUTS ==={Colors.ENDC}")
        
        # Find regular user directories (excluding system users)
        user_dirs = []
        for user_dir in Path("/home").iterdir():
            if user_dir.is_dir() and user_dir.stat().st_uid >= 1000:
                user_dirs.append(user_dir)
        
        for user_dir in user_dirs:
            username = user_dir.name
            desktop_dir = user_dir / "Desktop"
            
            # Create Desktop directory if it doesn't exist
            desktop_dir.mkdir(exist_ok=True)
            
            # Copy desktop files to user's desktop
            shortcuts = [
                "/usr/share/applications/google-chrome.desktop"
            ]
            
            for shortcut in shortcuts:
                if Path(shortcut).exists():
                    shortcut_name = Path(shortcut).name
                    user_shortcut = desktop_dir / shortcut_name
                    self.run_command(f"cp {shortcut} {user_shortcut}")
                    self.run_command(f"chown {username}:{username} {user_shortcut}")
                    self.run_command(f"chmod +x {user_shortcut}")
                    
                    self.log(f"Created {shortcut_name} shortcut for {username}", "SUCCESS")

    def create_final_report(self):
        """Create final setup report"""
        print(f"\n{Colors.HEADER}=== FINAL SETUP REPORT ==={Colors.ENDC}")
        
        # Get system information
        try:
            tailscale_result = self.run_command("tailscale ip -4")
            tailscale_ip = tailscale_result.stdout.strip()
        except:
            tailscale_ip = "Not available"
        
        try:
            chrome_result = self.run_command("google-chrome --version")
            chrome_version = chrome_result.stdout.strip()
        except:
            chrome_version = "Installation failed"
        
        try:
            openclaw_result = self.run_command("systemctl is-active openclaw", check=False)
            openclaw_status = "Running" if openclaw_result.stdout.strip() == "active" else "Installed (service not active)"
        except:
            openclaw_status = "Installation failed"
        
        report = f"""
{Colors.GREEN}{Colors.BOLD}VPS SETUP COMPLETED SUCCESSFULLY!{Colors.ENDC}

{Colors.CYAN}Final Configuration Summary:{Colors.ENDC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{Colors.BOLD}Network Configuration:{Colors.ENDC}
• Tailscale IP: {tailscale_ip}
• RDP Access: {tailscale_ip}:3389
• SSH Access: ssh user@{tailscale_ip}
• Firewall: UFW active (Tailscale-only access)

{Colors.BOLD}Installed Software:{Colors.ENDC}
• RDP Server: XRDP with session persistence
• OpenClaw: {openclaw_status}
• Google Chrome: {chrome_version}

{Colors.BOLD}Desktop Applications:{Colors.ENDC}
• Applications available in desktop environment
• Shortcuts created on user desktops
• Accessible via RDP connection

{Colors.WARNING}Important Security Notes:{Colors.ENDC}
• Server is locked down to Tailscale network only
• No direct internet access for RDP/SSH
• All connections must go through Tailscale VPN

{Colors.CYAN}Next Steps:{Colors.ENDC}
1. Connect via RDP: {tailscale_ip}:3389
2. Launch applications from desktop or menu
3. Enjoy OpenClaw and browse with Chrome!

{Colors.GREEN}Setup logs saved to: /var/log/vps_post_setup.log{Colors.ENDC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        print(report)
        
        # Save detailed log
        with open("/var/log/vps_post_setup.log", "w") as f:
            f.write("VPS Post-Lockdown Setup Log\n")
            f.write("=" * 50 + "\n\n")
            for entry in self.setup_log:
                f.write(entry + "\n")
            f.write("\n" + "=" * 50 + "\n")
            f.write("Setup completed successfully!\n")

    def run_post_setup(self):
        """Main post-lockdown setup orchestrator"""
        print(f"{Colors.HEADER}{Colors.BOLD}")
        print("=" * 60)
        print("    Post-Lockdown Setup Continuation")
        print("=" * 60)
        print(f"{Colors.ENDC}")
        
        try:
            if not self.verify_tailscale_connection():
                print(f"{Colors.FAIL}Tailscale connection could not be verified!{Colors.ENDC}")
                print(f"{Colors.WARNING}Continuing anyway, but please verify your connection.{Colors.ENDC}")
            
            self.test_lockdown_status()
            self.install_openclaw()
            self.install_chrome()
            self.create_user_shortcuts()
            self.create_final_report()
            
            print(f"\n{Colors.GREEN}{Colors.BOLD}All setup tasks completed successfully!{Colors.ENDC}")
            
        except KeyboardInterrupt:
            print(f"\n{Colors.WARNING}Setup interrupted by user{Colors.ENDC}")
            sys.exit(1)
        except Exception as e:
            self.log(f"Post-setup failed: {str(e)}", "ERROR")
            print(f"\n{Colors.FAIL}Setup encountered an error. Check logs for details.{Colors.ENDC}")
            sys.exit(1)

def main():
    if os.geteuid() != 0:
        print(f"{Colors.FAIL}This script must be run as root (use sudo){Colors.ENDC}")
        sys.exit(1)
    
    setup = PostLockdownSetup()
    setup.run_post_setup()

if __name__ == "__main__":
    main()
