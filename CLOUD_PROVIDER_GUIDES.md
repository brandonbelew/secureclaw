# Cloud Provider Setup Guides

Quick setup instructions for popular VPS providers.

## DigitalOcean

### 1. Create Droplet
- **Image**: Ubuntu 22.04 Desktop
- **Size**: Minimum 2GB RAM (4GB recommended)
- **Region**: Choose closest to you
- **Authentication**: SSH Key recommended

### 2. Initial Connection
```bash
# SSH to your droplet
ssh root@your-droplet-ip

# Run the installer
wget -O - https://raw.githubusercontent.com/brandonbelew/secure-vps/main/install.sh | sudo bash
```

### 3. Post-Setup Access
```bash
# After lockdown, use Tailscale IP
ssh user@100.64.x.x
```

---

## Linode

### 1. Create Linode
- **Image**: Ubuntu 22.04 LTS
- **Region**: Select preferred location
- **Plan**: Nanode 1GB minimum (2GB+ recommended)
- **Root Password**: Set strong password

### 2. Initial Connection
```bash
ssh root@your-linode-ip
wget -O - https://raw.githubusercontent.com/brandonbelew/secure-vps/main/install.sh | sudo bash
```

---

## AWS EC2

### 1. Launch Instance
- **AMI**: Ubuntu Server 22.04 LTS
- **Instance Type**: t3.small minimum (t3.medium recommended)
- **Security Group**: Allow SSH (22) initially
- **Key Pair**: Create or use existing

### 2. Initial Connection
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip
sudo su  # Switch to root
wget -O - https://raw.githubusercontent.com/brandonbelew/secure-vps/main/install.sh | bash
```

### 3. Post-Setup
- Security group rules automatically handled by UFW
- Connect via Tailscale after lockdown

---

## Vultr

### 1. Deploy Server
- **OS**: Ubuntu 22.04 x64
- **Size**: 2GB RAM minimum
- **Location**: Choose optimal region

### 2. Setup Process
```bash
ssh root@your-server-ip
wget -O - https://raw.githubusercontent.com/brandonbelew/secure-vps/main/install.sh | sudo bash
```

---

## Google Cloud Platform

### 1. Create VM Instance
- **Machine Type**: e2-standard-2 (2 vCPUs, 8GB RAM)
- **Boot Disk**: Ubuntu 22.04 LTS
- **Firewall**: Allow HTTP/HTTPS (will be locked down)

### 2. Initial Access
```bash
# Via cloud console or:
gcloud compute ssh your-instance-name

# Run installer
sudo wget -O - https://raw.githubusercontent.com/brandonbelew/secure-vps/main/install.sh | bash
```

---

## General Tips

### Before Starting
- [ ] Ensure VPS has Ubuntu Desktop (not Server)
- [ ] Have Tailscale account ready
- [ ] Note your VPS provider's recovery console access
- [ ] Consider taking a snapshot before setup

### During Setup
- [ ] Have your Tailscale login credentials ready
- [ ] Test from another device before lockdown
- [ ] Keep cloud provider console open as backup

### After Setup
- [ ] Install Tailscale on your local machine
- [ ] Connect via RDP: `100.64.x.x:3389`
- [ ] Verify applications work (OpenClaw, Chrome)

### Cost Optimization
- **DigitalOcean**: $12/month (2GB) or $24/month (4GB)
- **Linode**: $10/month (2GB) or $20/month (4GB)  
- **AWS**: $15-30/month depending on usage
- **Vultr**: $10/month (2GB) or $20/month (4GB)

### Security Notes
- Setup automatically configures UFW firewall
- Only Tailscale network access after setup
- Consider enabling cloud provider backups
- Monitor for unusual activity in Tailscale admin panel
