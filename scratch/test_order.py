from src.clients.tl_client import TradeLockerClient
tl = TradeLockerClient()
res = tl.helpers[0].place_order(instrument_id=19965, side="buy", qty=0.30, stop_loss=62091, take_profit=63391)
print("Result:", res)
