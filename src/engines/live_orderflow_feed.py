"""
Live Tick-Level Orderflow & CVD (Cumulative Volume Delta) Feed
=============================================================
Provides real-time, tick-level orderflow delta tracking via public,
unauthenticated WebSocket streams (Binance aggTrade).

Architecture & Safety:
1. Public & Read-Only: Zero API keys or secrets.
2. Non-Blocking Background Daemon: Runs on an isolated asyncio thread.
3. Thread-Safe Ring Buffer: collections.deque(maxlen=15000) capped to ~5MB RAM.
4. Fail-Safe Fallback: Gracefully reports health status so consumers can fallback
   to OHLCV proxy CVD if disconnected.
"""

import asyncio
import json
import logging
import threading
import time
from collections import deque
from typing import Dict, Optional, Tuple

import websockets

logger = logging.getLogger(__name__)

# Symbol mapping to Binance public stream identifiers
SYMBOL_STREAM_MAP = {
    "BTC/USD": "btcusdt",
    "BTCUSD": "btcusdt",
    "BTC/USDT": "btcusdt",
    "ETH/USD": "ethusdt",
    "ETHUSD": "ethusdt",
    "ETH/USDT": "ethusdt",
    "SOL/USD": "solusdt",
    "SOLUSD": "solusdt",
    "SOL/USDT": "solusdt",
}

WS_BASE_URL = "wss://stream.binance.com:9443/ws"


