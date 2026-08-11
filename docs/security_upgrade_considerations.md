# Security Hardening Considerations
> Captured: 2026-08-11 — Post-phishing incident review (Proton Mail)
> Status: No compromise found. All checks clean. These are proactive upgrades for future consideration.

---

## Context

On 2026-08-11 a phishing link was received via Proton Mail. A full security sweep was conducted using Sovereign Guard and native macOS tooling. The Mac was confirmed clean across all checked vectors. The following are hardening improvements identified during that session that go beyond the current Sovereign Guard baseline.

---

## 1. osquery Integration into Sovereign Guard

**What it is:** Open-source OS telemetry tool (used by Cloudflare, Facebook internally) that exposes the entire OS as queryable SQL tables — running processes, open sockets, loaded kernel extensions, cron jobs, user accounts, LaunchAgents, and more.

**Why it's better than current approach:**
- Current process scanning uses `psutil` + `lsof` — point-in-time snapshots
- `osquery` provides structured, continuous, queryable telemetry with historical logging
- Can join process data with network data with file data in a single query
- Industry-standard — same tool used by enterprise EDR platforms as their data layer

**Implementation idea:**
- Install via `brew install osquery`
- Add `OsqueryScanner` class to `guard_engine.py` running scheduled queries
- Queries: unusual processes with network connections, new files in sensitive paths, unexpected LaunchAgent additions, processes with `DYLD_INSERT_LIBRARIES` in environment
- Log to `guard_engine.log`, alert via Telegram on anomalies

---

## 2. Live IOC (Indicators of Compromise) Feed Matching

**What it is:** Cross-referencing active network connections, process hashes, and domain lookups against live threat intelligence databases.

**Recommended feeds (free tier available):**
- [AlienVault OTX](https://otx.alienvault.com/) — malicious IPs, domains, file hashes
- [abuse.ch URLhaus](https://urlhaus.abuse.ch/) — active malware distribution URLs
- [Emerging Threats](https://rules.emergingthreats.net/) — network-level IOC rules

**Implementation idea:**
- Add `IOCChecker` module to Sovereign Guard
- On session startup: pull latest IOC feed, cache locally (daily refresh)
- Cross-check active TCP connections against known malicious IPs
- Cross-check DNS queries against known malicious domains
- Alert via Telegram on any match

---

## 3. Browser Extension Continuous Auditing (Enhance Existing)

**Current state:** Sovereign Guard scans browser extensions hourly for risky permissions.

**Gaps identified:**
- Does not verify extension version against Chrome Web Store (supply-chain attack vector)
- Does not hash-check extension files against known-good baselines
- `__MSG_appName__` localisation quirk makes display noisy (MetaMask showed as unnamed)

**Enhancement ideas:**
- Add CWS version check via webstore API
- Store extension manifest hashes on first scan as baseline; alert on changes
- Resolve `__MSG_*` keys from `_locales/en/messages.json` for cleaner output

---

## 4. Process Memory Integrity Scanning

**Current state:** `_check_deep_forensics()` runs `codesign` on Chrome and Brave only.

**Enhancement:**
- Extend to all running processes above a memory threshold that have network connections
- Flag any process with invalid or missing code signature
- Particularly important for: Python interpreter, Node.js, tsx (used extensively in this stack)

---

## 5. Network Baselining & Anomaly Detection

**What it is:** Record a clean-state snapshot of all outbound connections and alert on new destinations.

**Current state:** `_check_session_hijack()` monitors connections to TradeLocker and LinkedIn specifically.

**Enhancement:**
- On first clean run, snapshot all unique remote IPs/hostnames
- Store as `network_baseline.json` in `run_data/`
- On subsequent scans, diff against baseline and alert on new external destinations
- Detects C2 (command-and-control) beaconing to new IPs

---

## 6. MTU Hardening (Post-VPN Cleanup)

**Issue found 2026-08-11:** MTU was set to 1450 (leftover from Cloudflare WARP session) instead of standard 1500. Causes packet fragmentation overhead on every web request.

**Manual fix (requires sudo):**
```bash
sudo networksetup -setMTU Wi-Fi 1500
```

**Guard enhancement:** Add MTU check to startup — detect non-standard MTU and alert if changed outside of an active VPN session.

---

## 7. DNS Resolver Enforcement

**Current state:** DNS routes through WARP's local resolver when active; falls back to ISP DNS when off.

**Recommendation:**
- Hardcode a trusted DoH resolver when WARP is disabled (Cloudflare `1.1.1.1`, Quad9 `9.9.9.9`, or NextDNS)
- Add DNS resolver check to Sovereign Guard: alert if resolver is not on the approved list

---

## 8. Syscall-Level Monitoring (Long-Term / Nice-to-Have)

**Reality check:** Requires an Apple-notarised System Extension. Cannot be achieved in pure userspace on a SIP-enabled Mac. This is what CrowdStrike/SentinelOne use.

**Options if needed:**
- [Objective-See tools](https://objective-see.org/) — free, open-source macOS security tools (BlockBlock, LuLu, KnockKnock)
- Complement to Sovereign Guard rather than a replacement

---

## Priority Order

| Priority | Item | Effort | Impact |
|---|---|---|---|
| 🔴 High | osquery integration | Medium | Very High |
| 🔴 High | MTU auto-check on Guard startup | Low | Medium |
| 🟡 Medium | IOC feed matching | Medium | High |
| 🟡 Medium | Network baselining | Medium | High |
| 🟡 Medium | Browser extension version/hash check | Low | Medium |
| 🟢 Low | Process memory integrity (all procs) | High | Medium |
| 🟢 Low | DNS resolver enforcement | Low | Medium |
| ⚪ Future | Syscall-level via Objective-See tools | Low (install) | High |

---

## Audit Results — 2026-08-11

| Check | Result |
|---|---|
| SIP (System Integrity Protection) | ✅ Enabled |
| Non-Apple kernel extensions | ✅ Zero |
| LaunchAgents | ✅ All 10 verified as legitimate sovereign/betbodhi services |
| Browser extensions | ✅ Phantom, Proton Pass, Vercel, MetaMask, Block Site — all legitimate |
| Chrome binary signature | ✅ Valid (TeamID: EQHXZ8M8AV) |
| DYLD memory injection | ✅ None |
| Debug port 9222 | ✅ Sealed |
| Downloads (last 7 days) | ✅ Nothing from unknown/suspicious sources |
| Chrome history | ✅ No phishing domain visited |
| ARP table | ✅ No spoofing, router MAC stable |
| Active HTTPS connections | ✅ Only Python scanner + IDE to Google infrastructure |
| Clipboard | ✅ Clean, no pastejacking payload |
