#!/usr/bin/env python3
"""
Universal Ubuntu VPS Setup Script
Handles both SSH and RDP initial access scenarios
Configures RDP, Tailscale, security lockdown, and installs OpenClaw + Chrome
Author: Brandon
"""

import os
import sys
import subprocess
import time
from pathlib import Path
import getpass
import tkinter as tk
from tkinter import messagebox, simpledialog
import threading

class Colors:
    """Terminal colors for better UX"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class UniversalVPSSetup:
    def __init__(self):
        self.tailscale_ip = None
        self.setup_log = []
        self.is_desktop_env = self.detect_desktop_environment()
        self.gui_available = self.is_desktop_env and self.check_display()
        self.initial_access_method = self.detect_access_method()
        
    def detect_desktop_environment(self):
        """Detect if we're running in a desktop environment"""
        desktop_indicators = [
            'DESKTOP_SESSION',
            'GDMSESSION', 
            'XDG_CURRENT_DESKTOP',
            'DISPLAY'
        ]
        
        for indicator in desktop_indicators:
            if os.environ.get(indicator):
                return True
                
        # Check if X11 or Wayland is running
        if os.path.exists('/tmp/.X11-unix') or os.environ.get('WAYLAND_DISPLAY'):
            return True
            
        return False
    
    def check_display(self):
        """Check if GUI display is available"""
        try:
            # Try to create a simple tkinter window
            root = tk.Tk()
            root.withdraw()
            return True
        except:
            return False
    
    def get_os_codename(self):
        """Get the Ubuntu OS codename for repository setup"""
        try:
            result = subprocess.run("lsb_release -cs", shell=True, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return "jammy"  # fallback to 22.04

    def detect_access_method(self):
        """Detect how the user is accessing the system"""
        ssh_client = os.environ.get('SSH_CLIENT')
        ssh_connection = os.environ.get('SSH_CONNECTION')
        
        if ssh_client or ssh_connection:
            return "SSH"
        elif self.is_desktop_env:
            return "RDP"
        else:
            return "CONSOLE"

    def log(self, message, level="INFO"):
        """Log messages with timestamps and optional GUI display"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        self.setup_log.append(log_entry)
        
        # Console output
        if level == "ERROR":
            print(f"{Colors.FAIL}{log_entry}{Colors.ENDC}")
        elif level == "WARNING":
            print(f"{Colors.WARNING}{log_entry}{Colors.ENDC}")
        elif level == "SUCCESS":
            print(f"{Colors.GREEN}{log_entry}{Colors.ENDC}")
        else:
            print(f"{Colors.CYAN}{log_entry}{Colors.ENDC}")
        
        # GUI notification for important messages in RDP mode
        if self.gui_available and level in ["ERROR", "WARNING", "SUCCESS"] and self.initial_access_method == "RDP":
            try:
                root = tk.Tk()
                root.withdraw()
                if level == "ERROR":
                    messagebox.showerror("Setup Error", message)
                elif level == "WARNING":
                    messagebox.showwarning("Setup Warning", message)
                elif level == "SUCCESS":
                    messagebox.showinfo("Setup Success", message)
                root.destroy()
            except:
                pass  # GUI not available, continue with console only

    def show_startup_message(self):
        """Display appropriate startup message based on access method"""
        print(f"{Colors.HEADER}{Colors.BOLD}")
        print("=" * 70)
        print("        Universal Ubuntu VPS Interactive Setup")
        print("=" * 70)
        print(f"{Colors.ENDC}")
        
        print(f"{Colors.CYAN}Detected Environment:{Colors.ENDC}")
        print(f"  • Access Method: {Colors.BOLD}{self.initial_access_method}{Colors.ENDC}")
        print(f"  • Desktop Environment: {Colors.BOLD}{'Yes' if self.is_desktop_env else 'No'}{Colors.ENDC}")
        print(f"  • GUI Available: {Colors.BOLD}{'Yes' if self.gui_available else 'No'}{Colors.ENDC}")
        
        if self.initial_access_method == "RDP":
            print(f"\n{Colors.GREEN}RDP Mode Detected:{Colors.ENDC}")
            print("  • You're already connected via RDP")
            print("  • Script will enhance your current RDP setup")
            print("  • GUI notifications will be shown during setup")
            
            if self.gui_available:
                try:
                    root = tk.Tk()
                    root.withdraw()
                    result = messagebox.askyesno(
                        "VPS Setup", 
                        "Welcome to Ubuntu VPS Setup!\n\n"
                        "Detected: You're connected via RDP\n\n"
                        "This script will:\n"
                        "• Enhance RDP with session persistence\n"
                        "• Install and configure Tailscale VPN\n"
                        "• Lock down server security\n"
                        "• Install OpenClaw and Chrome\n\n"
                        "Continue with setup?"
                    )
                    root.destroy()
                    if not result:
                        self.log("Setup cancelled by user", "WARNING")
                        sys.exit(0)
                except:
                    pass
                    
        elif self.initial_access_method == "SSH":
            print(f"\n{Colors.GREEN}SSH Mode Detected:{Colors.ENDC}")
            print("  • You're connected via SSH")
            print("  • Script will install and configure RDP server")
            print("  • You'll test RDP before server lockdown")
            
        print(f"\n{Colors.WARNING}Important Notes:{Colors.ENDC}")
        print("  • This script requires root privileges")
        print("  • Your server will be locked down to Tailscale-only access")
        print("  • Have your Tailscale account ready (free at tailscale.com)")

    def run_command(self, command, check=True, shell=True, capture_output=True):
        """Execute shell commands with proper error handling"""
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

    def check_root(self):
        """Ensure script is run with root privileges"""
        if os.geteuid() != 0:
            error_msg = "This script must be run as root (use sudo)"
            self.log(error_msg, "ERROR")
            
            if self.gui_available and self.initial_access_method == "RDP":
                try:
                    root = tk.Tk()
                    root.withdraw()
                    messagebox.showerror(
                        "Root Access Required", 
                        f"{error_msg}\n\nPlease run from terminal:\nsudo python3 {sys.argv[0]}"
                    )
                    root.destroy()
                except:
                    pass
            
            sys.exit(1)
        self.log("Root privileges confirmed", "SUCCESS")

    def update_system(self):
        """Update package lists and upgrade system"""
        print(f"\n{Colors.HEADER}=== SYSTEM UPDATE ==={Colors.ENDC}")
        self.log("Starting system update...")
        
        if self.gui_available and self.initial_access_method == "RDP":
            self.show_gui_progress("Updating system packages...", "This may take several minutes")
        
        self.run_command("apt update", capture_output=False)
        self.run_command("apt upgrade -y", capture_output=False)
        self.run_command("apt install -y curl wget gnupg2 software-properties-common python3-tk")
        
        self.log("System update completed", "SUCCESS")

    def show_gui_progress(self, title, message):
        """Show a progress window for long-running operations"""
        if not self.gui_available:
            return
            
        def show_progress():
            try:
                progress_window = tk.Tk()
                progress_window.title(title)
                progress_window.geometry("400x150")
                progress_window.resizable(False, False)
                
                # Center the window
                progress_window.update_idletasks()
                x = (progress_window.winfo_screenwidth() // 2) - (400 // 2)
                y = (progress_window.winfo_screenheight() // 2) - (150 // 2)
                progress_window.geometry(f"400x150+{x}+{y}")
                
                label = tk.Label(progress_window, text=message, wraplength=350)
                label.pack(pady=20)
                
                progress_window.after(5000, progress_window.destroy)  # Auto-close after 5 seconds
                progress_window.mainloop()
            except:
                pass
        
        # Run in separate thread to not block main execution
        thread = threading.Thread(target=show_progress)
        thread.daemon = True
        thread.start()

    def install_rdp(self):
        """Install and configure RDP with session persistence"""
        print(f"\n{Colors.HEADER}=== RDP INSTALLATION ==={Colors.ENDC}")
        
        if self.initial_access_method == "RDP":
            self.log("Already connected via RDP, enhancing configuration...", "SUCCESS")
            response = self.get_user_input(
                "You're already using RDP. Would you like to enhance the configuration for better session persistence?",
                ["Yes, enhance RDP", "Skip RDP configuration"], 
                default_index=0
            )
            if response == 1:  # Skip
                self.log("RDP configuration skipped by user", "WARNING")
                return
        else:
            self.log("Installing RDP server for SSH users...", "SUCCESS")
        
        if self.gui_available:
            self.show_gui_progress("Installing RDP Server", "Setting up remote desktop access...")
        
        # Install XRDP and desktop environment if not already present
        self.run_command("apt install -y xrdp", capture_output=False)
        
        # Only install desktop if we don't detect one
        if not self.is_desktop_env:
            self.run_command("apt install -y ubuntu-desktop-minimal", capture_output=False)
        
        # Configure XRDP for session persistence
        xrdp_config = """
[Xorg]
name=Xorg
lib=libxup.so
username=ask
password=ask
ip=127.0.0.1
port=-1
code=20
"""
        
        # Backup original config
        self.run_command("cp /etc/xrdp/xrdp.ini /etc/xrdp/xrdp.ini.backup")
        
        with open("/etc/xrdp/xrdp.ini", "a") as f:
            f.write(xrdp_config)
        
        # Create .xsessionrc for persistent sessions
        xsession_config = """#!/bin/bash
export GNOME_SHELL_SESSION_MODE=ubuntu
export XDG_CURRENT_DESKTOP=ubuntu:GNOME
export XDG_CONFIG_DIRS=/etc/xdg/xdg-ubuntu:/etc/xdg
gnome-session --session=ubuntu
"""
        
        # Apply to all users
        with open("/etc/skel/.xsessionrc", "w") as f:
            f.write(xsession_config)
        
        # Configure existing users
        for user_dir in Path("/home").iterdir():
            if user_dir.is_dir():
                xsessionrc_path = user_dir / ".xsessionrc"
                with open(xsessionrc_path, "w") as f:
                    f.write(xsession_config)
                self.run_command(f"chown {user_dir.name}:{user_dir.name} {xsessionrc_path}")
                self.run_command(f"chmod +x {xsessionrc_path}")
        
        # Enable and start XRDP
        self.run_command("systemctl enable xrdp")
        self.run_command("systemctl restart xrdp")
        
        # Configure firewall for RDP (temporarily)
        self.run_command("ufw allow 3389/tcp")
        
        self.log("RDP installation/enhancement completed", "SUCCESS")

    def get_user_input(self, message, options, default_index=0):
        """Get user input via GUI or console based on environment"""
        if self.gui_available and self.initial_access_method == "RDP":
            try:
                root = tk.Tk()
                root.withdraw()
                
                # Create custom dialog
                dialog = tk.Toplevel()
                dialog.title("Setup Choice")
                dialog.geometry("500x200")
                dialog.resizable(False, False)
                
                # Center the dialog
                dialog.update_idletasks()
                x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
                y = (dialog.winfo_screenheight() // 2) - (200 // 2)
                dialog.geometry(f"500x200+{x}+{y}")
                
                result = [default_index]  # Use list for closure
                
                tk.Label(dialog, text=message, wraplength=450).pack(pady=20)
                
                button_frame = tk.Frame(dialog)
                button_frame.pack(pady=10)
                
                for i, option in enumerate(options):
                    btn = tk.Button(
                        button_frame, 
                        text=option, 
                        command=lambda idx=i: [result.__setitem__(0, idx), dialog.destroy()]
                    )
                    btn.pack(side=tk.LEFT, padx=10)
                
                dialog.wait_window()
                root.destroy()
                return result[0]
                
            except:
                pass  # Fall back to console
        
        # Console input
        print(f"\n{Colors.CYAN}{message}{Colors.ENDC}")
        for i, option in enumerate(options):
            print(f"  {i+1}. {option}")
        
        while True:
            try:
                choice = input(f"\nEnter choice (1-{len(options)}) [default: {default_index+1}]: ").strip()
                if not choice:
                    return default_index
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(options):
                    return choice_idx
                else:
                    print(f"{Colors.WARNING}Please enter a number between 1 and {len(options)}{Colors.ENDC}")
            except (ValueError, KeyboardInterrupt):
                print(f"{Colors.WARNING}Invalid input. Please enter a number.{Colors.ENDC}")

    def install_tailscale(self):
        """Install Tailscale"""
        print(f"\n{Colors.HEADER}=== TAILSCALE INSTALLATION ==={Colors.ENDC}")
        self.log("Installing Tailscale...")
        
        if self.gui_available:
            self.show_gui_progress("Installing Tailscale", "Adding repository and installing VPN client...")
        
        # Add Tailscale repository
        codename = self.get_os_codename()
        self.run_command(f"curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/{codename}.noarmor.gpg | tee /usr/share/keyrings/tailscale-archive-keyring.gpg > /dev/null")
        self.run_command(f'curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/{codename}.tailscale-keyring.list | tee /etc/apt/sources.list.d/tailscale.list')
        
        # Install Tailscale
        self.run_command("apt update")
        self.run_command("apt install -y tailscale")
        
        self.log("Tailscale installed successfully", "SUCCESS")

    def configure_tailscale(self):
        """Interactive Tailscale configuration"""
        print(f"\n{Colors.HEADER}=== TAILSCALE CONFIGURATION ==={Colors.ENDC}")
        
        message = ("Tailscale setup requires authentication with your Tailscale account.\n"
                  "If you don't have an account, create one at https://tailscale.com")
        
        if self.gui_available and self.initial_access_method == "RDP":
            try:
                root = tk.Tk()
                root.withdraw()
                messagebox.showinfo("Tailscale Setup", message)
                root.destroy()
            except:
                pass
        
        print(f"{Colors.CYAN}{message}{Colors.ENDC}")
        
        proceed = self.get_user_input(
            "Ready to authenticate with Tailscale?",
            ["Continue with authentication", "Skip Tailscale setup"],
            default_index=0
        )
        
        if proceed == 1:  # Skip
            self.log("Tailscale setup skipped by user", "WARNING")
            return False
        
        # Start Tailscale with authentication
        try:
            self.run_command("tailscale up", capture_output=False)
        except subprocess.CalledProcessError:
            self.log("Tailscale authentication may have failed", "WARNING")
            retry = self.get_user_input(
                "Tailscale authentication failed. What would you like to do?",
                ["Retry with reset", "Continue without Tailscale", "Exit setup"],
                default_index=0
            )
            
            if retry == 0:  # Retry
                self.run_command("tailscale up --reset", capture_output=False)
            elif retry == 1:  # Continue without
                return False
            else:  # Exit
                sys.exit(0)
        
        # Get Tailscale IP
        time.sleep(5)  # Wait for IP assignment
        try:
            result = self.run_command("tailscale ip -4")
            self.tailscale_ip = result.stdout.strip()
            self.log(f"Tailscale IP assigned: {self.tailscale_ip}", "SUCCESS")
            return True
        except:
            self.log("Failed to get Tailscale IP", "ERROR")
            return False

    def test_tailscale_connection(self):
        """Test Tailscale connectivity based on access method"""
        print(f"\n{Colors.HEADER}=== TAILSCALE CONNECTION TEST ==={Colors.ENDC}")
        
        if not self.tailscale_ip:
            self.log("No Tailscale IP available for testing", "ERROR")
            return False
        
        test_message = f"Your server's Tailscale IP is: {self.tailscale_ip}"
        
        if self.initial_access_method == "SSH":
            # SSH users need to test from another device
            test_instructions = (f"Please test these connections from your home computer:\n"
                               f"• RDP: {self.tailscale_ip}:3389\n"
                               f"• SSH: ssh {getpass.getuser()}@{self.tailscale_ip}")
            
            print(f"{Colors.CYAN}{test_message}{Colors.ENDC}")
            print(f"{Colors.CYAN}{test_instructions}{Colors.ENDC}")
            
            while True:
                test_result = self.get_user_input(
                    "Can you successfully connect via RDP and SSH through Tailscale?",
                    ["Yes, connections work", "No, having issues", "Skip test (risky)"],
                    default_index=0
                )
                
                if test_result == 0:  # Yes
                    self.log("Tailscale connectivity confirmed", "SUCCESS")
                    return True
                elif test_result == 2:  # Skip
                    self.log("User chose to skip connection test", "WARNING")
                    return True
                else:  # No
                    troubleshoot = self.get_user_input(
                        "Connection issues detected. What would you like to do?",
                        ["Get troubleshooting help", "Retry test", "Continue anyway (risky)", "Exit setup"],
                        default_index=1
                    )
                    
                    if troubleshoot == 0:  # Help
                        self.show_troubleshooting_help()
                    elif troubleshoot == 1:  # Retry
                        continue
                    elif troubleshoot == 2:  # Continue
                        return True
                    else:  # Exit
                        sys.exit(0)
        
        elif self.initial_access_method == "RDP":
            # RDP users are already connected, just verify Tailscale is working
            if self.gui_available:
                try:
                    root = tk.Tk()
                    root.withdraw()
                    result = messagebox.askyesno(
                        "Tailscale Test",
                        f"{test_message}\n\n"
                        f"Tailscale should now be running.\n"
                        f"You can test SSH access from another device if desired.\n\n"
                        f"Continue with server lockdown?"
                    )
                    root.destroy()
                    if result:
                        self.log("RDP user confirmed Tailscale setup", "SUCCESS")
                        return True
                    else:
                        return False
                except:
                    pass
            
            # Console fallback
            result = self.get_user_input(
                f"{test_message}\n\nTailscale is now running. Continue with server lockdown?",
                ["Yes, continue", "No, troubleshoot first"],
                default_index=0
            )
            return result == 0
        
        return True

    def show_troubleshooting_help(self):
        """Display troubleshooting information"""
        help_text = """
TAILSCALE TROUBLESHOOTING:

1. Tailscale Client Installation:
   • Download from https://tailscale.com/download
   • Install on your home computer
   • Login with the same account used on server

2. Connection Issues:
   • Check both devices show as connected in Tailscale admin panel
   • Verify no local firewalls blocking connections
   • Try: tailscale ping [server-ip] from home computer

3. RDP Issues:
   • Use RDP client with server IP: {tailscale_ip}:3389
   • Try different RDP clients if one fails
   • Ensure server firewall allows Tailscale traffic

4. SSH Issues:
   • Command: ssh username@{tailscale_ip}
   • Check SSH service is running: systemctl status sshd
   • Verify SSH allows connections from Tailscale network
        """.format(tailscale_ip=self.tailscale_ip)
        
        if self.gui_available:
            try:
                root = tk.Tk()
                root.withdraw()
                
                # Create scrollable text window
                help_window = tk.Toplevel()
                help_window.title("Troubleshooting Help")
                help_window.geometry("600x400")
                
                text_widget = tk.Text(help_window, wrap=tk.WORD)
                scrollbar = tk.Scrollbar(help_window, orient=tk.VERTICAL, command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)
                
                text_widget.insert(tk.END, help_text)
                text_widget.config(state=tk.DISABLED)
                
                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                
                close_btn = tk.Button(help_window, text="Close", command=help_window.destroy)
                close_btn.pack(pady=10)
                
                help_window.wait_window()
                root.destroy()
            except:
                pass
        
        print(f"{Colors.CYAN}{help_text}{Colors.ENDC}")

    def lockdown_server(self):
        """Lock down server to only allow Tailscale connections"""
        print(f"\n{Colors.HEADER}=== SERVER LOCKDOWN ==={Colors.ENDC}")
        
        warning_message = ("⚠️  WARNING: Server Lockdown ⚠️\n\n"
                          "This will lock down the server to Tailscale-only access!\n"
                          "After this step, you can only connect via Tailscale network.\n\n"
                          "Make sure you tested Tailscale connections successfully.")
        
        if self.gui_available:
            try:
                root = tk.Tk()
                root.withdraw()
                result = messagebox.askyesno("Server Lockdown Warning", warning_message)
                root.destroy()
                if not result:
                    self.log("Server lockdown cancelled by user", "WARNING")
                    return False
            except:
                pass
        
        # Console confirmation
        print(f"{Colors.FAIL}{Colors.BOLD}WARNING: This will lock down the server!{Colors.ENDC}")
        print(f"{Colors.WARNING}After this step, you will only be able to connect via Tailscale.{Colors.ENDC}")
        print(f"{Colors.WARNING}Make sure you can connect via Tailscale before proceeding.{Colors.ENDC}")
        
        confirmation = input(f"\n{Colors.WARNING}Type 'LOCKDOWN' to confirm server lockdown: {Colors.ENDC}")
        if confirmation != 'LOCKDOWN':
            self.log("Server lockdown cancelled by user", "WARNING")
            return False
        
        self.log("Beginning server lockdown...")
        
        # Reset UFW and set default policies
        self.run_command("ufw --force reset")
        self.run_command("ufw default deny incoming")
        self.run_command("ufw default allow outgoing")
        
        # Allow Tailscale interface
        self.run_command("ufw allow in on tailscale0")
        self.run_command("ufw allow out on tailscale0")
        
        # Allow only Tailscale subnet for SSH and RDP
        tailscale_subnet = "100.64.0.0/10"
        self.run_command(f"ufw allow from {tailscale_subnet} to any port 22")
        self.run_command(f"ufw allow from {tailscale_subnet} to any port 3389")
        
        # Enable UFW
        self.run_command("ufw --force enable")
        
        # Configure SSH to only listen on Tailscale interface if we have the IP
        if self.tailscale_ip:
            ssh_config_addition = f"""
# Tailscale only configuration
ListenAddress {self.tailscale_ip}
"""
            
            with open("/etc/ssh/sshd_config", "a") as f:
                f.write(ssh_config_addition)
            
            self.run_command("systemctl restart sshd")
        
        self.log("Server lockdown completed", "SUCCESS")
        
        # Different behavior based on access method
        if self.initial_access_method == "SSH":
            print(f"\n{Colors.FAIL}SSH CONNECTION WILL BE LOST IN 10 SECONDS!{Colors.ENDC}")
            print(f"{Colors.WARNING}Reconnect using Tailscale IP: {self.tailscale_ip}{Colors.ENDC}")
            
            for i in range(10, 0, -1):
                print(f"{Colors.WARNING}Connection closing in {i} seconds...{Colors.ENDC}")
                time.sleep(1)
        
        elif self.initial_access_method == "RDP":
            if self.gui_available:
                try:
                    root = tk.Tk()
                    root.withdraw()
                    messagebox.showinfo(
                        "Lockdown Complete",
                        f"Server lockdown completed!\n\n"
                        f"Your server is now secure and only accessible via Tailscale.\n"
                        f"Tailscale IP: {self.tailscale_ip}\n\n"
                        f"Continuing with application installation..."
                    )
                    root.destroy()
                except:
                    pass
            
            print(f"{Colors.GREEN}Lockdown completed! Continuing with setup...{Colors.ENDC}")
        
        return True

    def install_applications(self):
        """Install OpenClaw and Chrome - shared logic for both scenarios"""
        if self.gui_available:
            self.show_gui_progress("Installing Applications", "Installing OpenClaw and Google Chrome...")
        
        # Install OpenClaw
        self.install_openclaw()
        # Install Chrome
        self.install_chrome()
        # Create shortcuts
        self.create_user_shortcuts()

    def install_openclaw(self):
        """Install OpenClaw game engine"""
        print(f"\n{Colors.HEADER}=== OPENCLAW INSTALLATION ==={Colors.ENDC}")
        self.log("Installing OpenClaw...")
        
        # Check if already installed
        if Path("/opt/openclaw").exists():
            self.log("OpenClaw directory already exists, removing...", "WARNING")
            self.run_command("rm -rf /opt/openclaw")
        
        # Install dependencies
        self.log("Installing build dependencies...")
        self.run_command("apt update")
        self.run_command("apt install -y build-essential cmake git")
        self.run_command("apt install -y libsdl2-dev libsdl2-mixer-dev libsdl2-image-dev")
        self.run_command("apt install -y libsdl2-ttf-dev libtinyxml2-dev libzzip-dev")
        self.run_command("apt install -y libpng-dev zlib1g-dev")
        
        # Create installation directory
        install_dir = "/opt/openclaw"
        self.run_command(f"mkdir -p {install_dir}")
        
        # Clone OpenClaw repository
        self.log("Cloning OpenClaw repository...")
        self.run_command(f"git clone https://github.com/pjasicek/OpenClaw.git {install_dir}")
        
        # Build OpenClaw
        self.log("Building OpenClaw (this may take several minutes)...")
        build_dir = f"{install_dir}/Build_Release"
        self.run_command(f"mkdir -p {build_dir}")
        
        # Change to build directory and compile
        original_dir = os.getcwd()
        try:
            os.chdir(build_dir)
            self.run_command("cmake -DCMAKE_BUILD_TYPE=Release ..", capture_output=False)
            self.run_command("make -j$(nproc)", capture_output=False)
            self.run_command(f"chmod +x {build_dir}/openclaw")
        finally:
            os.chdir(original_dir)
        
        # Create launcher script
        launcher_script = f"""#!/bin/bash
cd {build_dir}
./openclaw "$@"
"""
        
        with open("/usr/local/bin/openclaw", "w") as f:
            f.write(launcher_script)
        
        self.run_command("chmod +x /usr/local/bin/openclaw")
        
        # Create desktop entry
        desktop_entry = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=OpenClaw
Comment=Captain Claw Game Engine
Exec=/usr/local/bin/openclaw
Icon={install_dir}/Assets/claw.png
Terminal=false
Categories=Game;Action;
StartupNotify=true
"""
        
        with open("/usr/share/applications/openclaw.desktop", "w") as f:
            f.write(desktop_entry)
        
        self.run_command("chmod 644 /usr/share/applications/openclaw.desktop")
        
        self.log("OpenClaw installation completed successfully", "SUCCESS")

    def install_chrome(self):
        """Install Google Chrome"""
        print(f"\n{Colors.HEADER}=== GOOGLE CHROME INSTALLATION ==={Colors.ENDC}")
        self.log("Installing Google Chrome...")
        
        # Check if already installed
        result = self.run_command("dpkg -l | grep google-chrome", check=False)
        if result.returncode == 0:
            self.log("Google Chrome is already installed", "SUCCESS")
            return
        
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
            self.run_command("wget -q -O /usr/share/keyrings/google-chrome.gpg https://dl.google.com/linux/linux_signing_key.pub")
            self.run_command('echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list')
            self.run_command("apt update")
            self.run_command("apt install -y google-chrome-stable")
        
        # Verify installation
        result = self.run_command("google-chrome --version")
        self.log(f"Chrome installed: {result.stdout.strip()}", "SUCCESS")

    def create_user_shortcuts(self):
        """Create desktop shortcuts for regular users"""
        print(f"\n{Colors.HEADER}=== CREATING USER SHORTCUTS ==={Colors.ENDC}")
        
        user_dirs = []
        for user_dir in Path("/home").iterdir():
            if user_dir.is_dir() and user_dir.stat().st_uid >= 1000:
                user_dirs.append(user_dir)
        
        for user_dir in user_dirs:
            username = user_dir.name
            desktop_dir = user_dir / "Desktop"
            desktop_dir.mkdir(exist_ok=True)
            
            shortcuts = [
                "/usr/share/applications/openclaw.desktop",
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
        
        openclaw_status = "Installed" if Path("/opt/openclaw/Build_Release/openclaw").exists() else "Installation failed"
        
        report = f"""
{Colors.GREEN}{Colors.BOLD}UNIVERSAL VPS SETUP COMPLETED!{Colors.ENDC}

{Colors.CYAN}Setup Summary:{Colors.ENDC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{Colors.BOLD}Initial Access Method: {self.initial_access_method}{Colors.ENDC}

{Colors.BOLD}Network Configuration:{Colors.ENDC}
• Tailscale IP: {tailscale_ip}
• RDP Access: {tailscale_ip}:3389
• SSH Access: ssh user@{tailscale_ip}
• Security: Locked down to Tailscale-only access

{Colors.BOLD}Applications Installed:{Colors.ENDC}
• OpenClaw Game Engine: {openclaw_status}
• Google Chrome: {chrome_version}
• Desktop shortcuts created for all users

{Colors.BOLD}Access Information:{Colors.ENDC}
• RDP: Connect to {tailscale_ip}:3389 via Tailscale
• Applications available in desktop environment
• Session persistence enabled (browsers stay open)

{Colors.WARNING}Security Notes:{Colors.ENDC}
• Server locked down to Tailscale network only
• UFW firewall active with restrictive rules
• All connections must use Tailscale VPN

{Colors.GREEN}Setup completed successfully!{Colors.ENDC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        print(report)
        
        if self.gui_available and self.initial_access_method == "RDP":
            try:
                root = tk.Tk()
                root.withdraw()
                messagebox.showinfo(
                    "Setup Complete!",
                    f"Ubuntu VPS setup completed successfully!\n\n"
                    f"Tailscale IP: {tailscale_ip}\n"
                    f"OpenClaw: {openclaw_status}\n"
                    f"Chrome: Installed\n\n"
                    f"Applications are available on your desktop!"
                )
                root.destroy()
            except:
                pass
        
        # Save log
        with open("/var/log/universal_vps_setup.log", "w") as f:
            f.write("Universal VPS Setup Log\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Initial Access Method: {self.initial_access_method}\n")
            f.write(f"Desktop Environment: {'Yes' if self.is_desktop_env else 'No'}\n")
            f.write(f"GUI Available: {'Yes' if self.gui_available else 'No'}\n\n")
            for entry in self.setup_log:
                f.write(entry + "\n")

    def run_setup(self):
        """Main setup orchestrator - handles both SSH and RDP scenarios"""
        try:
            self.show_startup_message()
            
            response = self.get_user_input(
                "Ready to begin VPS setup?",
                ["Start setup", "Exit"],
                default_index=0
            )
            
            if response == 1:  # Exit
                self.log("Setup cancelled by user", "WARNING")
                sys.exit(0)
            
            self.check_root()
            self.update_system()
            self.install_rdp()
            self.install_tailscale()
            
            if self.configure_tailscale():
                if self.test_tailscale_connection():
                    if self.lockdown_server():
                        # For SSH users, we stop here and they need to reconnect
                        if self.initial_access_method == "SSH":
                            print(f"\n{Colors.GREEN}Phase 1 Complete!{Colors.ENDC}")
                            print(f"{Colors.WARNING}Reconnect via Tailscale and run the post-lockdown script{Colors.ENDC}")
                            return
                        
                        # For RDP users, continue with application installation
                        elif self.initial_access_method == "RDP":
                            self.install_applications()
                            self.create_final_report()
                else:
                    print(f"{Colors.FAIL}Setup aborted due to connectivity issues{Colors.ENDC}")
            else:
                print(f"{Colors.WARNING}Setup completed without Tailscale configuration{Colors.ENDC}")
                
        except KeyboardInterrupt:
            print(f"\n{Colors.WARNING}Setup interrupted by user{Colors.ENDC}")
            sys.exit(1)
        except Exception as e:
            self.log(f"Setup failed: {str(e)}", "ERROR")
            if self.gui_available:
                try:
                    root = tk.Tk()
                    root.withdraw()
                    messagebox.showerror("Setup Failed", f"An error occurred during setup:\n\n{str(e)}")
                    root.destroy()
                except:
                    pass
            sys.exit(1)

def main():
    setup = UniversalVPSSetup()
    setup.run_setup()

if __name__ == "__main__":
    main()
