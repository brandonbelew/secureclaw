"""
platform_support.py — distro abstraction layer for SecureClaw installers.

SecureClaw was written for Debian/Ubuntu, but the only genuinely
distro-specific parts are: the package manager, package *names*, the firewall
stack, third-party repo setup, and a couple of group/service names. This module
isolates all of that behind a single `Platform` object so the setup scripts
(universal_vps_setup.py, post_lockdown_setup.py, local_setup.py) can run on
RHEL-family systems (Fedora, Rocky, AlmaLinux, CentOS Stream) too.

Design notes
------------
* Wired into install.sh + all three setup scripts + the widget. NOT yet
  validated on a real Rocky/Fedora box — a few mappings (firewalld rich rules,
  the Chrome/Tailscale RHEL repos, EPEL/CRB enablement) are written from docs
  and want a test pass before shipping.
* It deliberately does NOT import anything from the setup scripts. You inject the
  caller's `run_command(cmd, check=..., ...)` so logging/error handling stays in
  one place. `run_command` is expected to return an object with `.stdout` /
  `.returncode` (i.e. the same `subprocess.CompletedProcess` the scripts use).
* DISTRIBUTION: the bootstrap curls each .py individually; this file is fetched
  alongside them in install.sh (install_scripts() + the three shortcut heredocs)
  and by install_widget.sh, so a sibling `import platform_support` resolves from
  /usr/local/bin at runtime.
"""

import subprocess


# ── Family detection ───────────────────────────────────────────────────────────

DEBIAN_IDS = {"debian", "ubuntu", "linuxmint", "pop", "raspbian"}
RHEL_IDS = {"fedora", "rhel", "centos", "rocky", "almalinux", "ol"}  # ol = Oracle


def detect_family(os_info):
    """Return 'debian' or 'rhel' from an /etc/os-release dict.

    os_info is the dict the scripts already build in _detect_os_info().
    Falls back through ID -> ID_LIKE so derivatives we don't name explicitly
    still resolve (e.g. an Ubuntu remix with ID_LIKE="ubuntu debian").
    """
    idv = (os_info.get("ID") or "").lower()
    if idv in DEBIAN_IDS:
        return "debian"
    if idv in RHEL_IDS:
        return "rhel"

    like = (os_info.get("ID_LIKE") or "").lower().split()
    if any(x in DEBIAN_IDS or x == "debian" for x in like):
        return "debian"
    if any(x in RHEL_IDS or x in ("rhel", "fedora") for x in like):
        return "rhel"

    return "debian"  # safe historical default


# ── Logical package-name map ────────────────────────────────────────────────────
# Key on a logical name; value is {family: "space separated real package names"}.
# Anything not in this map is assumed to have the same name on both families
# (e.g. curl, wget, xrdp, cmake, make, nodejs, google-chrome-stable).

PACKAGE_MAP = {
    "tk":            {"debian": "python3-tk",                 "rhel": "python3-tkinter"},
    "gobject_gtk3":  {"debian": "python3-gi gir1.2-gtk-3.0",  "rhel": "python3-gobject gtk3"},
    "buildtools":    {"debian": "build-essential g++",        "rhel": "gcc gcc-c++ make"},
    "gnupg":         {"debian": "gnupg2",                     "rhel": "gnupg2"},
    "apt_extras":    {"debian": "software-properties-common", "rhel": ""},  # no RHEL equiv
    # RHEL xfce group id differs by distro and is resolved dynamically in
    # packages(): Fedora uses the environment group @xfce-desktop-environment,
    # while EL/EPEL (Rocky/Alma/RHEL 9) only ship the group @xfce-desktop.
    "xfce":          {"debian": "xfce4 xfce4-goodies",        "rhel": "@xfce-desktop"},
    "openssh_server":{"debian": "openssh-server",             "rhel": "openssh-server"},
    # Debian's xrdp pulls in xorgxrdp automatically; Fedora/RHEL does NOT, and
    # without it an RDP session connects to a black screen.
    "xrdp":          {"debian": "xrdp",                       "rhel": "xrdp xorgxrdp"},
}


