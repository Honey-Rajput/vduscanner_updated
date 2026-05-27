# scanner.py
import pandas as pd
import numpy as np
from config import DRY_VOLUME_THRESHOLD, MIN_VOLUME_RATIO, MIN_PRICE_CHANGE, DRY_ZONE_MIN_DAYS, DRY_ZONE_MAX_DAYS

def scan_stock(
    symbol: str, 
    df: pd.DataFrame, 
    min_dry_days: int = DRY_ZONE_MIN_DAYS, 
    max_dry_days: int = DRY_ZONE_MAX_DAYS,
    min_volume_ratio: float = MIN_VOLUME_RATIO,
    min_price_change: float = MIN_PRICE_CHANGE,
    min_dry_spikes: int = 2
) -> dict | None:
    """
    Evaluates a stock's OHLCV history for the Volume Dry-Up (VDU) Breakout pattern.
    
    STEP 1: Calculate baseline average volume over available history (up to last 90 days).
    STEP 2: Exclude today's breakout day and search backward for the most recent 
            Dry Zone of length between min_dry_days and max_dry_days, requiring at least 
            min_dry_spikes where volume exceeds 40% of baseline volume (accumulation spikes).
    STEP 3: Evaluate today's candle for the breakout pattern (Volume surge, bullish candle, minimum price change).
    STEP 4: Calculate the Signal Strength Score (0 to 100).
    
    Returns a dictionary of scan metrics and modified DataFrame if matched, otherwise None.
    """
    if df is None or len(df) < 50:
        # We need at least 50 trading days to compute standard indicators (like 50 DMA) and scan for VDU
        return None
        
    # --- STEP 1: Baseline Volume ---
    # Take the last 90 trading days to compute the baseline average volume
    baseline_subset = df.iloc[-90:] if len(df) >= 90 else df
    baseline_avg_vol = baseline_subset['Volume'].mean()
    
    if baseline_avg_vol <= 0:
        return None
        
    # Enforce at least 1 day of dry consolidation to prevent division by zero or NaN average volumes
    min_dry_days = max(1, min_dry_days)
    
    # --- STEP 2: Find Dry Zone (Exclude Today) ---
    # Exclude the latest day (today's candle) to scan historical dry period
    history_df = df.iloc[:-1].reset_index(drop=True)
    
    # Identify indices that DO NOT qualify as dry days (Volume > 40% of baseline volume)
    is_not_dry_mask = history_df['Volume'] > (DRY_VOLUME_THRESHOLD * baseline_avg_vol)
    
    best_window = None  # Format: (start_idx, end_idx, length, not_dry_count, dry_avg_vol)
    min_found_avg_vol = float('inf')
    
    # Scan only recent days (at most 10 trading days back) to guarantee the consolidation ended recently
    search_start_idx = len(history_df) - 1
    search_end_idx = max(0, len(history_df) - 10)
    
    for idx in range(search_start_idx, search_end_idx - 1, -1):
        # Check window lengths from min_dry_days up to max_dry_days to find the best tight dry zone
        for L in range(min_dry_days, max_dry_days + 1):
            start_idx = idx - L + 1
            if start_idx < 0:
                continue
                
            # Calculate average volume of this candidate dry zone window
            dry_zone_df = history_df.iloc[start_idx : idx + 1]
            dry_avg_vol = dry_zone_df['Volume'].mean()
            
            # Enforce quality filter: consolidation zone average volume MUST be dry (<= 60% of baseline average)
            if dry_avg_vol > 0 and dry_avg_vol <= (0.60 * baseline_avg_vol):
                # Count spikes (non-dry volume days where Volume > 40% of baseline) inside the window
                not_dry_count = is_not_dry_mask.iloc[start_idx : idx + 1].sum()
                if not_dry_count >= min_dry_spikes:
                    # We found a valid dry window! Select the driest one to represent the highest quality contraction
                    if dry_avg_vol < min_found_avg_vol:
                        min_found_avg_vol = dry_avg_vol
                        best_window = (start_idx, idx, L, int(not_dry_count), dry_avg_vol)
                        
    if best_window is None:
        return None
        
    start_idx, end_idx, dry_days_count, dry_spikes, dry_avg_vol = best_window
        
    # --- STEP 3: Today's Breakout Check ---
    today = df.iloc[-1]
    yesterday = df.iloc[-2] if len(df) >= 2 else today
    volume_ratio = today['Volume'] / dry_avg_vol
    
    # Condition a) Volume surge
    volume_surge_ok = volume_ratio >= min_volume_ratio
    # Condition b) Bullish candle close is higher than open OR it is a massive gap-up continuation
    bullish_candle_ok = today['Close'] > today['Open'] or today['Close'] > yesterday['Close']
    # Condition c) Price breakout of at least min_price_change (either Close-to-Close or Intraday Close-to-Open)
    pct_change_intraday = (today['Close'] - today['Open']) / today['Open'] * 100
    pct_change_close = ((today['Close'] - yesterday['Close']) / yesterday['Close'] * 100) if len(df) >= 2 else pct_change_intraday
    price_change_ok = (pct_change_intraday >= min_price_change) or (pct_change_close >= min_price_change)
    
    if not (volume_surge_ok and bullish_candle_ok and price_change_ok):
        return None
        
    # --- STEP 4: Signal Strength Score (0 to 100) & Indicators ---
    df_indicators = df.copy()
    df_indicators['MA50'] = df_indicators['Close'].rolling(window=50).mean()
    
    today_ma = df_indicators['MA50'].iloc[-1]
    above_50dma = False
    if not pd.isna(today_ma):
        above_50dma = today['Close'] > today_ma
        
    # Calculate score weights
    score = 0.0
    # 1. Volume ratio: Up to 40 points
    score += min(volume_ratio / 10.0 * 40.0, 40.0)
    # 2. Price move: Up to 30 points
    score += min(max(pct_change_intraday, pct_change_close) / 5.0 * 30.0, 30.0)
    # 3. Dry duration: Up to 20 points
    score += min(dry_days_count / 60.0 * 20.0, 20.0)
    # 4. Moving Average filter: 10 points
    if above_50dma:
        score += 10.0
        
    score = round(min(score, 100.0), 1)
    
    # Calculate day-over-day price change (standard Close-to-Close change)
    day_change_pct = pct_change_close
    
    # Calculate available 120-day high and low
    high_120d = float(df['High'].max())
    low_120d = float(df['Low'].min())
    
    # Advanced Trading Setup Calculations:
    buy_price = round(float(today['Close']), 2)
    # Swing low stop loss: lowest price of the last 5 days (pullback anchor) minus 2% buffer
    min_5d_low = float(df['Low'].iloc[-5:].min())
    exit_price = round(min(buy_price * 0.95, min_5d_low * 0.98), 2)
    # Target: 15% swing trade objective
    target_price = round(buy_price * 1.15, 2)
    
    # Confidence text based on algorithmic signal strength
    if score >= 75:
        confidence = f"High Conviction ({score}%)"
    elif score >= 50:
        confidence = f"Medium-High ({score}%)"
    else:
        confidence = f"Medium ({score}%)"
        
    base_rec = (
        f"Strong institutional VDU breakout! Volume ratio is {volume_ratio:.1f}x with signal score {score}%. "
        f"Buy around CMP ₹{buy_price:.2f}. Set stop loss at swing low ₹{exit_price:.2f} (risk {(buy_price-exit_price)/buy_price*100:.1f}%) "
        f"with a target of ₹{target_price:.2f} (potential +15.0%)."
    )
    recommendation = compute_rich_analysis(df_indicators, symbol, "VDU Breakout", base_rec)
    
    from config import get_company_name
    company_name = get_company_name(symbol)
    
    return {
        "symbol": symbol.strip().upper(),
        "company_name": company_name,
        "cmp": buy_price,
        "day_change_pct": round(day_change_pct, 2),
        "today_volume": int(today['Volume']),
        "dry_avg_vol": round(dry_avg_vol, 1),
        "volume_ratio": round(volume_ratio, 2),
        "dry_days_count": int(dry_days_count),
        "dry_spikes": dry_spikes,
        "dry_start_date": pd.to_datetime(history_df['Date'].iloc[start_idx]),
        "dry_end_date": pd.to_datetime(history_df['Date'].iloc[end_idx]),
        "signal_strength": score,
        "pct_change_today": round(day_change_pct, 2),
        "above_50dma": above_50dma,
        "df": df_indicators,
        "high_52w": high_120d,      
        "low_52w": low_120d,
        "buy_price": buy_price,
        "exit_price": exit_price,
        "target_price": target_price,
        "confidence": confidence,
        "recommendation": recommendation
    }

