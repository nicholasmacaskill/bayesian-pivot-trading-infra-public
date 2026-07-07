import json

path = "data/manual_trades_supabase.json"
with open(path, 'r') as f:
    data = json.load(f)

print("First 3 trades found in your snapshot:")
for d in data[:3]:
    symbol = d.get('symbol') or d.get('asset', 'Unknown')
    side = d.get('side', 'Unknown')
    pnl = d.get('pnl') or d.get('profit', 0)
    date = d.get('created_at') or d.get('close_date', 'Unknown')
    print(f"- {date} | {symbol} {side} | PnL: ${pnl}")
