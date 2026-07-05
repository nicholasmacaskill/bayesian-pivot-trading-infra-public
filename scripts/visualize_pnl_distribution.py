import os
import sqlite3
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# Set style for premium "Sovereign" Dark Mode look
plt.style.use('dark_background')
accent_color = '#00ffcc'       # Sovereign Teal
secondary_color = '#ff3366'    # Risk Red
highlight_color = '#ffcc00'    # Outlier Gold
muted_gray = '#4f5e71'         # Grid Muted Gray
system_color = '#3399ff'       # System Blue

def parse_timestamp(ts):
    if not ts:
        return None
    try:
        ts_str = str(ts).strip()
        if ts_str.isdigit():
            val = int(ts_str)
            if len(ts_str) == 13:
                return pd.to_datetime(val, unit='ms')
            else:
                return pd.to_datetime(val, unit='s')
        else:
            return pd.to_datetime(ts_str.replace("Z", ""))
    except Exception:
        return None

def load_data():
    conn = sqlite3.connect('data/smc_alpha.db')
    df = pd.read_sql_query("SELECT * FROM journal", conn)
    conn.close()
    
    # Parse timestamps to pandas Datetime
    df['datetime'] = df['timestamp'].apply(parse_timestamp)
    df = df.dropna(subset=['datetime']).sort_values('datetime')
    df['date'] = df['datetime'].dt.date
    return df