def scan_coiled_spring(symbol: str, df: pd.DataFrame) -> dict | None:
    """
    Scans a stock's history to identify if it is in a "Final Contraction" (Coiled Spring / VCP) setup.
    This represents an extremely tight price consolidation with dried volume prior to breakout.
    
    1. Uptrend Filter: Close > 50 SMA, 50 SMA > 100 SMA.
    2. Volatility Squeeze: 5-Day High-Low range <= 4.0% and tighter than preceding 5-day range.
    3. Volume Dry-Up: 5-Day average volume <= 50% of 50-day average volume baseline, and declining.
    """
    if df is None or len(df) < 50:
        return None
        
    # --- STEP 1: Uptrend Filter ---
    df_copy = df.copy()
    df_copy['MA50'] = df_copy['Close'].rolling(window=50).mean()
    df_copy['MA100'] = df_copy['Close'].rolling(window=100).mean()
    df_copy['EMA20'] = df_copy['Close'].ewm(span=20, adjust=False).mean()
    
    today = df_copy.iloc[-1]
    
    # 50 SMA and 100 SMA calculations
    today_ma50 = today['MA50']
    today_ma100 = today['MA100']
    
    if pd.isna(today_ma50) or pd.isna(today_ma100):
        return None
        
    # Standard VCP uptrend check: Close is above 50 SMA, and 50 SMA is above 100 SMA
    uptrend_ok = today['Close'] > today_ma50 and today_ma50 > today_ma100
    if not uptrend_ok:
        return None
        
    # --- STEP 2: Volatility Contraction Squeeze ---
    # We inspect Segment A (last 5 trading days) and Segment B (preceding 5 trading days, days -10 to -5)
    segment_a = df_copy.iloc[-5:]
    segment_b = df_copy.iloc[-10:-5]
    
    if len(segment_a) < 5 or len(segment_b) < 5:
        return None
        
    # High-Low Range for Segment A (%)
    max_h_a = segment_a['High'].max()
    min_l_a = segment_a['Low'].min()
    range_a = ((max_h_a - min_l_a) / min_l_a) * 100
    
    # High-Low Range for Segment B (%)
    max_h_b = segment_b['High'].max()
    min_l_b = segment_b['Low'].min()
    range_b = ((max_h_b - min_l_b) / min_l_b) * 100
    
    # Check 1: Extreme Price Tightness (Range_5d <= 4.0%)
    tightness_ok = range_a <= 4.0
    # Check 2: Volatility is actively contracting (Range_5d < Range_10d_5d)
    contraction_ok = range_a < range_b
    
    if not (tightness_ok and contraction_ok):
        return None
        
    # --- STEP 3: Volume Dry-Up (VDU) ---
    # 50-day average baseline volume
    baseline_subset = df_copy.iloc[-50:]
    baseline_avg_vol = baseline_subset['Volume'].mean()
    
    if baseline_avg_vol <= 0:
        return None
        
    # Average volume for Segment A and Segment B
    avg_vol_a = segment_a['Volume'].mean()
    avg_vol_b = segment_b['Volume'].mean()
    
    # Check 1: Volume is severely dried up (AvgVolume_5d <= 50% of 50-day baseline)
    vol_dry_ok = avg_vol_a <= (0.50 * baseline_avg_vol)
    # Check 2: Volume is actively declining (AvgVolume_5d < AvgVolume_10d_5d)
    vol_declining_ok = avg_vol_a < avg_vol_b
    
    if not (vol_dry_ok and vol_declining_ok):
        return None
        
    # --- STEP 4: Squeeze Score Calculation ---
    # 1. Tightness factor: Up to 50 pts
    score_tightness = max(0.0, 100.0 - (range_a / 4.0 * 100.0)) / 2.0
    # 2. Volume dry-up factor: Up to 30 pts
    score_volume = max(0.0, 1.0 - (avg_vol_a / (0.50 * baseline_avg_vol))) * 30.0
    # 3. Support trend factor: 20 pts if closing above 20 EMA
    score_trend = 20.0 if today['Close'] > today['EMA20'] else 0.0
    
    squeeze_score = round(min(score_tightness + score_volume + score_trend, 100.0), 1)
    
    # Day change pct for reporting
    yesterday = df_copy.iloc[-2] if len(df_copy) >= 2 else today
    day_change_pct = ((today['Close'] - yesterday['Close']) / yesterday['Close'] * 100) if len(df_copy) >= 2 else 0.0
    
    # Advanced Trading Setup Calculations for Coiled Spring VCP Squeeze
    buy_price = round(float(today['Close']), 2)
    # Tight VCP stop loss at 4%
    exit_price = round(buy_price * 0.96, 2)
    # 15% target
    target_price = round(buy_price * 1.15, 2)
    
    if squeeze_score >= 75:
        confidence = f"High ({squeeze_score}%)"
    else:
        confidence = f"Medium-High ({squeeze_score}%)"
        
    base_rec = (
        f"Extremely tight volatility contraction (VCP) squeeze score of {squeeze_score}%. "
        f"Buy at CMP ₹{buy_price:.2f} with a tight stop loss just below contraction support at ₹{exit_price:.2f} "
        f"(risk 4.0%) and look for a strong breakout toward target ₹{target_price:.2f} (+15.0%)."
    )
    recommendation = compute_rich_analysis(df_copy, symbol, "VCP Squeeze", base_rec)

    from config import get_company_name
    company_name = get_company_name(symbol)
    
    return {
        "symbol": symbol.strip().upper(),
        "company_name": company_name,
        "cmp": buy_price,
        "day_change_pct": round(day_change_pct, 2),
        "range_5d": round(range_a, 2),
        "range_prev": round(range_b, 2),
        "avg_vol_5d": round(avg_vol_a, 1),
        "baseline_avg_vol": round(baseline_avg_vol, 1),
        "vol_ratio": round(avg_vol_a / baseline_avg_vol, 2),
        "squeeze_score": squeeze_score,
        "above_20ema": today['Close'] > today['EMA20'],
        "df": df_copy,
        "buy_price": buy_price,
        "exit_price": exit_price,
        "target_price": target_price,
        "confidence": confidence,
        "recommendation": recommendation
    }

