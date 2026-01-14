import sqlite3
import os
from datetime import datetime, date
from src.core.config import Config

def get_db_connection():
    # Ensure directory exists (Modal Volume)
    db_dir = os.path.dirname(Config.DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    start_time = datetime.now()
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Scans Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                timeframe TEXT,
                pattern TEXT,
                bias TEXT,
                ai_score REAL,
                ai_reasoning TEXT,
                status TEXT DEFAULT 'PENDING',
                verdict TEXT DEFAULT 'N/A',
                shadow_regime TEXT DEFAULT 'Unknown',
                shadow_multiplier REAL DEFAULT 1.0
            )
        ''')
        
        # Auto-Migration for existing tables
        try:
            c.execute("ALTER TABLE scans ADD COLUMN verdict TEXT DEFAULT 'N/A'")
        except sqlite3.OperationalError: pass
        
        try:
            c.execute("ALTER TABLE scans ADD COLUMN shadow_regime TEXT DEFAULT 'Unknown'")
        except sqlite3.OperationalError: pass
        
        try:
            c.execute("ALTER TABLE scans ADD COLUMN shadow_multiplier REAL DEFAULT 1.0")
        except sqlite3.OperationalError: pass
        
        # Journal Table (AI Audit Reports)
        c.execute('''
            CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                trade_id TEXT UNIQUE,
                symbol TEXT,
                side TEXT,
                pnl REAL,
                ai_grade REAL,
                mentor_feedback TEXT,
                deviations TEXT,
                is_lucky_failure INTEGER DEFAULT 0
            )
        ''')
        
        # Migrations for Journal Table
        try:
            c.execute("ALTER TABLE journal ADD COLUMN price REAL DEFAULT 0.0")
        except sqlite3.OperationalError: pass

        try:
            c.execute("ALTER TABLE journal ADD COLUMN status TEXT DEFAULT 'CLOSED'")
        except sqlite3.OperationalError: pass
        
        # Sync State Table (For Local-to-Cloud Equity Sync)
        c.execute('''
            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                last_updated TEXT
            )
        ''')
        
        conn.commit()
    except Exception as e:
        print(f"DB Init Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT,
                symbol TEXT,
                timeframe TEXT,
                pattern TEXT,
                pnl REAL,
                win_rate REAL,
                total_trades INTEGER,
                trade_log JSON,
                metadata JSON
            )
        ''')
        conn.commit()
        conn.close()

def log_scan(scan_data, ai_result):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Extract shadow data safely
    shadow_regime = scan_data.get('shadow_regime', 'N/A')
    shadow_multiplier = scan_data.get('shadow_multiplier', 1.0)
    verdict = scan_data.get('verdict', 'N/A')
    
    c.execute('''
        INSERT INTO scans (
            timestamp, symbol, timeframe, pattern, bias, 
            ai_score, ai_reasoning, verdict, shadow_regime, shadow_multiplier
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        scan_data.get('timestamp', datetime.now().isoformat()),
        scan_data['symbol'],
        Config.TIMEFRAME,
        scan_data['pattern'],
        scan_data['bias'],
        ai_result['score'],
        ai_result['reasoning'],
        verdict,
        shadow_regime,
        shadow_multiplier
    ))
    scan_id = c.lastrowid
    conn.commit()
    conn.close()
    return scan_id

def log_journal_entry(trade_id, symbol, side, pnl, score, feedback, deviations, is_lucky_failure=0):
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now().isoformat()
    try:
        c.execute('''
            INSERT OR REPLACE INTO journal (timestamp, trade_id, symbol, side, pnl, ai_grade, mentor_feedback, deviations, is_lucky_failure)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (now, trade_id, symbol, side, pnl, score, feedback, deviations, is_lucky_failure))
        conn.commit()
    except Exception as e:
        print(f"Error logging journal entry: {e}")
    finally:
        conn.close()

def update_sync_state(total_equity, trades_today):
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now().isoformat()
    # Ensure table exists (just in case)
    c.execute('''
        CREATE TABLE IF NOT EXISTS sync_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            last_updated TEXT
        )
    ''')
    c.execute("INSERT OR REPLACE INTO sync_state (key, value, last_updated) VALUES (?, ?, ?)", ("total_equity", total_equity, now))
    c.execute("INSERT OR REPLACE INTO sync_state (key, value, last_updated) VALUES (?, ?, ?)", ("trades_today", trades_today, now))
    conn.commit()
    conn.close()

def get_sync_state():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Ensure table exists
    c.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            last_updated TEXT
        )
    """)
    
    c.execute("SELECT key, value FROM sync_state")
    rows = c.fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}

def check_daily_limit():
    """Returns True if daily trade count < Limit"""
    today = date.today().isoformat()
    conn = get_db_connection()
    c = conn.cursor()
    # This might fail if 'trades' table doesn't exist? 
    # Actually 'trades' table isn't defined in init_db above. 
    # It seems check_daily_limit was using a table that isn't cleanly defined here.
    # We'll assume 'journal' is the source of truth for trades now or create a trades table if needed.
    # For now, let's fix it to look at 'journal' or 'scans' with status executed?
    # Let's use journal count for now, assuming 1 journal entry = 1 trade.
    
    try:
        c.execute("SELECT COUNT(*) FROM journal WHERE date(timestamp) = ?", (today,))
        count = c.fetchone()[0]
    except:
        count = 0
        
    conn.close()
    return count < Config.DAILY_TRADE_LIMIT