class LiveOrderflowFeed:
    """
    Singleton / thread-safe manager for live orderflow data and CVD metrics.
    """
    _instance: Optional['LiveOrderflowFeed'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LiveOrderflowFeed, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, symbols: Optional[list] = None):
        if getattr(self, '_initialized', False):
            return

        self.symbols = symbols or ["BTC/USD", "ETH/USD", "SOL/USD"]
        self._buffers: Dict[str, deque] = {
            s: deque(maxlen=15000) for s in self.symbols
        }
        self._last_tick_time: Dict[str, float] = {s: 0.0 for s in self.symbols}
        self._last_price: Dict[str, float] = {s: 0.0 for s in self.symbols}
        self._data_lock = threading.Lock()
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._initialized = True
        logger.info("📡 LiveOrderflowFeed initialized.")

    def start(self):
        """Starts the background WebSocket streaming daemon thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._run_async_loop,
                name="LiveOrderflowFeedDaemon",
                daemon=True
            )
            self._thread.start()
            logger.info("🚀 LiveOrderflowFeed background daemon started.")

    def stop(self):
        """Stops the streaming daemon thread."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread:
                self._thread.join(timeout=2.0)
            logger.info("🛑 LiveOrderflowFeed background daemon stopped.")

    def _run_async_loop(self):
        """Worker thread entrypoint for asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._stream_manager())
        except Exception as e:
            logger.debug(f"LiveOrderflowFeed loop stopped: {e}")
        finally:
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            self._loop.close()

    async def _stream_manager(self):
        """Manages connections for all tracked symbols with exponential backoff."""
        streams = [
            f"{SYMBOL_STREAM_MAP[s]}@aggTrade"
            for s in self.symbols
            if s in SYMBOL_STREAM_MAP
        ]
        if not streams:
            return

        stream_url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
        reconnect_delay = 1.0

        while self._running:
            try:
                logger.info(f"📡 Connecting to Public Orderflow Stream: {stream_url}...")
                async with websockets.connect(
                    stream_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5
                ) as ws:
                    reconnect_delay = 1.0  # Reset backoff upon successful connection
                    logger.info("✅ Public Orderflow WebSocket connected and listening.")
                    
                    while self._running:
                        msg = await ws.recv()
                        self._process_message(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    logger.debug(f"⚠️ Orderflow WS reconnecting in {reconnect_delay:.1f}s ({e})")
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 1.5, 10.0)

    def _process_message(self, raw_msg: str):
        """
        Parses Binance aggTrade JSON message.
        aggTrade format:
          - 'p': Price
          - 'q': Quantity
          - 'T': Timestamp in ms
          - 'm': Was the buyer the maker? (m == True -> Seller was taker -> SELL delta)
        """
        try:
            data = json.loads(raw_msg)
            payload = data.get('data', data)
            stream_name = data.get('stream', '')

            # Resolve symbol from stream
            symbol = None
            for s, stream_id in SYMBOL_STREAM_MAP.items():
                if stream_id in stream_name or stream_id == payload.get('s', '').lower():
                    symbol = s
                    break

            if not symbol or symbol not in self._buffers:
                return

            price = float(payload['p'])
            qty = float(payload['q'])
            ts_sec = float(payload['T']) / 1000.0
            is_buyer_maker = bool(payload['m'])
            
            # Delta calculation:
            # If buyer was maker (m=True), the aggressive taker was a SELLER -> delta = -qty
            # If buyer was taker (m=False), the aggressive taker was a BUYER -> delta = +qty
            delta = -qty if is_buyer_maker else qty

            with self._data_lock:
                self._buffers[symbol].append((ts_sec, price, qty, delta))
                self._last_tick_time[symbol] = ts_sec
                self._last_price[symbol] = price
        except Exception as e:
            logger.debug(f"Failed to parse orderflow tick: {e}")

    def get_metrics(self, symbol: str, window_seconds: int = 300) -> dict:
        """
        Calculates cumulative delta, volume, and delta ratio over the specified time window.
        
        Args:
            symbol: Symbol string (e.g., 'BTC/USD')
            window_seconds: Lookback window in seconds (default: 300 = 5 minutes)
        
        Returns:
            dict containing:
              - is_healthy: True if live ticks received within last 15s
              - cumulative_delta: Net buyer volume - seller volume
              - total_volume: Total volume traded
              - delta_ratio: Normalized delta [-1.0, +1.0]
              - last_price: Most recent tick price
              - tick_count: Number of trades in window
        """
        canonical_symbol = None
        for s in [symbol, symbol.replace("/", ""), symbol + "/USD"]:
            if s in self._buffers:
                canonical_symbol = s
                break

        if not canonical_symbol:
            return {'is_healthy': False, 'reason': 'unsupported_symbol'}

        now = time.time()
        with self._data_lock:
            last_tick = self._last_tick_time.get(canonical_symbol, 0.0)
            is_healthy = (now - last_tick) < 15.0 and len(self._buffers[canonical_symbol]) > 0
            
            if not is_healthy or len(self._buffers[canonical_symbol]) == 0:
                return {
                    'is_healthy': False,
                    'last_tick_age': now - last_tick,
                    'cumulative_delta': 0.0,
                    'total_volume': 0.0,
                    'delta_ratio': 0.0,
                    'last_price': self._last_price.get(canonical_symbol, 0.0),
                    'tick_count': 0
                }

            cutoff = now - window_seconds
            ticks = [t for t in self._buffers[canonical_symbol] if t[0] >= cutoff]

        if not ticks:
            return {
                'is_healthy': is_healthy,
                'cumulative_delta': 0.0,
                'total_volume': 0.0,
                'delta_ratio': 0.0,
                'last_price': self._last_price.get(canonical_symbol, 0.0),
                'tick_count': 0
            }

        cum_delta = sum(t[3] for t in ticks)
        total_vol = sum(t[2] for t in ticks)
        delta_ratio = cum_delta / (total_vol + 1e-8)

        return {
            'is_healthy': is_healthy,
            'cumulative_delta': cum_delta,
            'total_volume': total_vol,
            'delta_ratio': delta_ratio,
            'last_price': ticks[-1][1],
            'tick_count': len(ticks)
        }

    def evaluate_iceberg_absorption(
        self,
        symbol: str,
        direction: str,
        window_seconds: int = 180,
        price_change_pct: float = 0.0
    ) -> Tuple[bool, float, str]:
        """
        Detects real-time institutional limit order iceberg absorption.

        Mechanics:
        - LONG setup: Aggressive market sellers were dumping volume (delta < 0),
          yet price held firm or pushed up (price_change_pct >= -0.10%).
          -> Limit Buy Iceberg absorbed market sellers.
        - SHORT setup: Aggressive market buyers were chasing price (delta > 0),
          yet price was capped or pushed down (price_change_pct <= 0.10%).
          -> Limit Sell Iceberg absorbed market buyers.

        Returns:
            (is_absorbed, strength [0.0 - 1.0], description)
        """
        metrics = self.get_metrics(symbol, window_seconds=window_seconds)
        if not metrics.get('is_healthy', False) or metrics.get('tick_count', 0) < 20:
            return False, 0.0, "Live Orderflow Feed Initializing/Unavailable"

        delta_ratio = metrics['delta_ratio']
        total_vol = metrics['total_volume']

        dir_upper = direction.upper()
        
        # 1. Bullish Absorption (Buying into aggressive sell flow)
        if dir_upper in ["LONG", "BUY"]:
            # Heavy market sell pressure (delta_ratio <= -0.15), but price did not collapse
            if delta_ratio <= -0.15 and price_change_pct >= -0.15:
                strength = min(abs(delta_ratio) * 1.8, 1.0)
                msg = (
                    f"⚡ Live CVD Bullish Absorption: Market Takers dumped "
                    f"({delta_ratio*100:.1f}% Delta, {total_vol:.1f} Vol) but Limit Buy Iceberg absorbed it."
                )
                return True, float(strength), msg

        # 2. Bearish Absorption (Selling into aggressive buy flow)
        elif dir_upper in ["SHORT", "SELL"]:
            # Heavy market buy pressure (delta_ratio >= 0.15), but price was capped
            if delta_ratio >= 0.15 and price_change_pct <= 0.15:
                strength = min(abs(delta_ratio) * 1.8, 1.0)
                msg = (
                    f"⚡ Live CVD Bearish Absorption: Market Takers chased "
                    f"(+{delta_ratio*100:.1f}% Delta, {total_vol:.1f} Vol) but Limit Sell Iceberg capped it."
                )
                return True, float(strength), msg

        return False, 0.0, f"Normal Orderflow Delta ({delta_ratio*100:+.1f}%)"
