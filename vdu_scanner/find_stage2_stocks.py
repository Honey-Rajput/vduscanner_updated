import sys
import os
import pandas as pd
from tabulate import tabulate

# Ensure we can import from current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_index_stocks, fetch_ohlcv_timeframe
from scanner import scan_monthly_early_stage2

def run_scanner(universe="NIFTY 100"):
    print(f"Fetching symbols for {universe}...")
    symbols = get_index_stocks(universe)
    
    if not symbols:
        print("No symbols found.")
        return
        
    print(f"Total symbols to scan: {len(symbols)}")
    print("Starting scan (Monthly Early Stage 2 Base Breakout)...")
    
    results = []
    
    for i, symbol in enumerate(symbols):
        print(f"[{i+1}/{len(symbols)}] Scanning {symbol}...", end='\r')
        # Fetch 5 years of monthly data
        df_monthly = fetch_ohlcv_timeframe(symbol, interval="1mo", period="5y")
        
        if df_monthly is not None and not df_monthly.empty:
            res = scan_monthly_early_stage2(symbol, df_monthly, max_run_up_pct=20.0)
            if res:
                results.append(res)
                
    print("\nScan complete!")
    
    if results:
        print(f"\nFound {len(results)} stocks matching the Early Stage 2 Base Breakout criteria:")
        
        # Sort by signal strength (descending)
        results = sorted(results, key=lambda x: x['score'], reverse=True)
        
        table_data = []
        for r in results:
            table_data.append([
                r['symbol'],
                f"₹{r['buy_price']:.2f}",
                f"₹{r['base_bottom']:.2f}",
                f"₹{r['historical_high']:.2f}",
                f"{r['extension']:.1f}%",
                f"₹{r['sma7']:.2f}",
                r['score'],
                f"₹{r['buy_price']:.2f}",
                f"₹{r['exit_price']:.2f}",
                f"₹{r['target_price']:.2f}"
            ])
            
        headers = ["Symbol", "CMP", "Base Bottom", "Historical High", "Extension %", "7M SMA", "Score", "Buy", "Stop Loss", "Target"]
        print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print("\nNo stocks found matching the criteria.")

if __name__ == "__main__":
    universe = "NIFTY 500" # Defaulting to a broader universe for more candidates
    if len(sys.argv) > 1:
        universe = sys.argv[1]
    run_scanner(universe)
