# Contributing to Ubuntu VPS Tailscale Setup

Thanks for your interest in contributing! This project aims to make secure VPS setup accessible to everyone.

## 🎯 Project Goals

- **Universal Access**: Support both SSH and RDP initial connections
- **Security First**: Zero-trust network access via Tailscale
- **User Friendly**: Clear feedback and error handling  
- **Production Ready**: Reliable automation for real-world use

## 🚀 How to Contribute

### Reporting Issues
- Use the [issue template](https://github.com/brandonbelew/secure-vps/issues/new)
- Include environment details (OS, cloud provider, access method)
- Attach relevant log files from `/var/log/`
- Test on a fresh VPS if possible

### Suggesting Features
- Check existing issues first
- Describe the use case and benefit
- Consider security implications
- Provide implementation ideas if possible

### Code Contributions

#### Development Setup
```bash
git clone https://github.com/brandonbelew/secure-vps.git
cd ubuntu-vps-tailscale-setup

# Test locally (requires Ubuntu with sudo)
sudo python3 scripts/universal_vps_setup.py
```

#### Code Standards
- **Python 3.8+** compatibility
- **PEP 8** formatting (use `black` formatter)
- **Type hints** for new functions
- **Docstrings** for all public methods
- **Error handling** with specific exceptions

#### Testing
- Test on fresh Ubuntu 20.04+ VPS
- Verify both SSH and RDP access scenarios  
- Check that all applications install correctly
- Confirm security lockdown works properly
- Test recovery procedures

### Areas Needing Help

#### High Priority
- [ ] **Additional Linux Distributions**
  - Debian 11/12 support
  - CentOS Stream 9
  - Rocky Linux 9
  
- [ ] **More Applications**  
  - VS Code installation
  - Discord client
  - Steam gaming platform
  - Development tools (Node.js, Docker)

- [ ] **Enhanced Error Recovery**
  - Automatic retry logic
  - Better network failure handling
  - Rollback procedures for failed installs

#### Medium Priority
- [ ] **Configuration Management**
  - Ansible playbook version
  - Docker containerization
  - Terraform integration
  
- [ ] **Monitoring & Logging**
  - Structured JSON logging
  - Health check endpoints
  - Performance metrics

- [ ] **User Experience**
  - Web-based setup interface
  - Mobile app for monitoring
  - Better progress indicators

#### Documentation
- [ ] Video tutorials for common scenarios
- [ ] More cloud provider guides
- [ ] Security best practices guide
- [ ] Troubleshooting flowcharts

## 🧪 Testing Guidelines

### Test Environments
1. **Fresh VPS**: Always test on clean Ubuntu installation
2. **Network Isolation**: Verify Tailscale-only access works
3. **Multi-Device**: Test connections from different clients
4. **Recovery**: Test error scenarios and recovery procedures

### Test Cases
- [ ] SSH-only VPS (DigitalOcean style)
- [ ] RDP-enabled VPS (managed provider)
- [ ] Slow network connections
- [ ] Limited disk space scenarios
- [ ] Firewall conflicts
- [ ] Tailscale authentication failures

### Security Testing
- [ ] Nmap scans show no open ports (except via Tailscale)
- [ ] SSH only accessible via Tailscale network
- [ ] RDP only accessible via Tailscale network
- [ ] UFW rules properly configured
- [ ] No unintended service exposure

## 📝 Pull Request Process

1. **Fork** the repository
2. **Create feature branch** from `main`
3. **Make changes** with tests
4. **Update documentation** as needed
5. **Submit PR** with clear description
6. **Respond to feedback** promptly

### PR Template
```
## Changes Made
- Brief description of changes
- Rationale for the changes

## Testing Done
- [ ] Tested on fresh Ubuntu VPS
- [ ] Verified SSH access scenario
- [ ] Verified RDP access scenario  
- [ ] Confirmed security lockdown works
- [ ] All applications install correctly

## Documentation Updated
- [ ] README updated if needed
- [ ] Code comments added
- [ ] New features documented

## Breaking Changes
- None / List any breaking changes
```

## 🛡️ Security Considerations

### Code Review Focus
- **Input validation** for all user inputs
- **Command injection** prevention
- **File permissions** and ownership
- **Network security** configurations
- **Credential handling** (never log secrets)

### Security Guidelines  
- Never disable security features by default
- Prefer allowlists over denylists
- Use system package managers when possible
- Validate all downloads (checksums, signatures)
- Follow principle of least privilege

## 🏗️ Architecture Overview

### Core Components
- `universal_vps_setup.py`: Main setup orchestrator
- `post_lockdown_setup.py`: SSH user continuation
- `install.sh`: Bootstrap installer

### Key Classes
- `UniversalVPSSetup`: Main setup logic
- Environment detection methods
- User interface adaptation
- Security configuration

### Extension Points
- Application installer framework
- Cloud provider detection
- Custom configuration hooks
- Plugin architecture (future)

## 💬 Communication

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas  
- **Pull Requests**: Code contributions
- **Email**: Open a GitHub issue for security concerns (private repo during testing)

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Recognition

Contributors will be:
- Listed in README acknowledgments
- Tagged in release notes for significant contributions
- Invited to join maintainer team for ongoing contributors

---

**Happy contributing! 🎉**
