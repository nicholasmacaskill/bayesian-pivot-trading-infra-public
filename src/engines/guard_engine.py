"""
Sovereign Guard Engine — Integrated Security Layer
===================================================
Ported from sovereign-guard-private into the SMC runner environment.

Runs as a background thread (5-second tick) alongside the trading scanner.
All threat alerts are routed through the shared TelegramNotifier so you
receive security events in the same channel as trade signals.

Architecture:
  LocalScannerRunner (main thread)
    └── GuardEngine.start()  →  daemon thread
          ├── Clipboard sentry         (every 5s)
          ├── Process scan             (every 10s)
          ├── Persistence monitor      (every 60s)
          ├── Debug-port audit         (every 30s)
          ├── Session monitor          (every 60s – TradeLocker, LinkedIn)
          ├── Root CA scan             (every 15 min)
          ├── Browser extension audit  (every hour)
          └── System trust score       (every hour → TG heartbeat)

Security context is exposed via GuardEngine.get_security_context() so the
AI validator can append a one-line state summary to its Gemini prompt.
"""

import os
import re
import sys
import time
import hmac
import socket
import logging
import platform
import threading
import subprocess
from datetime import datetime
from logging.handlers import RotatingFileHandler

logger = logging.getLogger("GuardEngine")

# ---------------------------------------------------------------------------
# sovereign_engine submodule — graceful fallback if not yet installed
# ---------------------------------------------------------------------------

try:
    from src.engines.sovereign_engine import (
        analyzer, injection_defense, file_monitor, forensics,
        identity, persistence, scanners, tripwire
    )
    _SOVEREIGN_ENGINE_AVAILABLE = True
    logger.info("🛡️  sovereign_engine submodule loaded (Functional API).")
except ImportError as _e:
    _SOVEREIGN_ENGINE_AVAILABLE = False
    logger.warning(f"sovereign_engine submodule not available: {_e} — running in lite mode.")

# ---------------------------------------------------------------------------
# Inline pattern constants (no sovereign_core / path_utils dependency)
# ---------------------------------------------------------------------------

PROTECTED_SESSION_DOMAINS = [
    'tradelocker.com', 'api.tradelocker.com',
    'linkedin.com', 'licdn.com', 'platform.linkedin.com',
]

SESSION_MONITOR_BROWSERS = [
    'chrome', 'brave', 'edge', 'arc', 'safari', 'firefox', 'opera', 'vivaldi',
]

SAFE_PROCESSES = [
    'Antigravity', 'Code Helper', 'Google Chrome Helper', 'secd',
    'trustedpeershelper', 'callservicesd', 'AudioComponentRegistrar',
    'PowerChime', 'loginwindow', 'distnoted', 'cfprefsd',
    'UserEventAgent', 'sharingd', 'commcenter', 'notification_center',
    'kernel_task', 'launchd', 'sysmond', 'logd', 'mdworker',
    'python', 'python3',  # allow our own process
]

# Crypto address patterns for clipper detection
BTC_PATTERN = r'\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[ac-hj-np-z02-9]{11,71})\b'
ETH_PATTERN = r'\b0x[a-fA-F0-9]{40}\b'
CRYPTO_RE   = re.compile(f"({BTC_PATTERN})|({ETH_PATTERN})")

PASTEJACKING_PATTERN = re.compile(
    r'(?:\x1b\[[0-9;]*[a-zA-Z]|curl\s+[^\|]+\|\s*sh|powershell\s+-enc'
    r'|base64\s+-d|echo\s+[^\n]+\|\s*base64|IEX\s*\(|DownloadString'
    r'|FromBase64String|mshta\s+|regsvr32\s+|rundll32\s+url\.dll)',
    re.IGNORECASE
)

CMD_INJECTION_PATTERN = re.compile(
    r'(?:curl|wget)\s+https?://[^\s]+\s*\|\s*(?:bash|sh|zsh|python)',
    re.IGNORECASE
)

SENSITIVE_KEY_PATTERN = re.compile(
    r'-----BEGIN (?:RSA|OPENSSH) PRIVATE KEY-----|AKIA[A-Z0-9]{16}'
)

