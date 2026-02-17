import numpy as np
import matplotlib.pyplot as plt

class PropFirmScaler:
    def __init__(
        self,
        starting_capital=100000,  # Current 2x $50k accounts
        monthly_return_rate=0.03,  # Conservative 3% monthly (based on 0.65% risk)
        challenge_cost=500,  # Average prop firm challenge cost
        challenge_size=50000,  # Capital unlocked per passed challenge
        reinvest_percentage=0.50,  # 50% of profits go to new challenges
        months_to_simulate=24
    ):
        self.starting_capital = starting_capital
        self.monthly_return = monthly_return_rate
        self.challenge_cost = challenge_cost
        self.challenge_size = challenge_size
        self.reinvest_pct = reinvest_percentage
        self.months = months_to_simulate
        
    def simulate_scaling(self):
        """
        Simulates prop firm scaling with profit reinvestment.
        REALISTIC CONSTRAINTS:
        - Most prop firms cap you at 5-10 accounts max
        - Max capital per firm: ~$500k-$1M
        - After hitting cap, you withdraw profit instead of reinvesting
        
        Returns: timeline of total capital, profit breakdown, and challenge purchases.
        """
        total_capital = self.starting_capital
        profit_pool = 0.0
        total_accounts = 2  # Starting with 2x $50k
        
        # REALISTIC LIMITS
        MAX_ACCOUNTS_PER_FIRM = 10
        MAX_TOTAL_CAPITAL = 1000000  # $1M cap (realistic prop firm limit)
        
        timeline = []
        challenges_purchased = []
        hit_cap = False
        
        print("🚀 PROP FIRM SCALING SIMULATION (REALISTIC)")
        print(f"Starting Capital: ${self.starting_capital:,.0f} ({total_accounts} accounts)")
        print(f"Max Capital Allowed: ${MAX_TOTAL_CAPITAL:,.0f}")
        print(f"Target: 2x every 2 months (until cap)")
        print("="*70)
        
        for month in range(1, self.months + 1):
            # 1. Generate monthly profit
            monthly_profit = total_capital * self.monthly_return
            profit_pool += monthly_profit
            
            # 2. Check if we've hit the cap
            if total_capital >= MAX_TOTAL_CAPITAL:
                if not hit_cap:
                    print(f"\n🎯 CAPITAL CAP REACHED at Month {month}")
                    print(f"   Total Capital: ${total_capital:,.0f}")
                    print(f"   From here: All profits go to withdrawal pool\n")
                    hit_cap = True
                
                # No more reinvestment, just accumulate withdrawals
                timeline.append({
                    'month': month,
                    'total_capital': total_capital,
                    'monthly_profit': monthly_profit,
                    'profit_pool': profit_pool,
                    'challenges_bought': 0,
                    'status': 'CAPPED'
                })
                
                # Print withdrawal milestones
                if month % 2 == 0:
                    print(f"Month {month:2d}: ${total_capital:,.0f} (Capped) | Withdrawal Pool: ${profit_pool:,.0f}")
                continue
            
            # 3. Reinvest portion into new challenges (if under cap)
            reinvest_amount = monthly_profit * self.reinvest_pct
            num_challenges = int(reinvest_amount // self.challenge_cost)
            
            # Cap challenges based on remaining room
            max_new_capital = MAX_TOTAL_CAPITAL - total_capital
            max_challenges_by_cap = int(max_new_capital / (self.challenge_size * 0.80))
            num_challenges = min(num_challenges, max_challenges_by_cap)
            
            if num_challenges > 0 and total_accounts < MAX_ACCOUNTS_PER_FIRM:
                # Buy new challenges
                cost = num_challenges * self.challenge_cost
                profit_pool -= cost
                
                # Add new capital (assuming 80% pass rate on challenges)
                new_capital = num_challenges * self.challenge_size * 0.80
                total_capital += new_capital
                total_accounts += num_challenges
                
                challenges_purchased.append({
                    'month': month,
                    'challenges': num_challenges,
                    'cost': cost,
                    'capital_added': new_capital
                })
            
            timeline.append({
                'month': month,
                'total_capital': total_capital,
                'monthly_profit': monthly_profit,
                'profit_pool': profit_pool,
                'challenges_bought': num_challenges,
                'status': 'SCALING'
            })
            
            # Print milestone updates
            if month % 2 == 0:  # Every 2 months
                growth = ((total_capital - self.starting_capital) / self.starting_capital) * 100
                print(f"Month {month:2d}: ${total_capital:,.0f} | Growth: {growth:+.1f}% | Accounts: {total_accounts}")
        
        return timeline, challenges_purchased
    
    def plot_trajectory(self, timeline):
        """Visualizes capital growth over time."""
        months = [t['month'] for t in timeline]
        capital = [t['total_capital'] for t in timeline]
        
        plt.figure(figsize=(12, 6))
        plt.plot(months, capital, linewidth=2, color='#00ff00')
        plt.axhline(y=self.starting_capital, color='gray', linestyle='--', label='Starting Capital')
        plt.axhline(y=self.starting_capital * 2, color='orange', linestyle='--', label='2x Target (2mo)')
        plt.axhline(y=self.starting_capital * 4, color='red', linestyle='--', label='4x Target (4mo)')
        
        plt.title('Prop Firm Capital Scaling (Reinvestment Model)', fontsize=14, fontweight='bold')
        plt.xlabel('Month')
        plt.ylabel('Total Capital ($)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig('/Users/nicholasmacaskill/sovereignSMC/sovereignSMC/scaling_trajectory.png', dpi=150)
        print("\n✅ Chart saved: scaling_trajectory.png")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("SCENARIO 1: Single Firm Cap (Conservative)")
    print("="*70)
    
    # Run simulation with single-firm cap
    scaler = PropFirmScaler(
        starting_capital=100000,
        monthly_return_rate=0.03,  # 3% monthly (conservative)
        reinvest_percentage=0.50,  # 50% of profit → new challenges
        months_to_simulate=12
    )
    
    timeline, challenges = scaler.simulate_scaling()
    
    # Final Summary
    final = timeline[-1]
    total_growth = ((final['total_capital'] - scaler.starting_capital) / scaler.starting_capital) * 100
    
    print("\n" + "="*70)
    print("📊 RESULTS (12 Months, Single Firm)")
    print("="*70)
    print(f"Starting Capital: ${scaler.starting_capital:,.0f}")
    print(f"Ending Capital:   ${final['total_capital']:,.0f}")
    print(f"Total Growth:     {total_growth:.1f}%")
    print(f"Withdrawal Pool:  ${final['profit_pool']:,.0f}")
    
    print("\n" + "="*70)
    print("SCENARIO 2: Multi-Firm Unlimited Scaling (Aggressive)")
    print("="*70)
    
    # Simulate unlimited scaling across multiple firms
    total_capital = 100000
    profit_pool = 0.0
    monthly_return = 0.03
    reinvest_pct = 0.50
    challenge_cost = 500
    challenge_size = 50000
    
    print("\n🚀 UNLIMITED MULTI-FIRM SCALING")
    print("Assumption: You can scale across infinite prop firms")
    print("="*70)
    
    for month in range(1, 13):
        monthly_profit = total_capital * monthly_return
        profit_pool += monthly_profit
        
        # Reinvest 50%
        reinvest_amount = monthly_profit * reinvest_pct
        num_challenges = int(reinvest_amount // challenge_cost)
        
        if num_challenges > 0:
            cost = num_challenges * challenge_cost
            profit_pool -= cost
            new_capital = num_challenges * challenge_size * 0.80  # 80% pass rate
            total_capital += new_capital
        
        if month % 2 == 0:
            print(f"Month {month:2d}: ${total_capital:,.0f} | Withdrawal Pool: ${profit_pool:,.0f}")
    
    year_growth = ((total_capital - 100000) / 100000) * 100
    
    print("\n" + "="*70)
    print("📊 RESULTS (12 Months, Multi-Firm)")
    print("="*70)
    print(f"Starting Capital:     ${100000:,.0f}")
    print(f"Ending Capital:       ${total_capital:,.0f}")
    print(f"Total Growth:         {year_growth:.1f}%")
    print(f"Total Withdrawn:      ${profit_pool:,.0f}")
    print(f"\n💰 Year 1 Total Earnings: ${profit_pool:,.0f}")
    print(f"📈 Year 2 Monthly Income: ${total_capital * 0.03:,.0f}/month (if you stop reinvesting)")

