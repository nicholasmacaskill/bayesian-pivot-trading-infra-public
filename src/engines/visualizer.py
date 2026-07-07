import matplotlib
matplotlib.use('Agg')
import mplfinance as mpf
import pandas as pd
import os
from datetime import datetime

def generate_ict_chart(df, setup, output_path="setup_chart.png"):
    """
    Generates a high-fidelity ICT-contextualized chart.
    """
    try:
        if df is None or df.empty:
            print("⚠️ No data available for chart generation")
            return None
        # Prepare Dataframe for mplfinance
        df_plot = df.copy()
        df_plot.set_index('timestamp', inplace=True)
        
        # Determine plot range (last 100 candles for context)
        df_plot = df_plot.iloc[-100:]
        
        # Prices to mark
        entry = setup['entry']
        target = setup['target']
        sl = setup['stop_loss']
        
        # Collect all hlines
        h_prices = [entry, target, sl]
        h_colors = ['#f1c40f', '#2ecc71', '#e74c3c']
        h_styles = ['-', '-', '-']
        
        # Add Horizontal lines for ranges if available
        if 'price_quartiles' in setup:
            pq = setup['price_quartiles']
            if 'Asian Range' in pq:
                ar = pq['Asian Range']
                h_prices.extend([ar['high'], ar['low']])
                h_colors.extend(['#3498db', '#3498db'])
                h_styles.extend(['--', '--'])
            if 'London Range' in pq:
                lr = pq['London Range']
                h_prices.extend([lr['high'], lr['low']])
                h_colors.extend(['#e67e22', '#e67e22'])
                h_styles.extend(['--', '--'])

        # Plot setup
        style = mpf.make_mpf_style(base_mpf_style='charles', gridcolor='#2c3e50', facecolor='#1a1a1a', 
                                  edgecolor='#2c3e50', figcolor='#1a1a1a')
        
        mpf.plot(df_plot, type='candle', style=style, 
                 hlines=dict(hlines=h_prices, colors=h_colors, linestyle=h_styles, linewidths=1.5),
                 title=f"SOVEREIGN AI LAB: {setup['symbol']} {setup['pattern']}",
                 ylabel='Price',
                 savefig=output_path,
                 tight_layout=True,
                 datetime_format='%H:%M',
                 volume=False)
        
        return output_path
    except Exception as e:
        print(f"Error generating chart: {e}")
        return None

def generate_bias_chart(df, symbol, timeframe="4h", output_path="bias_chart.png"):
    """
    Generates a clean chart for Visual Bias Confirmation (AI Vision).
    Focuses on Trend (EMAs) and Structure.
    """
    try:
        if df is None or df.empty: return None

        # Prepare Data
        df_plot = df.copy()
        df_plot.set_index('timestamp', inplace=True)
        df_plot = df_plot.iloc[-100:]  # Last 100 candles
        
        # Add EMAs
        ema_20 = df_plot['close'].ewm(span=20).mean()
        ema_50 = df_plot['close'].ewm(span=50).mean()
        
        adps = [
            mpf.make_addplot(ema_20, color='#2ecc71', width=1.5),  # Green
            mpf.make_addplot(ema_50, color='#e74c3c', width=1.5)   # Red
        ]
        
        # Style
        style = mpf.make_mpf_style(base_mpf_style='charles', gridcolor='#2c3e50', facecolor='#1a1a1a', 
                                  edgecolor='#2c3e50', figcolor='#1a1a1a')
        
        mpf.plot(df_plot, type='candle', style=style, 
                 addplot=adps,
                 title=f"{symbol} {timeframe} MARKET BIAS CHECK",
                 ylabel='Price',
                 savefig=output_path,
                 tight_layout=True,
                 datetime_format='%H:%M',
                 volume=False)
                 
        return output_path
    
    except Exception as e:
        print(f"Error generating bias chart: {e}")
        return None

if __name__ == "__main__":
    import numpy as np
    dates = pd.date_range('2024-01-01', periods=100, freq='5min')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': np.random.uniform(40000, 41000, 100),
        'high': np.random.uniform(40000, 41000, 100),
        'low': np.random.uniform(40000, 41000, 100),
        'close': np.random.uniform(40000, 41000, 100)
    })
    setup = {
        'symbol': 'BTC/USDT',
        'pattern': 'Bullish PO3',
        'entry': 40500,
        'target': 41000,
        'stop_loss': 40200
    }
    generate_ict_chart(df, setup, "mock_chart.png")