PERSISTENCE_PATHS = [
    os.path.expanduser('~/Library/LaunchAgents'),
    '/Library/LaunchAgents',
    '/Library/LaunchDaemons',
]

DEBUG_PORT_FLAG = '--remote-debugging-port'
SUSPICIOUS_FLAGS = ['--disable-web-security', '--no-sandbox', '--headless',
                    '--remote-debugging-port']

TRUSTED_CA_PATTERNS = [
    r'apple\.com', r'Apple Worldwide Developer Relations', r'System Identity',
    r'DigiCert', r'GlobalSign', r'Sectigo', r'Entrust', r'GoDaddy',
    r'Let\'s Encrypt', r'Amazon', r'Google Trust Services', r'Microsoft',
    r'UserTrust', r'Cloudflare',
]


# ---------------------------------------------------------------------------
# GuardEngine
# ---------------------------------------------------------------------------

class GuardEngine:
    """
    Sovereign Guard — background security monitor for the SMC trading agent.

    Usage:
        guard = GuardEngine(notifier=self.notifier)
        guard.start()                   # launches daemon thread
        ctx = guard.get_security_context()  # for AI prompt enrichment
        guard.stop()
    """

    TICK_INTERVAL = 5          # seconds between main loop iterations

    def __init__(self, notifier=None):
        self._notifier   = notifier     # TelegramNotifier instance (shared)
        self._thread     = None
        self._stop_event = threading.Event()

        # Threat state (thread-safe: written by guard thread, read by main)
        self._lock              = threading.Lock()
        self._active_threats    = []    # list of recent threat dicts
        self._trust_score       = 100
        self._system_clean      = True  # False if any threat in last cycle

        # Internal timers
        self._t_process      = 0
        self._t_persistence  = 0
        self._t_debug_port   = 0
        self._t_session      = 0
        self._t_ca           = 0
        self._t_extensions   = 0
        self._t_hourly       = 0
        self._t_plist        = 0

        # Clipboard last value
        self._last_clipboard = None

        # Persistence baselines
        self._persistence_baseline: dict = {}

        # ── sovereign_engine deep-scan initialization ─────────────────────────
        self.deep_scan_enabled = _SOVEREIGN_ENGINE_AVAILABLE
        if self.deep_scan_enabled:
            try:
                # Deploy honeypots/bait files at startup
                tripwire.deploy_bait()
                file_monitor.setup_honeypot()
                logger.info("🔬 Deep-scan modules (Functional) ready.")
            except Exception as _init_e:
                logger.warning(f"Deep-scan module init failed: {_init_e}")
                self.deep_scan_enabled = False
        # ─────────────────────────────────────────────────────────────────────

        logger.info("🛡️  Guard Engine initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start the guard monitor as a daemon thread."""
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="SovereignGuard",
            daemon=True,
        )
        self._thread.start()
        logger.info("🛡️  Sovereign Guard thread started.")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)

    def get_security_context(self) -> str:
        """
        Returns a one-line summary for injection into the AI validator prompt.
        Example:
          "System security: CLEAN (trust score: 97/100)"
          "⚠️ System security: THREAT DETECTED — CLIPBOARD_THREAT, DEBUG_PORT_OPEN"
        """
        with self._lock:
            if self._system_clean:
                return f"System security: CLEAN (trust score: {self._trust_score}/100)"
            types = ", ".join(t.get('type', '?') for t in self._active_threats[-5:])
            return f"⚠️ System security: THREAT DETECTED — {types} (trust: {self._trust_score}/100)"

    def get_trust_score(self) -> int:
        with self._lock:
            return self._trust_score

    # ------------------------------------------------------------------
    # Internal monitor loop
    # ------------------------------------------------------------------

    def _monitor_loop(self):
        logger.info("🛡️  Guard monitor loop running.")
        self._seal_debug_port()
        self._scan_launch_agent_plists()  # immediate startup audit

        while not self._stop_event.is_set():
            t = time.time()
            new_threats = []

            try:
                # ── Clipboard (every 5s) ─────────────────────────────────
                cb_threat = self._check_clipboard()
                if cb_threat:
                    new_threats.append(cb_threat)

                # ── Process scan (every 10s) ─────────────────────────────
                if t - self._t_process > 10:
                    proc_threats = self._scan_processes()
                    new_threats.extend(proc_threats)
                    self._t_process = t

                # ── Persistence (every 60s) ──────────────────────────────
                if t - self._t_persistence > 60:
                    persist_threats = self._check_persistence()
                    new_threats.extend(persist_threats)
                    self._t_persistence = t

                # ── LaunchAgent plist scan (every 5 min) ─────────────────
                if t - self._t_plist > 300:
                    self._scan_launch_agent_plists()
                    self._t_plist = t

                # ── Debug port (every 30s) ───────────────────────────────
                if t - self._t_debug_port > 30:
                    dp_threat = self._check_debug_port()
                    if dp_threat:
                        new_threats.append(dp_threat)
                    self._t_debug_port = t

                # ── Session monitor (every 60s) ──────────────────────────
                if t - self._t_session > 60:
                    sess_threats = self._check_session_hijack()
                    new_threats.extend(sess_threats)
                    self._t_session = t

                # ── Root CA scan (every 15 min) ──────────────────────────
                if t - self._t_ca > 900:
                    ca_threats = self._scan_root_cas()
                    new_threats.extend(ca_threats)
                    self._t_ca = t

                # ── Deep scan: MITM / network (every 5 min, if available) ────
                if self.deep_scan_enabled and t - self._t_ca > 300:
                    mitm_threats = self._check_mitm()
                    new_threats.extend(mitm_threats)

                # ── Deep scan: Injection + Tripwire (every tick) ───────────
                if self.deep_scan_enabled:
                    inj_threats = self._check_injection()
                    new_threats.extend(inj_threats)
                    
                    trip_threats = self._check_tripwires()
                    new_threats.extend(trip_threats)
                    
                    file_threats = self._check_sensitive_files()
                    new_threats.extend(file_threats)

                # ── Hourly: extensions + history + trust score report ────────
                if t - self._t_hourly > 3600:
                    ext_threats = self._scan_extensions()
                    new_threats.extend(ext_threats)
                    
                    if self.deep_scan_enabled:
                        hist_threats = self._check_history()
                        new_threats.extend(hist_threats)

                    self._update_trust_score()
                    self._send_hourly_status()
                    self._t_hourly = t

                # ── Dispatch new threats ─────────────────────────────────
                if new_threats:
                    for threat in new_threats:
                        self._dispatch_threat(threat)

                    with self._lock:
                        self._active_threats = new_threats
                        self._system_clean   = False
                        # Deduct trust score aggressively for active threats
                        self._trust_score = max(0, self._trust_score - 5 * len(new_threats))
                else:
                    with self._lock:
                        self._active_threats = []
                        self._system_clean   = True
                        # Slowly recover
                        self._trust_score = min(100, self._trust_score + 1)

            except Exception as e:
                logger.error(f"Guard loop error: {e}", exc_info=True)

            self._stop_event.wait(self.TICK_INTERVAL)

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    def _check_clipboard(self):
        """Detect clipboard hijacking — crypto swaps, pastejacking, command injection."""
        try:
            if platform.system() != 'Darwin':
                return None
            current = subprocess.check_output(
                ['pbpaste'], text=True, stderr=subprocess.DEVNULL
            )
            if not current or current == self._last_clipboard:
                self._last_clipboard = current
                return None

            prev = self._last_clipboard
            self._last_clipboard = current

            # 1. Crypto swap check
            curr_crypto = CRYPTO_RE.search(current)
            prev_crypto = CRYPTO_RE.search(prev) if prev else None
            if curr_crypto and prev_crypto and curr_crypto.group(0) != prev_crypto.group(0):
                return {
                    'type': 'CRYPTO_CLIPPER',
                    'severity': 'CRITICAL',
                    'title': '🚨 CRYPTO CLIPPER DETECTED',
                    'summary': (
                        f"Wallet address substituted in clipboard!\n"
                        f"  Was: `{prev_crypto.group(0)[:16]}…`\n"
                        f"  Now: `{curr_crypto.group(0)[:16]}…`"
                    )
                }

            # 2. Pastejacking / command injection
            if PASTEJACKING_PATTERN.search(current) or CMD_INJECTION_PATTERN.search(current):
                # Neutralise immediately
                subprocess.run(['pbcopy'], input=b'[SOVEREIGN GUARD: CLIPBOARD SANITISED]',
                               check=False)
                return {
                    'type': 'CLIPBOARD_THREAT',
                    'severity': 'HIGH',
                    'title': '🧹 CLIPBOARD THREAT NEUTRALISED',
                    'summary': 'Pastejacking / command-injection payload detected and wiped from clipboard.'
                }

            # 3. Exposed private key
            if SENSITIVE_KEY_PATTERN.search(current):
                return {
                    'type': 'SENSITIVE_EXPOSURE',
                    'severity': 'HIGH',
                    'title': '🔑 SENSITIVE KEY IN CLIPBOARD',
                    'summary': 'A private key or AWS credential was found in your clipboard.'
                }

        except Exception as e:
            logger.debug(f"Clipboard check error: {e}")

        return None

    def _scan_processes(self) -> list:
        """Scan running processes for known attack vectors."""
        threats = []
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'ppid']):
                try:
                    info    = proc.info
                    name    = (info.get('name') or '').lower()
                    cmdline = ' '.join(info.get('cmdline') or [])
                    exe     = info.get('exe') or ''

                    # Skip safe processes
                    if any(s.lower() in name for s in SAFE_PROCESSES):
                        continue

                    # Remote debugging port on a browser
                    if DEBUG_PORT_FLAG in cmdline and '9222' in cmdline:
                        if any(b in name for b in ['chrome', 'brave', 'edge', 'arc']):
                            try:
                                proc.kill()
                                note = f" — process killed (PID {info['pid']})"
                            except Exception:
                                note = " — could not terminate (insufficient perms)"

                            threats.append({
                                'type': 'DEBUG_HIJACK',
                                'severity': 'CRITICAL',
                                'title': '🔒 DEBUG PORT HIJACK BLOCKED',
                                'summary': (
                                    f"`{info.get('name')}` launched with `--remote-debugging-port=9222`{note}.\n"
                                    f"This is the primary session-theft vector. Threat neutralised."
                                )
                            })

                    # --no-sandbox (sandboxless browser)
                    if '--no-sandbox' in cmdline and any(b in name for b in ['chrome', 'brave', 'edge']):
                        threats.append({
                            'type': 'SANDBOX_BYPASS',
                            'severity': 'HIGH',
                            'title': '⚠️ SANDBOX BYPASS DETECTED',
                            'summary': f"`{info.get('name')}` is running without sandbox. Possible session isolation attack."
                        })

                except (Exception,):
                    continue

        except ImportError:
            logger.warning("psutil not installed — process scanning skipped.")

        return threats

    def _check_persistence(self) -> list:
        """Check LaunchAgents/Daemons for new or suspicious entries."""
        threats = []
        try:
            current_state: dict = {}
            for d in PERSISTENCE_PATHS:
                if not os.path.isdir(d):
                    continue
                try:
                    for fname in os.listdir(d):
                        if not fname.endswith('.plist'):
                            continue
                        fpath = os.path.join(d, fname)
                        mtime = os.path.getmtime(fpath)
                        current_state[fpath] = mtime

                        # New file since last check?
                        if fpath not in self._persistence_baseline:
                            threats.append({
                                'type': 'NEW_PERSISTENCE_ENTRY',
                                'severity': 'HIGH',
                                'title': '👻 NEW LAUNCH AGENT DETECTED',
                                'summary': f"New persistence entry appeared: `{fname}`\nPath: `{fpath}`"
                            })
                except PermissionError:
                    continue

            # Update baseline
            self._persistence_baseline = current_state

        except Exception as e:
            logger.debug(f"Persistence check error: {e}")

        return threats

    def _scan_launch_agent_plists(self):
        """
        Scan all plist files for the --remote-debugging-port flag.
        Quarantines and unloads any matches immediately.
        """
        for d in PERSISTENCE_PATHS:
            if not os.path.isdir(d):
                continue
            try:
                for fname in os.listdir(d):
                    if not fname.endswith('.plist'):
                        continue
                    fpath = os.path.join(d, fname)
                    try:
                        result = subprocess.run(
                            ['plutil', '-convert', 'json', '-o', '-', fpath],
                            capture_output=True, text=True, timeout=2
                        )
                        if result.returncode == 0 and '--remote-debugging-port' in result.stdout:
                            msg = f"🚨 MALICIOUS PLIST FOUND: {fpath}"
                            logger.critical(msg)
                            # Unload + quarantine
                            subprocess.run(['launchctl', 'unload', fpath],
                                           capture_output=True, check=False)
                            quarantine = os.path.expanduser('~/.sovereign_quarantine')
                            os.makedirs(quarantine, exist_ok=True)
                            os.rename(fpath, os.path.join(quarantine, fname + '.quarantine'))
                            self._dispatch_threat({
                                'type': 'MALICIOUS_LAUNCHAGENT',
                                'severity': 'CRITICAL',
                                'title': '🔒 MALICIOUS LAUNCH AGENT NEUTRALISED',
                                'summary': (
                                    f"LaunchAgent with `--remote-debugging-port` quarantined:\n"
                                    f"`{fname}`"
                                )
                            })
                    except Exception:
                        continue
            except PermissionError:
                continue

    def _check_debug_port(self):
        """Detect any process with port 9222 open (even if pf is blocking inbound)."""
        try:
            result = subprocess.run(
                ['lsof', '-iTCP:9222', '-sTCP:LISTEN,ESTABLISHED', '-n', '-P'],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    if 'COMMAND' in line:
                        continue
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    return {
                        'type': 'DEBUG_PORT_OPEN',
                        'severity': 'HIGH',
                        'title': '⚠️ PORT 9222 ACTIVE',
                        'summary': (
                            f"`{parts[0]}` (PID: {parts[1]}) has Chrome DevTools port open.\n"
                            f"State: {parts[-1]}. Connection should be blocked by pf."
                        )
                    }
        except Exception as e:
            logger.debug(f"Debug port check: {e}")
        return None

    def _check_session_hijack(self) -> list:
        """
        Detect non-browser processes with active HTTPS connections to
        protected domains (TradeLocker, LinkedIn).
        """
        threats = []
        try:
            result = subprocess.run(
                ['lsof', '-iTCP:443', '-sTCP:ESTABLISHED', '-n', '-P'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0 or not result.stdout.strip():
                return threats

            for line in result.stdout.strip().splitlines():
                if 'COMMAND' in line:
                    continue
                parts = line.split()
                if len(parts) < 9:
                    continue
                proc_name = parts[0]
                pid       = parts[1]
                name_field = parts[8]

                # Skip browsers
                if any(b in proc_name.lower() for b in SESSION_MONITOR_BROWSERS):
                    continue

                if '->' not in name_field:
                    continue

                remote_ip = name_field.split('->')[1].rsplit(':', 1)[0]
                try:
                    hostname = socket.gethostbyaddr(remote_ip)[0]
                except (socket.herror, socket.gaierror):
                    continue

                if any(d in hostname for d in PROTECTED_SESSION_DOMAINS):
                    threats.append({
                        'type': 'SESSION_HIJACK_RISK',
                        'severity': 'CRITICAL',
                        'title': '🔐 SESSION HIJACK RISK',
                        'summary': (
                            f"Non-browser `{proc_name}` (PID: {pid}) has active HTTPS connection to:\n"
                            f"`{hostname}` ({remote_ip})\n"
                            f"This process should NOT have access to your trading session."
                        )
                    })

        except Exception as e:
            logger.debug(f"Session hijack check: {e}")

        return threats

    def _scan_root_cas(self) -> list:
        """Detect rogue self-signed root certificates in macOS keychains."""
        threats = []
        if platform.system() != 'Darwin':
            return threats

        keychains = [
            '/Library/Keychains/System.keychain',
            os.path.expanduser('~/Library/Keychains/login.keychain-db'),
        ]

        for kc in keychains:
            if not os.path.exists(kc):
                continue
            try:
                cmd = f'security find-certificate -a -p "{kc}"'
                certs_pem = subprocess.check_output(
                    cmd, shell=True, text=True, stderr=subprocess.DEVNULL
                )
                for cert_body in certs_pem.split('-----BEGIN CERTIFICATE-----'):
                    if not cert_body.strip():
                        continue
                    full_cert = '-----BEGIN CERTIFICATE-----' + cert_body
                    proc = subprocess.Popen(
                        ['openssl', 'x509', '-noout', '-subject', '-issuer'],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True
                    )
                    out, _ = proc.communicate(input=full_cert)
                    if proc.returncode == 0:
                        subject = ''
                        issuer  = ''
                        for line in out.splitlines():
                            if line.startswith('subject='):
                                subject = line.replace('subject=', '').strip()
                            if line.startswith('issuer='):
                                issuer = line.replace('issuer=', '').strip()

                        if subject and subject == issuer:
                            trusted = any(
                                re.search(p, subject, re.IGNORECASE)
                                for p in TRUSTED_CA_PATTERNS
                            )
                            if not trusted:
                                threats.append({
                                    'type': 'ROGUE_ROOT_CA',
                                    'severity': 'CRITICAL',
                                    'title': '🔓 ROGUE ROOT CA DETECTED',
                                    'summary': (
                                        f"Unknown self-signed root certificate in `{os.path.basename(kc)}`:\n"
                                        f"`{subject}`\n"
                                        f"This is the primary vector for HTTPS interception/MITM attacks."
                                    )
                                })
            except Exception:
                continue

        return threats

    def _scan_extensions(self) -> list:
        """Scan browser extensions for high-risk permissions."""
        threats = []
        RISKY_PERMS = [
            '<all_urls>', 'http://*/*', 'https://*/*',
            'debugger', 'webRequestBlocking', 'proxy'
        ]
        EXT_PATHS = [
            os.path.expanduser('~/Library/Application Support/Google/Chrome/Default/Extensions'),
            os.path.expanduser('~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Extensions'),
            os.path.expanduser('~/Library/Application Support/Arc/User Data/Default/Extensions'),
            os.path.expanduser('~/Library/Application Support/Microsoft Edge/Default/Extensions'),
        ]
        import json
        for base_path in EXT_PATHS:
            if not os.path.exists(base_path):
                continue
            try:
                for ext_id in os.listdir(base_path):
                    ext_dir = os.path.join(base_path, ext_id)
                    if not os.path.isdir(ext_dir):
                        continue
                    versions = sorted(os.listdir(ext_dir))
                    if not versions:
                        continue
                    manifest_path = os.path.join(ext_dir, versions[-1], 'manifest.json')
                    if not os.path.exists(manifest_path):
                        continue
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    perms = manifest.get('permissions', [])
                    found_risks = [p for p in perms if p in RISKY_PERMS]
                    if found_risks:
                        threats.append({
                            'type': 'RISKY_EXTENSION',
                            'severity': 'MEDIUM',
                            'title': '🧩 RISKY BROWSER EXTENSION',
                            'summary': (
                                f"`{manifest.get('name', 'Unknown')}` ({ext_id[:16]}…) "
                                f"has sensitive permissions: `{', '.join(found_risks)}`"
                            )
                        })
            except Exception:
                continue
        return threats

    # ------------------------------------------------------------------
    # Hardening
    # ------------------------------------------------------------------

    def _seal_debug_port(self):
        """Block TCP 9222 (Chrome DevTools) via pf at startup."""
        try:
            existing = subprocess.run(
                ['pfctl', '-sr'], capture_output=True, text=True, timeout=3
            )
            if existing.returncode == 0 and '9222' in (existing.stdout or ''):
                logger.info("🔒 Port 9222 pf rule already active.")
                return
            rule = 'block drop quick proto tcp from any to any port 9222\n'
            subprocess.run(
                ['pfctl', '-ef', '-'],
                input=rule, capture_output=True, text=True, timeout=5
            )
            logger.info("🔒 PORT 9222 SEALED via pf firewall.")
        except Exception as e:
            logger.warning(f"Could not seal port 9222: {e}")

    def _check_mitm(self) -> list:
        """Deep MITM / ARP / network scan via sovereign_engine.analyzer."""
        threats = []
        try:
            results = analyzer.check_mitm_vulnerabilities()
            for r in (results or []):
                threats.append({
                    'type': 'MITM_RISK',
                    'severity': r.get('severity', 'HIGH'),
                    'title': f"🌐 NETWORK THREAT: {r.get('type','?')}",
                    'summary': r.get('summary', 'Unusual network activity detected.')
                })
        except Exception as e:
            logger.debug(f"MITM scan error: {e}")
        return threats

    def _check_injection(self) -> list:
        """Process-level code injection detection via sovereign_engine.injection_defense."""
        threats = []
        try:
            # Check binary integrity of browsers
            integrity_threats = injection_defense.verify_binary_integrity()
            for r in (integrity_threats or []):
                threats.append(r)
                
            # Check for browser hijackers in Launch Services
            launch_threats = injection_defense.check_launch_services()
            for r in (launch_threats or []):
                threats.append(r)
        except Exception as e:
            logger.debug(f"Injection scan error: {e}")
        return threats

    def _check_tripwires(self) -> list:
        """Check honeypot files for unauthorized access."""
        threats = []
        try:
            results = tripwire.check_traps()
            for r in (results or []):
                threats.append(r)
        except Exception as e:
            logger.debug(f"Tripwire check error: {e}")
        return threats

    def _check_sensitive_files(self) -> list:
        """Monitor browser identity files and decoy honeypots."""
        threats = []
        try:
            results = file_monitor.monitor_sensitive_files(active_response_level='safe')
            for r in (results or []):
                threats.append(r)
        except Exception as e:
            logger.debug(f"File monitor error: {e}")
        return threats

    def _check_history(self) -> list:
        """Scan browser history for visits to malicious domains."""
        threats = []
        try:
            results = forensics.scan_browser_history()
            for r in (results or []):
                threats.append(r)
        except Exception as e:
            logger.debug(f"History scan error: {e}")
        return threats


    # ------------------------------------------------------------------
    # Trust score + reporting
    # ------------------------------------------------------------------

    def _update_trust_score(self):
        """Recalculate trust score based on system posture."""
        score = 100

        # Recent guard log threats
        try:
            log_path = 'guard_engine.log'
            if os.path.exists(log_path):
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                recent_threats = sum(
                    1 for l in lines[-500:] if 'CRITICAL' in l or 'WARNING' in l
                )
                score -= min(recent_threats * 3, 40)
        except Exception:
            pass

        with self._lock:
            self._trust_score = max(0, min(100, score))

    def _send_hourly_status(self):
        """Send a compact security status summary to Telegram."""
        with self._lock:
            score = self._trust_score
            clean = self._system_clean

        icon  = "🟢" if clean and score >= 80 else ("🟡" if score >= 50 else "🔴")
        grade = "CLEAN" if clean and score >= 80 else ("DEGRADED" if score >= 50 else "AT RISK")

        msg = (
            f"{icon} *SOVEREIGN GUARD — HOURLY STATUS*\n\n"
            f"🛡️ Trust Score: `{score}/100` ({grade})\n"
            f"⏰ {datetime.now().strftime('%H:%M UTC')}"
        )
        self._tg_send_raw(msg)

    def _dispatch_threat(self, threat: dict):
        """Route a threat to Telegram and log it."""
        severity = threat.get('severity', 'UNKNOWN')
        title    = threat.get('title', '⚠️ THREAT DETECTED')
        summary  = threat.get('summary', '')

        logger.warning(f"[{severity}] {title}: {summary}")

        if self._notifier:
            try:
                self._notifier.send_security_alert(title, summary, severity)
            except Exception as e:
                logger.error(f"Failed to dispatch threat to Telegram: {e}")

    def _tg_send_raw(self, message: str):
        """Send a raw message via the notifier, if available."""
        if self._notifier:
            try:
                self._notifier._send_message(message)
            except Exception:
                pass