def scan_wt_cross(symbol: str, df: pd.DataFrame) -> dict | None:
    """
    Scans a stock's history to calculate WaveTrend with Crosses [LazyBear] (WT_CROSS_LB).
    Returns WT details if wt1 <= -40.0 (oversold zone).
    Also detects bullish buy signal (green dot): wt1 crosses above wt2 from oversold zone.
    
    Mathematical details:
    ap = Typical Price = (High + Low + Close) / 3
    esa = EMA(ap, n1=10)
    d = EMA(abs(ap - esa), n1=10)
    ci = (ap - esa) / (0.015 * d)
    wt1 = EMA(ci, n2=21)
    wt2 = SMA(wt1, 4)
    
    Buy signal (green dot): wt1 crosses above wt2 while in oversold zone (wt2 <= -40)
    """
    if df is None or len(df) < 40:
        return None
        
    df_copy = df.copy()
    
    # Typical price: hlc3
    ap = (df_copy['High'] + df_copy['Low'] + df_copy['Close']) / 3.0
    
    # esa = ema(ap, 10)
    esa = ap.ewm(span=10, adjust=False).mean()
    
    # d = ema(abs(ap - esa), 10)
    d = (ap - esa).abs().ewm(span=10, adjust=False).mean()
    
    # ci = (ap - esa) / (0.015 * d)
    ci = (ap - esa) / (0.015 * d + 1e-10)
    
    # wt1 = tci = ema(ci, 21)
    wt1 = ci.ewm(span=21, adjust=False).mean()
    
    # wt2 = sma(wt1, 4)
    wt2 = wt1.rolling(window=4).mean()
    
    today_wt1 = wt1.iloc[-1]
    today_wt2 = wt2.iloc[-1]
    
    if pd.isna(today_wt1) or pd.isna(today_wt2):
        return None
        
    # Check if wt1 is in oversold zone (below -40)
    if today_wt1 > -40.0:
        return None
    
    today = df_copy.iloc[-1]
    yesterday = df_copy.iloc[-2] if len(df_copy) >= 2 else today
    day_change_pct = ((today['Close'] - yesterday['Close']) / yesterday['Close'] * 100) if len(df_copy) >= 2 else 0.0
    
    # Detect buy signal (green dot): wt1 crosses above wt2
    # We check if a bullish crossover (green dot) occurred recently (today or within the last 3 days/bars)
    # to highlight stocks that are in active buying stages.
    buy_signal = False
    for offset in range(1, 4):
        if len(wt1) > offset and len(wt2) > offset:
            t_wt1 = wt1.iloc[-offset]
            t_wt2 = wt2.iloc[-offset]
            p_wt1 = wt1.iloc[-offset - 1]
            p_wt2 = wt2.iloc[-offset - 1]
            if not pd.isna(t_wt1) and not pd.isna(t_wt2) and not pd.isna(p_wt1) and not pd.isna(p_wt2):
                if (p_wt1 <= p_wt2) and (t_wt1 > t_wt2):
                    buy_signal = True
                    break
    
    # Advanced Trading Setup Calculations for WaveTrend
    buy_price = round(float(today['Close']), 2)
    exit_price = round(buy_price * 0.95, 2)
    target_price = round(buy_price * 1.12, 2)
    
    # Calculate SMAs to see if price is trading above 20 SMA & 50 SMA
    df_copy['SMA20'] = df_copy['Close'].rolling(window=20).mean()
    df_copy['SMA50'] = df_copy['Close'].rolling(window=50).mean()
    today_sma20 = df_copy['SMA20'].iloc[-1]
    today_sma50 = df_copy['SMA50'].iloc[-1]
    above_20sma = bool(buy_price > today_sma20) if not pd.isna(today_sma20) else False
    above_50sma = bool(buy_price > today_sma50) if not pd.isna(today_sma50) else False

    if buy_signal:
        confidence = "High (WT Buy Signal)"
        base_rec = (
            f"Bullish mean-reversion buy signal (LazyBear Green Dot) triggered in oversold zone! "
            f"WT1 is {today_wt1:.1f} and crossed above WT2. Buy around CMP ₹{buy_price:.2f}. "
            f"Place stop loss at ₹{exit_price:.2f} (risk 5.0%) with a target bounce at ₹{target_price:.2f} (+12.0%)."
        )
    else:
        confidence = "Medium (WT Oversold)"
        base_rec = (
            f"Stock is in a deep WaveTrend oversold zone (WT1 = {today_wt1:.1f} is below -40). "
            f"No green dot cross yet, but prime for accumulation. Buy on pullbacks near ₹{buy_price:.2f} "
            f"with stop loss at ₹{exit_price:.2f} and target bounce of ₹{target_price:.2f}."
        )
    recommendation = compute_rich_analysis(df_copy, symbol, "WaveTrend Cross", base_rec)

    from config import get_company_name
    company_name = get_company_name(symbol)
    
    return {
        "symbol": symbol.strip().upper(),
        "company_name": company_name,
        "cmp": buy_price,
        "day_change_pct": round(day_change_pct, 2),
        "wt_value": round(today_wt1, 2),
        "wt2_value": round(today_wt2, 2),
        "buy_signal": buy_signal,
        "wt_diff": round(today_wt1 - today_wt2, 2),
        "volume": int(today['Volume']),
        "buy_price": buy_price,
        "exit_price": exit_price,
        "target_price": target_price,
        "confidence": confidence,
        "recommendation": recommendation,
        "above_20sma": above_20sma,
        "above_50sma": above_50sma
    }

