import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

def generate_heatmap():
    print("🎨 Generating Premium Combinatorial Heatmap...")
    
    # 1. Load Data
    csv_path = "data/combinatorial_results.csv"
    if not os.path.exists(csv_path):
        print(f"❌ Could not find {csv_path}")
        return
        
    df = pd.read_csv(csv_path)
    
    # Set premium dark mode style
    plt.style.use('dark_background')
    sns.set_theme(style="darkgrid", rc={
        "axes.facecolor": "#0d1117",
        "figure.facecolor": "#0d1117",
        "grid.color": "#21262d",
        "text.color": "#c9d1d9",
        "axes.labelcolor": "#8b949e",
        "xtick.color": "#8b949e",
        "ytick.color": "#8b949e",
        "font.family": "sans-serif",
    })
    
    fig, ax = plt.subplots(figsize=(14, 10))
    
    # 2. Prepare Pivot Table
    # To display 5 dimensions, we aggregate into a 2D pivot table.
    # Y-axis: Core Signal (Hurst + Bias)
    # X-axis: Confirmation (SMT + Volume)
    
    df['Core Signal'] = df.apply(lambda r: f"Hurst:{r['Hurst']} | Bias:{r['Bias']}", axis=1)
    df['Confirmation'] = df.apply(lambda r: f"SMT:{r['SMT']} | Vol:{r['Volume']}", axis=1)
    
    # Aggregate by average Sharpe Ratio (averaging out the 'News' boolean)
    pivot = pd.pivot_table(df, values='Sharpe', index='Core Signal', columns='Confirmation', aggfunc='mean')
    
    # 3. Draw Heatmap
    # Use a vibrant custom colormap (Red to Green / Plasma)
    cmap = sns.diverging_palette(10, 130, as_cmap=True, s=90, l=45)
    
    sns.heatmap(
        pivot, 
        annot=True, 
        fmt=".2f", 
        cmap=cmap, 
        center=0, 
        linewidths=1.5, 
        linecolor="#0d1117", 
        cbar_kws={"label": "Sharpe Ratio (Return/Risk)"},
        annot_kws={"size": 12, "weight": "bold"},
        ax=ax
    )
    
    # 4. Styling
    ax.set_title("9-Gate Funnel: Combinatorial Edge Matrix", fontsize=22, weight='bold', color='#58a6ff', pad=25)
    ax.set_xlabel("Secondary Confirmation Gates", fontsize=14, weight='bold', labelpad=15)
    ax.set_ylabel("Primary Regime Filters", fontsize=14, weight='bold', labelpad=15)
    
    plt.xticks(rotation=15, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    
    # 5. Save Output
    os.makedirs("data/images", exist_ok=True)
    out_path = "data/images/combinatorial_heatmap.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor="#0d1117")
    print(f"✅ Visualization saved to {out_path}")
    plt.close()

if __name__ == "__main__":
    generate_heatmap()