class Platform:
    def __init__(self, run_command, os_info):
        """run_command: the caller's bound run_command(cmd, check=True, ...).
        os_info: the dict from _detect_os_info() (parsed /etc/os-release)."""
        self.run = run_command
        self.os_info = os_info
        self.family = detect_family(os_info)
        self.firewall = _UFW(self) if self.family == "debian" else _Firewalld(self)

    # ── identity helpers ────────────────────────────────────────────────────
    @property
    def is_debian(self):
        return self.family == "debian"

    @property
    def is_rhel(self):
        return self.family == "rhel"

    # ── display helpers (for user-facing text) ──────────────────────────────
    @property
    def firewall_name(self):
        """Human name of the firewall stack, for info/UI text."""
        return "UFW" if self.is_debian else "firewalld"

    @property
    def upgrade_hint(self):
        """The command to suggest for keeping the system patched."""
        return "sudo apt upgrade" if self.is_debian else "sudo dnf upgrade"

    @property
    def admin_group(self):
        """Group that confers sudo: 'sudo' on Debian, 'wheel' on RHEL."""
        return "sudo" if self.is_debian else "wheel"

    @property
    def ssh_service(self):
        return "ssh" if self.is_debian else "sshd"

    def packages(self, *logical_names):
        """Translate logical names -> real package names for this family.
        Pass-through for names not in PACKAGE_MAP."""
        out = []
        for name in logical_names:
            mapped = PACKAGE_MAP.get(name, {}).get(self.family, name)
            # The XFCE desktop group id differs across the RHEL family: Fedora
            # ships it as an environment group, EL/EPEL as a plain group.
            if name == "xfce" and self.is_rhel:
                mapped = ("@xfce-desktop-environment"
                          if self.os_info.get("ID") == "fedora" else "@xfce-desktop")
            if mapped:
                out.extend(mapped.split())
        return out

    # ── package manager ─────────────────────────────────────────────────────
    def pkg_refresh(self):
        """Update the package index (apt update / dnf makecache)."""
        if self.is_debian:
            self.run("apt-get update -qq", check=False)
        else:
            self.run("dnf -y makecache", check=False)

    def pkg_upgrade(self):
        if self.is_debian:
            self.run("DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq", check=False)
        else:
            self.run("dnf -y upgrade", check=False)

    def pkg_install(self, *names, logical=False):
        """Install packages. If logical=True, names are run through packages()
        first; otherwise they're treated as already-real package names."""
        pkgs = self.packages(*names) if logical else list(names)
        if not pkgs:
            return
        joined = " ".join(pkgs)
        if self.is_debian:
            self.run(f"DEBIAN_FRONTEND=noninteractive apt-get install -y -qq {joined}")
        else:
            self.run(f"dnf -y install {joined}")

    def pkg_installed(self, pkg):
        """True if a package is installed (replaces `dpkg -l` / `rpm -qa` checks)."""
        if self.is_debian:
            r = self.run(f"dpkg -l {pkg} 2>/dev/null | grep -q '^ii'", check=False)
        else:
            r = self.run(f"rpm -q {pkg} >/dev/null 2>&1", check=False)
        return r.returncode == 0

    def pkg_install_local(self, path):
        """Install a downloaded package file (.deb on Debian, .rpm on RHEL)."""
        if self.is_debian:
            self.run(f"DEBIAN_FRONTEND=noninteractive apt-get install -y {path}")
        else:
            self.run(f"dnf -y install {path}")

    def ensure_extra_repos(self):
        """Enable distro repos needed for xrdp/xfce/etc.
        No-op on Debian. On RHEL (not Fedora) this means EPEL + CRB, which is
        where xrdp and the XFCE group live."""
        if self.is_debian:
            return
        if self.os_info.get("ID") == "fedora":
            return  # xfce/xrdp are in Fedora's default repos
        # Rocky/Alma/RHEL/CentOS Stream. dnf-plugins-core provides
        # `config-manager`, which is NOT on a minimal install but is needed to
        # enable CRB below; install it alongside epel-release.
        self.run("dnf -y install epel-release dnf-plugins-core", check=False)
        # CodeReady Builder (named 'crb' on EL9+, 'powertools' on EL8) — some
        # EPEL packages depend on it. Try both; ignore the one that doesn't exist.
        self.run("dnf -y config-manager --set-enabled crb", check=False)
        self.run("dnf -y config-manager --set-enabled powertools", check=False)
        self.pkg_refresh()

    # ── third-party repos ───────────────────────────────────────────────────
    def install_chrome(self):
        """Install Google Chrome.

        Debian: direct .deb download (fast path) with a signed apt-repo
        fallback — mirrors the original behaviour. RHEL: the official .rpm,
        which also drops the google-chrome yum repo for future updates."""
        if self.is_rhel:
            self.run(
                "dnf -y install "
                "https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm"
            )
            return
        try:
            self.run("wget -q -O /tmp/google-chrome.deb "
                     "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb")
            self.pkg_install_local("/tmp/google-chrome.deb")
            self.run("rm -f /tmp/google-chrome.deb", check=False)
        except subprocess.CalledProcessError:
            # Fallback: add the signed apt repo and install from it
            self.run("wget -q -O /usr/share/keyrings/google-chrome.gpg "
                     "https://dl.google.com/linux/linux_signing_key.pub")
            self.run(
                "echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] "
                "http://dl.google.com/linux/chrome/deb/ stable main' "
                "> /etc/apt/sources.list.d/google-chrome.list"
            )
            self.pkg_refresh()
            self.pkg_install("google-chrome-stable")

    def install_node(self, major="22"):
        """NodeSource publishes both deb and rpm setup scripts.

        Also installs the build toolchain + git, which OpenClaw's installer and
        Homebrew both need. git ships on most Debian images but NOT on Fedora
        Server, so it must be installed explicitly."""
        if self.is_debian:
            self.run(f"curl -fsSL https://deb.nodesource.com/setup_{major}.x | bash -")
            self.pkg_install("nodejs")
        else:
            self.run(f"curl -fsSL https://rpm.nodesource.com/setup_{major}.x | bash -")
            self.pkg_install("nodejs")
        self.pkg_install("buildtools", "cmake", "python3", "git", logical=True)

    def add_tailscale_repo(self):
        """Tailscale publishes per-distro repo files. Debian keys off the
        codename; RHEL drops a .repo into /etc/yum.repos.d.

        We curl the .repo file directly rather than using `dnf config-manager
        --add-repo`, because dnf5 (Fedora 41+) renamed that to `addrepo
        --from-repofile=` while dnf4 (EL8/9) still uses `--add-repo`. A plain
        curl works on both. Note the Fedora repo path is NOT versioned, but the
        RHEL/Rocky/Alma path IS keyed by major release."""
        if self.is_debian:
            codename = self._debian_codename()
            self.run(
                f"curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/{codename}.noarmor.gpg "
                "| tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null"
            )
            self.run(
                f"curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/{codename}.tailscale-keyring.list "
                "| tee /etc/apt/sources.list.d/tailscale.list >/dev/null"
            )
            self.pkg_refresh()
        elif self.os_info.get("ID") == "fedora":
            self.run(
                "curl -fsSL https://pkgs.tailscale.com/stable/fedora/tailscale.repo "
                "-o /etc/yum.repos.d/tailscale.repo"
            )
        else:
            # RHEL / Rocky / AlmaLinux / CentOS Stream — versioned by major release
            ver = self.os_info.get("VERSION_ID", "").split(".")[0]
            self.run(
                f"curl -fsSL https://pkgs.tailscale.com/stable/rhel/{ver}/tailscale.repo "
                "-o /etc/yum.repos.d/tailscale.repo"
            )
        self.pkg_install("tailscale")

    # ── firewall status (for verification checks) ───────────────────────────
    def firewall_active(self):
        """True if the host firewall is up (ufw active / firewalld running)."""
        if self.is_debian:
            r = self.run("ufw status verbose", check=False)
            return "Status: active" in (r.stdout or "")
        r = self.run("systemctl is-active firewalld", check=False)
        return (r.stdout or "").strip() == "active"

    def firewall_rules_text(self):
        """Human-readable dump of active firewall rules (for grepping subnets)."""
        if self.is_debian:
            return (self.run("ufw status verbose", check=False).stdout or "")
        zones = (self.run("firewall-cmd --list-all-zones", check=False).stdout or "")
        rich = (self.run("firewall-cmd --list-rich-rules", check=False).stdout or "")
        return zones + "\n" + rich

    def security_check_firewall_fragments(self):
        """Return (fw_check, fw_fix) bash fragments for the security-check tool,
        selected for the host firewall stack (ufw on Debian, firewalld on RHEL).

        Contract honoured by both:
          * read live firewall state into $fw_out
          * set FIX_FW / FIX_FW6 / FIX_TS_RULE / FIX_SSH_RULE / FIX_RDP_RULE
          * fw_fix applies any requested fixes and sets fw_changed=1 + reloads
        """
        if not self.is_rhel:
            fw_check = r"""# ── Firewall ──────────────────────────────────────────────────────────────────
section "Firewall (UFW)"
fw_out=$(ufw status verbose 2>/dev/null)
if echo "$fw_out" | grep -q "Status: active"; then
    pass "UFW is active"
else
    fail "UFW is NOT active — server is unprotected!"; FIX_FW=1
fi
if grep -q "^IPV6=yes" /etc/default/ufw 2>/dev/null; then
    pass "UFW IPv6 filtering is enabled"
else
    fail "UFW IPv6 filtering is disabled — IPv6 traffic may be unprotected!"; FIX_FW6=1
fi
if echo "$fw_out" | grep -q "tailscale0"; then
    pass "Tailscale interface rules present"
else
    fail "Tailscale interface rules missing"; FIX_TS_RULE=1
fi
if echo "$fw_out" | grep -qE "100\.64\.0\.0/10.*22|22.*100\.64\.0\.0/10"; then
    pass "SSH (22) restricted to Tailscale IPv4 subnet"
else
    fail "SSH (22) does not have a Tailscale IPv4 rule"; FIX_SSH_RULE=1
fi
if echo "$fw_out" | grep -qE "fd7a:115c:a1e0::/48.*22|22.*fd7a:115c:a1e0::/48"; then
    pass "SSH (22) restricted to Tailscale IPv6 subnet"
else
    fail "SSH (22) does not have a Tailscale IPv6 rule"; FIX_SSH_RULE=1
fi
if echo "$fw_out" | grep -qE "100\.64\.0\.0/10.*3389|3389.*100\.64\.0\.0/10"; then
    pass "RDP (3389) restricted to Tailscale IPv4 subnet"
else
    fail "RDP (3389) does not have a Tailscale IPv4 rule"; FIX_RDP_RULE=1
fi
if echo "$fw_out" | grep -qE "fd7a:115c:a1e0::/48.*3389|3389.*fd7a:115c:a1e0::/48"; then
    pass "RDP (3389) restricted to Tailscale IPv6 subnet"
else
    fail "RDP (3389) does not have a Tailscale IPv6 rule"; FIX_RDP_RULE=1
fi"""

            fw_fix = r"""        if [ "$FIX_FW" -eq 1 ]; then
            echo -e "  → Enabling UFW..."
            ufw --force enable && fix_ok "UFW enabled" || fix_err "Failed to enable UFW"
            fw_changed=1
        fi

        if [ "$FIX_FW6" -eq 1 ]; then
            echo -e "  → Enabling UFW IPv6 filtering..."
            sed -i 's/^IPV6=no/IPV6=yes/' /etc/default/ufw
            grep -q '^IPV6=' /etc/default/ufw || echo 'IPV6=yes' >> /etc/default/ufw
            fix_ok "UFW IPv6 filtering enabled"
            fw_changed=1
        fi

        if [ "$FIX_TS_RULE" -eq 1 ]; then
            echo -e "  → Adding Tailscale interface rules..."
            ufw allow in on tailscale0 && \
            ufw allow out on tailscale0 && \
            fix_ok "Tailscale interface rules added" || fix_err "Failed to add Tailscale rules"
            fw_changed=1
        fi

        if [ "$FIX_SSH_RULE" -eq 1 ]; then
            echo -e "  → Restricting SSH to Tailscale subnets (IPv4 + IPv6)..."
            ufw delete allow 22/tcp  2>/dev/null || true
            ufw delete allow 22      2>/dev/null || true
            ufw delete allow OpenSSH 2>/dev/null || true
            ufw allow from 100.64.0.0/10       to any port 22 proto tcp && \
            ufw allow from fd7a:115c:a1e0::/48 to any port 22 proto tcp && \
                fix_ok "SSH restricted to Tailscale (IPv4 + IPv6)" || fix_err "Failed to restrict SSH"
            fw_changed=1
        fi

        if [ "$FIX_RDP_RULE" -eq 1 ]; then
            echo -e "  → Restricting RDP to Tailscale subnets (IPv4 + IPv6)..."
            ufw delete allow 3389/tcp 2>/dev/null || true
            ufw delete allow 3389     2>/dev/null || true
            ufw allow from 100.64.0.0/10       to any port 3389 proto tcp && \
            ufw allow from fd7a:115c:a1e0::/48 to any port 3389 proto tcp && \
                fix_ok "RDP restricted to Tailscale (IPv4 + IPv6)" || fix_err "Failed to restrict RDP"
            fw_changed=1
        fi

        if [ "$fw_changed" -eq 1 ]; then
            echo -e "  → Reloading UFW..."
            ufw --force reload && fix_ok "UFW reloaded" || fix_err "UFW reload failed"
        fi"""
            return fw_check, fw_fix

        # ── RHEL family: firewalld ──────────────────────────────────────────
        # firewalld is zone-based: default zone 'drop' = deny incoming, the
        # tailscale0 interface lives in the 'trusted' zone, and per-subnet
        # access is expressed as rich rules. IPv6 is filtered natively, so
        # there is no separate IPv6 toggle (FIX_FW6 stays 0).
        fw_check = r"""# ── Firewall ──────────────────────────────────────────────────────────────────
section "Firewall (firewalld)"
if systemctl is-active --quiet firewalld; then
    pass "firewalld is active"
else
    fail "firewalld is NOT active — server is unprotected!"; FIX_FW=1
fi
fw_out=$(firewall-cmd --list-all-zones 2>/dev/null)
rich=$(firewall-cmd --list-rich-rules 2>/dev/null)
if [ "$(firewall-cmd --get-default-zone 2>/dev/null)" = "drop" ]; then
    pass "Default zone is 'drop' (incoming denied)"
else
    fail "Default zone is not 'drop' — incoming traffic may be allowed!"; FIX_FW=1
fi
pass "IPv6 filtering handled natively by firewalld"
if firewall-cmd --zone=trusted --list-interfaces 2>/dev/null | grep -qw tailscale0; then
    pass "Tailscale interface is in the trusted zone"
else
    fail "Tailscale interface not in trusted zone"; FIX_TS_RULE=1
fi
if echo "$rich" | grep 'family="ipv4"' | grep '100.64.0.0/10' | grep -q 'port="22"'; then
    pass "SSH (22) restricted to Tailscale IPv4 subnet"
else
    fail "SSH (22) does not have a Tailscale IPv4 rule"; FIX_SSH_RULE=1
fi
if echo "$rich" | grep 'family="ipv6"' | grep 'fd7a:115c:a1e0::/48' | grep -q 'port="22"'; then
    pass "SSH (22) restricted to Tailscale IPv6 subnet"
else
    fail "SSH (22) does not have a Tailscale IPv6 rule"; FIX_SSH_RULE=1
fi
if echo "$rich" | grep 'family="ipv4"' | grep '100.64.0.0/10' | grep -q 'port="3389"'; then
    pass "RDP (3389) restricted to Tailscale IPv4 subnet"
else
    fail "RDP (3389) does not have a Tailscale IPv4 rule"; FIX_RDP_RULE=1
fi
if echo "$rich" | grep 'family="ipv6"' | grep 'fd7a:115c:a1e0::/48' | grep -q 'port="3389"'; then
    pass "RDP (3389) restricted to Tailscale IPv6 subnet"
else
    fail "RDP (3389) does not have a Tailscale IPv6 rule"; FIX_RDP_RULE=1
fi"""

        fw_fix = r"""        if [ "$FIX_FW" -eq 1 ]; then
            echo -e "  → Enabling firewalld and setting default zone to drop..."
            systemctl enable --now firewalld && \
            firewall-cmd --set-default-zone=drop && \
                fix_ok "firewalld enabled, default zone = drop" || fix_err "Failed to enable firewalld"
            fw_changed=1
        fi

        if [ "$FIX_TS_RULE" -eq 1 ]; then
            echo -e "  → Adding Tailscale interface to trusted zone..."
            firewall-cmd --permanent --zone=trusted --add-interface=tailscale0 && \
                fix_ok "Tailscale interface trusted" || fix_err "Failed to trust tailscale0"
            fw_changed=1
        fi

        if [ "$FIX_SSH_RULE" -eq 1 ]; then
            echo -e "  → Restricting SSH to Tailscale subnets (IPv4 + IPv6)..."
            firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=100.64.0.0/10 port port=22 protocol=tcp accept' && \
            firewall-cmd --permanent --add-rich-rule='rule family=ipv6 source address=fd7a:115c:a1e0::/48 port port=22 protocol=tcp accept' && \
                fix_ok "SSH restricted to Tailscale (IPv4 + IPv6)" || fix_err "Failed to restrict SSH"
            fw_changed=1
        fi

        if [ "$FIX_RDP_RULE" -eq 1 ]; then
            echo -e "  → Restricting RDP to Tailscale subnets (IPv4 + IPv6)..."
            firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=100.64.0.0/10 port port=3389 protocol=tcp accept' && \
            firewall-cmd --permanent --add-rich-rule='rule family=ipv6 source address=fd7a:115c:a1e0::/48 port port=3389 protocol=tcp accept' && \
                fix_ok "RDP restricted to Tailscale (IPv4 + IPv6)" || fix_err "Failed to restrict RDP"
            fw_changed=1
        fi

        if [ "$fw_changed" -eq 1 ]; then
            echo -e "  → Reloading firewalld..."
            firewall-cmd --reload && fix_ok "firewalld reloaded" || fix_err "firewalld reload failed"
        fi"""
        return fw_check, fw_fix

    def _debian_codename(self):
        """VERSION_CODENAME from os-release, falling back to lsb_release."""
        cn = self.os_info.get("VERSION_CODENAME")
        if cn:
            return cn
        try:
            r = subprocess.run("lsb_release -cs", shell=True, capture_output=True,
                               text=True, check=True)
            return r.stdout.strip()
        except Exception:
            return "jammy"