def compute_rich_analysis(df, symbol, strategy_name, base_rec_text):
    """
    Computes CCI, RSI, EMA, SMA and checklist triggers, 
    and returns a structured JSON recommendation string.
    """
    if df is None or len(df) < 14:
        return base_rec_text
        
    try:
        import pandas as pd
        import json
        
        # Standard indicators
        close_series = df['Close']
        high_series = df['High']
        low_series = df['Low']
        
        # 1. RSI (14)
        delta = close_series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        ema_gain = gain.ewm(com=13, adjust=False).mean()
        ema_loss = loss.ewm(com=13, adjust=False).mean()
        rs = ema_gain / (ema_loss + 1e-9)
        rsi_series = 100 - (100 / (1 + rs))
        rsi_val = float(rsi_series.iloc[-1])
        
        # 2. CCI (14)
        tp = (high_series + low_series + close_series) / 3
        sma_tp = tp.rolling(window=14).mean()
        mad_manual = tp.rolling(window=14).apply(lambda x: abs(x - x.mean()).mean(), raw=True)
        cci_series = (tp - sma_tp) / (0.015 * mad_manual + 1e-9)
        cci_val = float(cci_series.iloc[-1])
        
        # 3. Moving Averages
        ema20 = float(close_series.ewm(span=20, adjust=False).mean().iloc[-1])
        sma50 = float(close_series.rolling(window=50).mean().iloc[-1]) if len(df) >= 50 else float(close_series.iloc[-1])
        sma200 = float(close_series.rolling(window=200).mean().iloc[-1]) if len(df) >= 200 else float(close_series.iloc[-1])
        cmp = float(close_series.iloc[-1])
        
        # 4. Interpretations & Status
        if rsi_val >= 70:
            rsi_status = "Overbought"
            rsi_interp = "Extremely strong bullish momentum; check for near-term exhaustion."
        elif rsi_val >= 50:
            rsi_status = "Bullish Momentum"
            rsi_interp = "Solid buying interest with strong upward price power."
        elif rsi_val >= 35:
            rsi_status = "Neutral Consolidation"
            rsi_interp = "Price is stable, hovering within a sideways range."
        else:
            rsi_status = "Oversold Bounce"
            rsi_interp = "Deep oversold territory; highly prime for a technical recovery."
            
        if cci_val >= 100:
            cci_status = "Bullish Breakout"
            cci_interp = "Price velocity is in a strong upward breakout phase."
        elif cci_val >= 0:
            cci_status = "Positive Territory"
            cci_interp = "Short-term momentum is supportive of higher prices."
        elif cci_val >= -100:
            cci_status = "Weak Momentum"
            cci_interp = "Trading in bearish territory, under consolidation."
        else:
            cci_status = "Extremely Oversold"
            cci_interp = "Deep oversold condition; expect a sharp mean-reversion move."
            
        # Triggers Checklist
        triggers = []
        if cmp > sma50 and sma50 > sma200:
            triggers.append("✔️ Golden Trend: Price is supported by long-term institutional SMA structure.")
        elif cmp > sma50:
            triggers.append("✔️ Mid-Term Bullish: Trading comfortably above the 50-day moving average.")
            
        if rsi_val >= 50 and rsi_val <= 68:
            triggers.append("✔️ RSI Sweet Spot: Healthy buying momentum without being overextended.")
        elif rsi_val < 35:
            triggers.append("✔️ Reversion Alert: Deeply discounted oversold price levels ready to bounce.")
            
        if cci_val > 100:
            triggers.append("✔️ Momentum Surge: CCI confirms active breakout velocity is backing the move.")
        elif cci_val < -100:
            triggers.append("✔️ Oversold Stretch: CCI indicates institutional selling is exhausted.")
            
        if cmp >= ema20 * 0.98 and cmp <= ema20 * 1.02:
            triggers.append("✔️ Dynamic Pullback: Price is pulling back perfectly into the 20-day EMA support anchor.")
        elif cmp > ema20:
            triggers.append("✔️ Fast Trend: Sustained buying velocity holding above the short-term 20 EMA.")
            
        if not triggers:
            triggers.append("✔️ Value Consolidation: Standard technical entry on strategy parameters.")
            
        # Determine the price position relative to MAs dynamically
        ma_reasoning = ""
        if cmp > ema20 and cmp > sma50:
            ma_reasoning = f"Price holds strong above short-term 20 EMA (₹{ema20:,.2f}) and medium-term 50 SMA (₹{sma50:,.2f}), confirming dynamic uptrend support."
        elif cmp > ema20:
            ma_reasoning = f"Price is trading above the fast-moving 20 EMA (₹{ema20:,.2f}), while testing major resistance/consolidation zones."
        elif cmp > sma50:
            ma_reasoning = f"Price holds above structural 50 SMA (₹{sma50:,.2f}) institutional support, despite a short-term dip below 20 EMA."
        else:
            ma_reasoning = f"Price is testing critical structural zones near the 50 SMA (₹{sma50:,.2f}) and 200 SMA (₹{sma200:,.2f}) floors."

        # RSI Momentum reasoning
        rsi_reasoning = ""
        if rsi_val >= 70:
            rsi_reasoning = f"RSI is extremely strong at {rsi_val:.1f} ({rsi_status}), showing high bullish momentum."
        elif rsi_val >= 50:
            rsi_reasoning = f"RSI at {rsi_val:.1f} ({rsi_status}) indicates active buying interest and healthy momentum."
        elif rsi_val >= 35:
            rsi_reasoning = f"RSI at {rsi_val:.1f} ({rsi_status}) indicates a healthy cooling consolidation zone."
        else:
            rsi_reasoning = f"RSI at {rsi_val:.1f} ({rsi_status}) indicates deeply oversold levels, highly prime for a technical bounce."

        # CCI momentum velocity reasoning
        cci_reasoning = ""
        if cci_val >= 100:
            cci_reasoning = f"CCI is at {cci_val:.1f} ({cci_status}), confirming an active breakout phase."
        elif cci_val >= 0:
            cci_reasoning = f"CCI at {cci_val:.1f} ({cci_status}) indicates supportive short-term momentum."
        elif cci_val >= -100:
            cci_reasoning = f"CCI is at {cci_val:.1f} ({cci_status}), reflecting temporary sideways consolidation."
        else:
            cci_reasoning = f"CCI at {cci_val:.1f} ({cci_status}) shows extreme selling exhaustion, signaling an upward pivot."

        # Extract execution parameters (Stop Loss and Target) from base_rec_text
        sl_target_part = ""
        if "Set stop loss" in base_rec_text:
            sl_target_part = base_rec_text[base_rec_text.index("Set stop loss"):]
        elif "Place stop loss" in base_rec_text:
            sl_target_part = base_rec_text[base_rec_text.index("Place stop loss"):]
        elif "stop loss" in base_rec_text.lower():
            try:
                idx = base_rec_text.lower().index("stop loss")
                sl_target_part = base_rec_text[idx-4:]
            except ValueError:
                sl_target_part = base_rec_text
        else:
            sl_target_part = base_rec_text

        final_text = f"{rsi_reasoning} {cci_reasoning} {ma_reasoning} {sl_target_part}"

        analysis_payload = {
            "is_rich": True,
            "text": final_text,
            "rsi": round(rsi_val, 1),
            "rsi_status": rsi_status,
            "rsi_interp": rsi_interp,
            "cci": round(cci_val, 1),
            "cci_status": cci_status,
            "cci_interp": cci_interp,
            "ema20": round(ema20, 2),
            "sma50": round(sma50, 2),
            "sma200": round(sma200, 2),
            "triggers": triggers
        }
        return json.dumps(analysis_payload)
    except Exception as e:
        print(f"Error computing rich technical analysis for {symbol}: {e}")
        return base_rec_text


