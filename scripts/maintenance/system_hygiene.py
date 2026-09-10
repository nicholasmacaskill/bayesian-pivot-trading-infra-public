import os
import sys
import subprocess
import logging
import signal
import shutil
from pathlib import Path
from typing import List, Dict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger("SystemHygiene")

# Targeted process patterns for cleanup
TARGET_ORPHAN_PATTERNS = [
    "chrome-devtools-mcp",
    "npm exec chrome-devtools-mcp",
]

# Cache thresholds in Megabytes (Auto-purge if exceeded)
MAX_NPM_CACHE_MB = 300.0
MAX_BUN_CACHE_MB = 300.0
MAX_GENERAL_CACHE_MB = 300.0

def get_dir_size_mb(path: str) -> float:
    """Returns directory size in Megabytes."""
    if not os.path.exists(path):
        return 0.0
    total_bytes = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total_bytes += entry.stat(follow_symlinks=False).st_size
            elif entry.is_dir(follow_symlinks=False):
                total_bytes += sum(
                    f.stat(follow_symlinks=False).st_size
                    for f in Path(entry.path).rglob('*')
                    if f.is_file()
                )
    except Exception:
        pass
    return round(total_bytes / (1024 * 1024), 2)

def clean_package_caches() -> Dict[str, float]:
    """Audits and purges bloated package manager caches."""
    home = os.path.expanduser("~")
    freed_mb = {}

    # 1. NPM Cache
    npm_cache = os.path.join(home, ".npm")
    npm_size = get_dir_size_mb(npm_cache)
    if npm_size > MAX_NPM_CACHE_MB:
        logger.info(f"🧹 NPM cache exceeds {MAX_NPM_CACHE_MB} MB ({npm_size} MB). Purging...")
        try:
            subprocess.run(["npm", "cache", "clean", "--force"], capture_output=True, timeout=10)
            shutil.rmtree(os.path.join(npm_cache, "_cacache"), ignore_errors=True)
            shutil.rmtree(os.path.join(npm_cache, "_npx"), ignore_errors=True)
            freed_mb["npm"] = npm_size
        except Exception as e:
            logger.warning(f"⚠️ NPM cache clean error: {e}")

    # 2. Bun Cache
    bun_cache = os.path.join(home, ".bun", "install", "cache")
    bun_size = get_dir_size_mb(bun_cache)
    if bun_size > MAX_BUN_CACHE_MB:
        logger.info(f"🧹 Bun cache exceeds {MAX_BUN_CACHE_MB} MB ({bun_size} MB). Purging...")
        try:
            shutil.rmtree(bun_cache, ignore_errors=True)
            freed_mb["bun"] = bun_size
        except Exception as e:
            logger.warning(f"⚠️ Bun cache clean error: {e}")

    # 3. User & UV Cache
    user_cache = os.path.join(home, ".cache")
    cache_size = get_dir_size_mb(user_cache)
    if cache_size > MAX_GENERAL_CACHE_MB:
        logger.info(f"🧹 ~/.cache exceeds {MAX_GENERAL_CACHE_MB} MB ({cache_size} MB). Purging...")
        try:
            for sub in ["uv", "puppeteer", "selenium"]:
                sub_path = os.path.join(user_cache, sub)
                if os.path.exists(sub_path):
                    shutil.rmtree(sub_path, ignore_errors=True)
            freed_mb["user_cache"] = cache_size
        except Exception as e:
            logger.warning(f"⚠️ ~/.cache clean error: {e}")

    return freed_mb

def purge_pycache(workspace_roots: List[str]) -> int:
    """Removes __pycache__ and .pytest_cache trees in active repositories."""
    removed_count = 0
    for root in workspace_roots:
        if not os.path.exists(root):
            continue
        for p in Path(root).rglob('__pycache__'):
            if p.is_dir() and "venv" not in str(p) and "node_modules" not in str(p):
                try:
                    shutil.rmtree(p, ignore_errors=True)
                    removed_count += 1
                except Exception:
                    pass
        for p in Path(root).rglob('.pytest_cache'):
            if p.is_dir():
                try:
                    shutil.rmtree(p, ignore_errors=True)
                    removed_count += 1
                except Exception:
                    pass
    return removed_count

