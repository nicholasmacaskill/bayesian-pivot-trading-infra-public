#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('data/smc_alpha.db')

rows = conn.execute("""
SELECT symbol, 
       count(*), 
       sum(case when pnl > 0 then pnl else 0 end), 
       sum(case when pnl <= 0 then pnl else 0 end), 
       sum(pnl)
FROM journal
WHERE timestamp >= '2026-08-18'
GROUP BY symbol
""").fetchall()

print("="*75)
print("PnL BREAKDOWN BY SYMBOL (AUGUST 18, 2026 - SEPTEMBER 18, 2026)")
print("="*75)

btc_wins = 0.0
btc_losses = 0.0
btc_net = 0.0
btc_count = 0

alt_wins = 0.0
alt_losses = 0.0
alt_net = 0.0
alt_count = 0

for r in rows:
    sym = r[0] or 'UNKNOWN'
    cnt = r[1]
    gw = float(r[2] or 0)
    gl = float(r[3] or 0)
    net = float(r[4] or 0)
    
    is_btc = ('BTC' in sym)
    if is_btc:
        btc_wins += gw
        btc_losses += gl
        btc_net += net
        btc_count += cnt
    else:
        alt_wins += gw
        alt_losses += gl
        alt_net += net
        alt_count += cnt
        
    print(f"{sym:<12}: {cnt:>4} trades | Gross Wins: +${gw:>8.2f} | Gross Losses: ${gl:>9.2f} | Net PnL: ${net:>9.2f}")

print("="*75)
print(f"BTC COMBINED: {btc_count} trades | Gross Wins: +${btc_wins:,.2f} | Gross Losses: ${btc_losses:,.2f} | Net: ${btc_net:,.2f}")
print(f"NON-BTC ALTS: {alt_count} trades | Gross Wins: +${alt_wins:,.2f} | Gross Losses: ${alt_losses:,.2f} | Net: ${alt_net:,.2f}")
print("="*75)