def generate_report_and_plots():
    df = load_data()
    
    # Group by date and strategy
    daily_stats = df.groupby(['date', 'strategy']).agg(
        daily_pnl=('pnl', 'sum'),
        trade_count=('pnl', 'count'),
        avg_trade_pnl=('pnl', 'mean')
    ).reset_index()
    
    # Pivot for clean comparison
    daily_pnl = daily_stats.pivot(index='date', columns='strategy', values='daily_pnl').fillna(0)
    daily_count = daily_stats.pivot(index='date', columns='strategy', values='trade_count').fillna(0)
    
    # Get combined data for easy indexing
    dates = sorted(list(set(daily_stats['date'])))
    all_dates_df = pd.DataFrame(index=dates)
    all_dates_df = all_dates_df.join(daily_pnl).fillna(0)
    all_dates_df = all_dates_df.rename(columns={'SYSTEM': 'system_pnl', 'ROGUE': 'rogue_pnl'})
    all_dates_df = all_dates_df.join(daily_count).fillna(0)
    all_dates_df = all_dates_df.rename(columns={'SYSTEM': 'system_count', 'ROGUE': 'rogue_count'})
    
    # Calculate cumulative metrics
    all_dates_df['system_cum'] = all_dates_df['system_pnl'].cumsum()
    all_dates_df['rogue_cum'] = all_dates_df['rogue_pnl'].cumsum()
    all_dates_df['total_cum'] = all_dates_df['system_cum'] + all_dates_df['rogue_cum']
    
    # Outlier Analysis
    # Let's define statistical outliers on daily P&L (beyond 2 standard deviations)
    sys_daily_mean = all_dates_df['system_pnl'].mean()
    sys_daily_std = all_dates_df['system_pnl'].std()
    rogue_daily_mean = all_dates_df['rogue_pnl'].mean()
    rogue_daily_std = all_dates_df['rogue_pnl'].std()
    
    # Identify outlier days
    all_dates_df['system_outlier'] = (all_dates_df['system_pnl'] - sys_daily_mean).abs() > (2 * sys_daily_std)
    all_dates_df['rogue_outlier'] = (all_dates_df['rogue_pnl'] - rogue_daily_mean).abs() > (2 * rogue_daily_std)
    
    # Print Markdown Summary Report
    print("# P&L Outlier & Consistency Analysis")
    print(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print("## 1. Summary Statistics of Daily Performance")
    print("| Metric | SYSTEM (Automated) | ROGUE (Manual Discretionary) |")
    print("| :--- | :---: | :---: |")
    print(f"| **Active Trading Days** | {len(all_dates_df[all_dates_df['system_count'] > 0])} days | {len(all_dates_df[all_dates_df['rogue_count'] > 0])} days |")
    print(f"| **Total Net P&L** | **${all_dates_df['system_pnl'].sum():+,.2f}** | **${all_dates_df['rogue_pnl'].sum():+,.2f}** |")
    print(f"| **Mean Daily P&L** | ${sys_daily_mean:+,.2f} | ${rogue_daily_mean:+,.2f} |")
    print(f"| **Daily P&L Volatility (Std Dev)** | ${sys_daily_std:,.2f} | ${rogue_daily_std:,.2f} |")
    print(f"| **Worst Performing Day** | ${all_dates_df['system_pnl'].min():+,.2f} | ${all_dates_df['rogue_pnl'].min():+,.2f} |")
    print(f"| **Best Performing Day** | ${all_dates_df['system_pnl'].max():+,.2f} | ${all_dates_df['rogue_pnl'].max():+,.2f} |")
    print(f"| **Win Days % (Daily P&L > 0)** | {len(all_dates_df[all_dates_df['system_pnl'] > 0]) / max(1, len(all_dates_df[all_dates_df['system_count'] > 0])) * 100:.1f}% | {len(all_dates_df[all_dates_df['rogue_pnl'] > 0]) / max(1, len(all_dates_df[all_dates_df['rogue_count'] > 0])) * 100:.1f}% |\n")
    
    print("## 2. Top Daily Outliers (> 2.0 Std Devs from Mean)")
    print("These are the outlier days causing the largest swings in your equity curve:")
    print("\n### SYSTEM (Automated) Daily Outliers")
    sys_outliers = all_dates_df[all_dates_df['system_outlier'] & (all_dates_df['system_count'] > 0)]
    if not sys_outliers.empty:
        print("| Date | Daily P&L | Trades | Deviation | Notes |")
        print("| :--- | :---: | :---: | :---: | :--- |")
        for date, row in sys_outliers.iterrows():
            dev_val = (row['system_pnl'] - sys_daily_mean) / sys_daily_std
            print(f"| {date} | **${row['system_pnl']:+,.2f}** | {int(row['system_count'])} | {dev_val:+.1f} σ | Normal distribution tail |")
    else:
        print("*No extreme statistical outliers detected for the SYSTEM.*")
        
    print("\n### ROGUE (Manual) Daily Outliers")
    rogue_outliers = all_dates_df[all_dates_df['rogue_outlier'] & (all_dates_df['rogue_count'] > 0)]
    if not rogue_outliers.empty:
        print("| Date | Daily P&L | Trades | Deviation | Diagnosis |")
        print("| :--- | :---: | :---: | :---: | :--- |")
        for date, row in rogue_outliers.iterrows():
            dev_val = (row['rogue_pnl'] - rogue_daily_mean) / rogue_daily_std
            diagnosis = "Tilt / Revenge Trading" if row['rogue_count'] >= 5 and row['rogue_pnl'] < 0 else ("Lucky Win" if row['rogue_pnl'] > 500 else "Standard Volatility")
            print(f"| {date} | **${row['rogue_pnl']:+,.2f}** | {int(row['rogue_count'])} | {dev_val:+.1f} σ | {diagnosis} |")
    else:
        print("*No extreme statistical outliers detected for ROGUE trading.*")
        
    # Analyze the correlation between Trade Count and Daily P&L (Overtrading diagnostic)
    print("\n## 3. Correlation Study: Frequency vs. Daily Return")
    rogue_corr = all_dates_df[all_dates_df['rogue_count'] > 0][['rogue_pnl', 'rogue_count']].corr().iloc[0, 1]
    system_corr = all_dates_df[all_dates_df['system_count'] > 0][['system_pnl', 'system_count']].corr().iloc[0, 1]
    print(f"- **SYSTEM correlation (PnL vs Trade Count)**: `{system_corr:+.3f}` (Expectancy holds at high frequencies)")
    print(f"- **ROGUE correlation (PnL vs Trade Count)**: `{rogue_corr:+.3f}` (A negative correlation indicates that *more* trades taken manually leads to larger drawdowns - classic overtrading symptom)")
    
    # ------------------- PLOTTING -------------------
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Plot 1: Cumulative Equity Curve (Compare System, Rogue, Total)
    axes[0, 0].plot(all_dates_df.index, all_dates_df['system_cum'], label='SYSTEM (Automated)', color=system_color, linewidth=2)
    axes[0, 0].plot(all_dates_df.index, all_dates_df['rogue_cum'], label='ROGUE (Manual)', color=secondary_color, linewidth=2)
    axes[0, 0].plot(all_dates_df.index, all_dates_df['total_cum'], label='TOTAL Net Portfolio', color='white', linewidth=2.5, linestyle='--')
    axes[0, 0].set_title('CUMULATIVE PERFORMANCE COMPARISON', fontsize=12, fontweight='bold', pad=15)
    axes[0, 0].set_ylabel('Net Profit / Loss ($)', fontsize=10)
    axes[0, 0].grid(True, linestyle='--', alpha=0.15, color=muted_gray)
    axes[0, 0].legend(facecolor='black', edgecolor=muted_gray)
    axes[0, 0].axhline(0, color='white', linewidth=0.8, alpha=0.5)
    
    # Plot 2: Daily P&L Distribution (Seaborn KDE / Histogram)
    sys_daily_active = all_dates_df[all_dates_df['system_count'] > 0]['system_pnl']
    rogue_daily_active = all_dates_df[all_dates_df['rogue_count'] > 0]['rogue_pnl']
    
    sns.histplot(sys_daily_active, kde=True, ax=axes[0, 1], color=system_color, label='SYSTEM', alpha=0.4, bins=15, edgecolor='black')
    sns.histplot(rogue_daily_active, kde=True, ax=axes[0, 1], color=secondary_color, label='ROGUE', alpha=0.4, bins=15, edgecolor='black')
    axes[0, 1].set_title('DAILY P&L PROBABILITY DISTRIBUTION', fontsize=12, fontweight='bold', pad=15)
    axes[0, 1].set_xlabel('Daily Return ($)', fontsize=10)
    axes[0, 1].set_ylabel('Frequency (Days)', fontsize=10)
    axes[0, 1].grid(True, linestyle='--', alpha=0.15, color=muted_gray)
    axes[0, 1].axvline(0, color='white', linewidth=1.5, linestyle='-')
    axes[0, 1].legend(facecolor='black', edgecolor=muted_gray)
    
    # Plot 3: Scatter Plot - Trades per Day vs Daily P&L (Frequency Penalty)
    axes[1, 0].scatter(
        all_dates_df[all_dates_df['system_count'] > 0]['system_count'],
        all_dates_df[all_dates_df['system_count'] > 0]['system_pnl'],
        color=system_color, alpha=0.7, s=50, label='SYSTEM'
    )
    axes[1, 0].scatter(
        all_dates_df[all_dates_df['rogue_count'] > 0]['rogue_count'],
        all_dates_df[all_dates_df['rogue_count'] > 0]['rogue_pnl'],
        color=secondary_color, alpha=0.7, s=50, label='ROGUE'
    )
    
    # Draw trendline for Rogue overtrading
    rogue_active_days = all_dates_df[all_dates_df['rogue_count'] > 0]
    if len(rogue_active_days) > 1:
        m, b = np.polyfit(rogue_active_days['rogue_count'], rogue_active_days['rogue_pnl'], 1)
        x_vals = np.linspace(1, rogue_active_days['rogue_count'].max(), 100)
        axes[1, 0].plot(x_vals, m*x_vals + b, color=secondary_color, linestyle=':', label='ROGUE Trendline')
        
    axes[1, 0].set_title('THE FREQUENCY PENALTY (TRADES/DAY vs P&L)', fontsize=12, fontweight='bold', pad=15)
    axes[1, 0].set_xlabel('Number of Trades in a Single Day', fontsize=10)
    axes[1, 0].set_ylabel('Daily Return ($)', fontsize=10)
    axes[1, 0].grid(True, linestyle='--', alpha=0.15, color=muted_gray)
    axes[1, 0].axhline(0, color='white', linewidth=0.8, alpha=0.5)
    axes[1, 0].legend(facecolor='black', edgecolor=muted_gray)
    
    # Plot 4: Boxplot of Daily P&Ls (Visualizing Outlier Range)
    pnl_data_to_plot = [sys_daily_active.values, rogue_daily_active.values]
    bp = axes[1, 1].boxplot(pnl_data_to_plot, patch_artist=True, tick_labels=['SYSTEM', 'ROGUE'])
    
    # Customise Boxplot Colors
    colors = [system_color, secondary_color]
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
        patch.set_edgecolor('white')
        
    for whisker in bp['whiskers']:
        whisker.set(color='white', linewidth=1.5, linestyle=':')
        
    for cap in bp['caps']:
        cap.set(color='white', linewidth=1.5)
        
    for median in bp['medians']:
        median.set(color='yellow', linewidth=2)
        
    for flier in bp['fliers']:
        flier.set(marker='o', color=highlight_color, alpha=0.8, markerfacecolor=highlight_color, markeredgecolor='white')
        
    axes[1, 1].set_title('DAILY P&L BOXPLOT (WHISKERS & OUTLIERS)', fontsize=12, fontweight='bold', pad=15)
    axes[1, 1].set_ylabel('Daily P&L ($)', fontsize=10)
    axes[1, 1].grid(True, linestyle='--', alpha=0.15, color=muted_gray)
    axes[1, 1].axhline(0, color='white', linewidth=0.8, alpha=0.5)
    
    plt.suptitle('BAYESIAN PIVOT P&L DISTRIBUTION & OUTLIER FORENSICS', fontsize=16, fontweight='bold', y=0.96)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    
    # Ensure directory exists and save
    os.makedirs('docs/images', exist_ok=True)
    plot_path = 'docs/images/pnl_distribution_analysis.png'
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\n📊 Visualization dashboard saved successfully to: {plot_path}")

if __name__ == '__main__':
    generate_report_and_plots()