def find_matching_processes(patterns: List[str]) -> List[Dict]:
    """Finds running processes matching targeted orphan patterns."""
    matched = []
    try:
        out = subprocess.check_output(["ps", "-eo", "pid,ppid,%cpu,%mem,rss,command"]).decode("utf-8")
        lines = out.strip().split("\n")
        current_pid = os.getpid()

        for line in lines[1:]:
            parts = line.split(None, 5)
            if len(parts) >= 6:
                pid, ppid, cpu, mem, rss, cmd = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
                try:
                    p_id = int(pid)
                    if p_id == current_pid:
                        continue
                    
                    for pattern in patterns:
                        if pattern in cmd and "grep" not in cmd and "system_hygiene.py" not in cmd:
                            matched.append({
                                "pid": p_id,
                                "ppid": int(ppid),
                                "cpu": float(cpu),
                                "mem": float(mem),
                                "rss_mb": round(int(rss) / 1024, 2),
                                "cmd": cmd,
                                "pattern": pattern
                            })
                            break
                except ValueError:
                    continue
    except Exception as e:
        logger.error(f"Error scanning processes: {e}")
    return matched

def terminate_orphaned_mcp_processes() -> int:
    """Terminates orphaned chrome-devtools-mcp and related lingering debugger instances."""
    targets = find_matching_processes(TARGET_ORPHAN_PATTERNS)
    if not targets:
        return 0

    killed_count = 0
    logger.info(f"🧹 Found {len(targets)} lingering MCP / debugger process(es) to clean:")
    for proc in targets:
        logger.info(f"   - Killing PID {proc['pid']} (RSS: {proc['rss_mb']} MB): {proc['cmd'][:80]}")
        try:
            os.kill(proc["pid"], signal.SIGKILL)
            killed_count += 1
        except ProcessLookupError:
            pass
        except Exception as e:
            logger.error(f"   ⚠️ Failed to kill PID {proc['pid']}: {e}")

    return killed_count

def check_system_memory_health() -> Dict:
    """Queries macOS swap and compression metrics."""
    health = {"swap_used_mb": 0.0, "status": "NOMINAL"}
    try:
        out = subprocess.check_output(["sysctl", "vm.swapusage"]).decode("utf-8")
        # e.g., vm.swapusage: total = 0.00M  used = 0.00M  free = 0.00M  (encrypted)
        if "used =" in out:
            used_str = out.split("used =")[1].split("M")[0].strip()
            health["swap_used_mb"] = float(used_str)
            if health["swap_used_mb"] > 256.0:
                health["status"] = "WARNING_SWAPPING"
    except Exception:
        pass
    return health

def sweep_system_hygiene() -> Dict:
    """Full system hygiene sweep callable by background supervisors or cron."""
    mcp_cleaned = terminate_orphaned_mcp_processes()
    caches_freed = clean_package_caches()
    home = os.path.expanduser("~")
    workspaces = [
        os.path.join(home, "sovereignSMC", "bayesian-pivot-trading-infra"),
        os.path.join(home, "Downloads", "bet-bodhi"),
    ]
    pycache_cleaned = purge_pycache(workspaces)
    mem_health = check_system_memory_health()

    return {
        "mcp_cleaned": mcp_cleaned,
        "caches_freed_mb": caches_freed,
        "pycache_dirs_removed": pycache_cleaned,
        "memory_health": mem_health
    }

if __name__ == "__main__":
    logger.info("🛡️ Initiating Sovereign Automated System Hygiene Sweep...")
    result = sweep_system_hygiene()
    logger.info(f"🎉 Sweep Complete: MCP Terminated={result['mcp_cleaned']}, Caches Purged={result['caches_freed_mb']}, PyCache Cleaned={result['pycache_dirs_removed']}, Mem Status={result['memory_health']['status']}")
