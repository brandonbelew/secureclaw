## Setup

**main (stable)**
```bash
curl -fsSL https://raw.githubusercontent.com/brandonbelew/secureclaw/main/install.sh -o /tmp/sc-install.sh && sudo bash /tmp/sc-install.sh
```

**dev (latest)**
```bash
curl -fsSL https://raw.githubusercontent.com/brandonbelew/secureclaw/dev/install.sh -o /tmp/sc-install.sh && sudo bash /tmp/sc-install.sh dev
```

> **Tested on:** Rocky Linux 10 (server), Fedora Server 44, and Ubuntu Server 24.04 LTS.

> **Heads up:** on systems using GNOME Remote Desktop as the RDP backend (e.g. Rocky/RHEL 10, which has no Xorg), the server automatically **reboots** as the last step of setup — GRD only activates cleanly after a fresh boot. Your SSH session will drop; give it about a minute, then reconnect over Tailscale and RDP in.

### Which installation to use

SecureClaw is built for **servers**, and a fresh, headless **server install** is the recommended and best-tested target. The installer provisions the remote desktop, installs an AI agent, and hardens the machine so it is reachable only over your private Tailscale network.

Partway through setup you'll be asked which AI agent to install:

- **[OpenClaw](https://openclaw.ai)** — the default
- **[Hermes Agent](https://hermes-agent.nousresearch.com)** — Nous Research's open-source agent

Both are installed by running the vendor's own official installer (`curl | bash`) unmodified — SecureClaw doesn't fork or patch either one, it just orchestrates the surrounding server setup (RDP, Tailscale, firewall lockdown) around whichever one you pick. Both get the same treatment: single-pass install, the desktop control-panel widget (which shows the right branding and status commands for whichever agent you picked), and Tailscale-only lockdown.

If you are setting up a **desktop edition of Linux on a machine in your home**, you most likely do not need this script. Its core features — Tailscale VPN, remote desktop (RDP), and the Tailscale-only firewall lockdown — exist to provide secure remote access to a server. On a machine you sit in front of, that remote-access layer adds little value, and you can simply install [OpenClaw](https://openclaw.ai) or [Hermes Agent](https://hermes-agent.nousresearch.com) directly instead.