# ── Firewall back-ends ──────────────────────────────────────────────────────────
# Both expose the same surface the lockdown routine needs:
#   reset(), default_deny_incoming(), trust_interface(iface),
#   allow_from_to_port(subnet, port, family), enable()
# Call them in the same order the current ufw block uses.

class _UFW:
    """Debian/Ubuntu — thin wrapper over the existing ufw commands."""
    def __init__(self, plat):
        self.run = plat.run

    def reset(self):
        # keep the existing IPv6 toggle so IPv6 rules actually apply
        self.run("sed -i 's/^IPV6=no/IPV6=yes/' /etc/default/ufw", check=False)
        self.run("ufw --force reset")

    def default_deny_incoming(self):
        self.run("ufw default deny incoming")
        self.run("ufw default allow outgoing")

    def trust_interface(self, iface):
        self.run(f"ufw allow in on {iface}")
        self.run(f"ufw allow out on {iface}")

    def allow_from_to_port(self, subnet, port, family=None):
        self.run(f"ufw allow from {subnet} to any port {port}")

    def enable(self):
        self.run("ufw --force enable")


class _Firewalld:
    """RHEL family — firewalld is zone-based, so the model is different:
      * default zone -> drop (≈ deny incoming)
      * put the tailscale iface in the 'trusted' zone (≈ allow in on tailscale0)
      * rich rules for the specific Tailscale CGNAT subnets + ports
    All --permanent, then a single reload at enable()."""
    def __init__(self, plat):
        self.run = plat.run

    def reset(self):
        self.run("systemctl enable --now firewalld", check=False)
        # start from a clean default zone
        self.run("firewall-cmd --permanent --zone=public --remove-service=ssh", check=False)

    def default_deny_incoming(self):
        self.run("firewall-cmd --set-default-zone=drop")

    def trust_interface(self, iface):
        self.run(f"firewall-cmd --permanent --zone=trusted --add-interface={iface}")

    def allow_from_to_port(self, subnet, port, family=None):
        fam = family or ("ipv6" if ":" in subnet else "ipv4")
        self.run(
            "firewall-cmd --permanent --add-rich-rule="
            f"'rule family={fam} source address={subnet} "
            f"port port={port} protocol=tcp accept'"
        )

    def enable(self):
        self.run("firewall-cmd --reload")


# ─────────────────────────────────────────────────────────────────────────────
# To distribute this module, add it everywhere the .py scripts are fetched:
#   install.sh  -> install_scripts():      curl .../ubuntu/platform_support.py
#   install.sh  -> create_shortcuts():     add to vps-setup / vps-post-setup /
#                                          local-setup heredocs next to the
#                                          existing per-script curl lines
# and `import platform_support` (or `from platform_support import Platform`)
# at the top of each setup script. Because /usr/local/bin is on sys.path for a
# script run from there, a sibling module there imports cleanly.
# ─────────────────────────────────────────────────────────────────────────────
