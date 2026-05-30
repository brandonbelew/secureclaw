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
* This is a SKETCH / skeleton. The mappings are real but a few of them (notably
  firewalld rich rules and Chrome/Tailscale repos) want a hardening pass and a
  test run on an actual Rocky/Fedora box before shipping.
* It deliberately does NOT import anything from the setup scripts. You inject the
  caller's `run_command(cmd, check=..., ...)` so logging/error handling stays in
  one place. `run_command` is expected to return an object with `.stdout` /
  `.returncode` (i.e. the same `subprocess.CompletedProcess` the scripts use).
* DISTRIBUTION: the bootstrap (install.sh + the vps-setup/local-setup shortcuts)
  currently curls each .py individually. This file must be added to those fetch
  lists, or imported code will be missing at runtime. See the bottom of this
  file for the exact spots.
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
    "xfce":          {"debian": "xfce4 xfce4-goodies",        "rhel": "@xfce"},  # dnf group
    "openssh_server":{"debian": "openssh-server",             "rhel": "openssh-server"},
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

    # ── third-party repos ───────────────────────────────────────────────────
    def add_chrome_repo_and_install(self):
        """Google Chrome. RHEL has an official .rpm + yum repo; Debian uses the
        signed apt source the scripts use today."""
        if self.is_debian:
            self.run(
                "echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] "
                "http://dl.google.com/linux/chrome/deb/ stable main' "
                "> /etc/apt/sources.list.d/google-chrome.list"
            )
            self.pkg_refresh()
            self.pkg_install("google-chrome-stable")
        else:
            # Google ships a yum repo; the rpm pulls it in, or drop a .repo file.
            self.run(
                "dnf -y install "
                "https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm"
            )

    def install_node(self, major="22"):
        """NodeSource publishes both deb and rpm setup scripts."""
        if self.is_debian:
            self.run(f"curl -fsSL https://deb.nodesource.com/setup_{major}.x | bash -")
            self.pkg_install("nodejs")
        else:
            self.run(f"curl -fsSL https://rpm.nodesource.com/setup_{major}.x | bash -")
            self.pkg_install("nodejs")
        self.pkg_install("buildtools", "cmake", "python3", logical=True)

    def add_tailscale_repo(self):
        """Tailscale publishes per-distro repo files. Debian keys off the
        codename; RHEL uses a single el-version-agnostic .repo."""
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
        else:
            # Works for Fedora and the RHEL/Rocky/Alma "el" family alike.
            distro = "fedora" if (self.os_info.get("ID") == "fedora") else "rhel"
            ver = self.os_info.get("VERSION_ID", "").split(".")[0]
            self.run(
                f"dnf -y config-manager --add-repo "
                f"https://pkgs.tailscale.com/stable/{distro}/{ver}/tailscale.repo"
            )
        self.pkg_install("tailscale")

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
