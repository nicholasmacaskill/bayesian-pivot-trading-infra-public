# Future Strategy Ideas

## 1. News Catalysts (Event-Driven)
- **Concept:** Trade immediately following high-impact news releases (CPI, FOMC, NFP) by fading the initial "fake-out" wick.
- **Logic:** News algos often spike price to clear liquidity before the true move.
- **Trigger:** Wait 5 minutes after release -> entry on break of the 1-minute candle high/low in the direction of the trend.

## 2. Statistical Arbitrage (Pairs Trading)
- **Concept:** Exploit pricing inefficiencies between two highly correlated assets (e.g., BTC vs ETH, or SOL vs AVAX).
- **Logic:** When the ratio between Pair A and Pair B deviates > 2 Sigma from the mean, Short the winner and Long the loser.
- **Edge:** Market neutral; profits regardless of market direction, relies only on convergence.

## 3. Funding Rate Arbitrage (Delta Neutral)
- **Concept:** Capture funding fees without directional risk.
- **Logic:** If Perp Funding is highly positive (Longs paying Shorts), Buy Spot BTC and Short Perp BTC 1:1.
- **Profit:** Collect the funding fee every 8 hours.

## 4. Breakout Momentum (Volatility Expansion)
- **Concept:** Catch explosive moves out of tight consolidation (Squeezes).
- **Indicator:** Bollinger Bands contracting to minimum width (The Squeeze).
- **Trigger:** Candle close outside the bands + Volume Spike.

## 5. Order Flow Imbalance (Footprint)
- **Concept:** Detect aggressive market buying/selling at specific price levels using footprint charts.
- **Logic:** Identifies "Stacked Imbalances" (e.g., 3 consecutive price ticks with 300%+ more buy volume than sell volume).
- **Trigger:** Retest of the imbalance stack.
