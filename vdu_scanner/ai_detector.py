# ai_detector.py
import json
import requests
import os
import pandas as pd
from dotenv import load_dotenv

# Resolve and load environment variables from parent directory's .env file
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(parent_dir, ".env")
load_dotenv(env_path)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

EURI_API_KEY = os.getenv("EURI_API_KEY")
EURI_BASE_URL = os.getenv("EURI_BASE_URL")

def _parse_ai_json(content: str) -> dict:
    """
    Cleans up any potential markdown formatting wrapping the JSON string and parses it.
    """
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    return json.loads(content)

def run_algorithmic_pattern_scan(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 30:
        return {"pattern": "None", "confidence": "None", "details": "Insufficient data for mathematical scanning."}
        
    try:
        # Smoothed Close using a short rolling window to avoid noise
        prices = df['Close'].rolling(window=3, min_periods=1).mean()
        highs = df['High']
        lows = df['Low']
        dates = df['Date']
        
        # Extrema detection window=3
        peaks = []
        troughs = []
        window = 3
        
        for i in range(window, len(prices) - window):
            val = prices.iloc[i]
            subset = prices.iloc[i - window : i + window + 1]
            if val == subset.max():
                peaks.append((i, float(highs.iloc[i]), dates.iloc[i]))
            elif val == subset.min():
                troughs.append((i, float(lows.iloc[i]), dates.iloc[i]))
                
        # 1. Double Bottom Check (most recent troughs) - BULLISH
        if len(troughs) >= 2:
            t1 = troughs[-2]
            t2 = troughs[-1]
            diff = abs(t1[1] - t2[1]) / min(t1[1], t2[1])
            peaks_between = [p for p in peaks if t1[0] < p[0] < t2[0]]
            if diff <= 0.025 and len(peaks_between) > 0:
                neckline = max([p[1] for p in peaks_between])
                current_price = float(df['Close'].iloc[-1])
                if current_price >= neckline * 0.95:
                    return {
                        "pattern": "Double Bottom",
                        "confidence": "High" if current_price >= neckline else "Medium",
                        "details": f"Bullish Extrema proof: Trough 1 at ₹{t1[1]:.2f}, Trough 2 at ₹{t2[1]:.2f} (diff {diff*100:.1f}%), neckline resistance at ₹{neckline:.2f}."
                    }
                    
        # 2. Inverse Head & Shoulders Check - BULLISH
        if len(troughs) >= 3:
            ls = troughs[-3]
            hd = troughs[-2]
            rs = troughs[-1]
            if hd[1] < ls[1] and hd[1] < rs[1]:
                shoulder_diff = abs(ls[1] - rs[1]) / min(ls[1], rs[1])
                if shoulder_diff <= 0.035:
                    peaks_between = [p for p in peaks if ls[0] < p[0] < rs[0]]
                    neckline = max([p[1] for p in peaks_between]) if len(peaks_between) > 0 else ls[1] * 1.1
                    current_price = float(df['Close'].iloc[-1])
                    return {
                        "pattern": "Inverse Head & Shoulders",
                        "confidence": "High" if current_price >= neckline else "Medium",
                        "details": f"Bullish Shoulder proof: Left Shoulder ₹{ls[1]:.2f}, Head ₹{hd[1]:.2f}, Right Shoulder ₹{rs[1]:.2f} (symmetry {shoulder_diff*100:.1f}%)."
                    }
                    
        # 3. Bull Flag Check - BULLISH
        if len(prices) >= 20:
            for length in range(3, 11):
                start_price = float(df['Close'].iloc[-15-length])
                pole_peak_val = float(df['High'].iloc[-15])
                pole_rise = (pole_peak_val - start_price) / start_price
                if pole_rise >= 0.08:
                    consolidation_subset = df.iloc[-15:]
                    c_max = float(consolidation_subset['High'].max())
                    c_min = float(consolidation_subset['Low'].min())
                    halfway_pole = start_price + (pole_peak_val - start_price) * 0.5
                    if c_min >= halfway_pole and c_max <= pole_peak_val * 1.02:
                        current_price = float(df['Close'].iloc[-1])
                        return {
                            "pattern": "Bull Flag",
                            "confidence": "High" if current_price >= c_max * 0.98 else "Medium",
                            "details": f"Bullish Momentum proof: flagpole rise of {pole_rise*100:.1f}%, tight flag consolidation (₹{c_min:.2f} - ₹{c_max:.2f}) holding above midpoint (₹{halfway_pole:.2f})."
                        }
                        
        # 4. Ascending Triangle Check - BULLISH
        if len(peaks) >= 2 and len(troughs) >= 2:
            last_peaks = peaks[-2:]
            last_troughs = troughs[-2:]
            flat_resistance = abs(last_peaks[0][1] - last_peaks[1][1]) / min(last_peaks[0][1], last_peaks[1][1]) <= 0.015
            ascending_troughs = (last_troughs[1][1] - last_troughs[0][1]) / last_troughs[0][1] >= 0.015
            if flat_resistance and ascending_troughs:
                return {
                    "pattern": "Ascending Triangle",
                    "confidence": "Medium-High",
                    "details": f"Bullish Resistance proof: Flat resistance at ₹{last_peaks[1][1]:.2f} and rising support troughs (₹{last_troughs[0][1]:.2f} -> ₹{last_troughs[1][1]:.2f})."
                }

        # 5. Cup & Handle Check - BULLISH
        if len(peaks) >= 2:
            p1 = peaks[-2] # Left rim
            p2 = peaks[-1] # Right rim
            rim_diff = abs(p1[1] - p2[1]) / min(p1[1], p2[1])
            if rim_diff <= 0.03: # Rims are equal within 3%
                troughs_inside = [t for t in troughs if p1[0] < t[0] < p2[0]]
                if len(troughs_inside) > 0:
                    cup_bottom = min([t[1] for t in troughs_inside])
                    cup_depth = p1[1] - cup_bottom
                    if cup_depth / p1[1] >= 0.08:
                        handle_subset = df.iloc[-7:]
                        h_min = float(handle_subset['Low'].min())
                        max_handle_pullback = p2[1] - cup_depth * 0.35
                        if h_min >= max_handle_pullback:
                            current_price = float(df['Close'].iloc[-1])
                            return {
                                "pattern": "Cup & Handle",
                                "confidence": "High" if current_price >= p2[1] * 0.98 else "Medium",
                                "details": f"Bullish Continuation proof: Left rim ₹{p1[1]:.2f}, Right rim ₹{p2[1]:.2f}, Cup bottom ₹{cup_bottom:.2f} (depth {(cup_depth/p1[1])*100:.1f}%), handle pullback holding safely above ₹{max_handle_pullback:.2f}."
                            }

        # 6. Falling Wedge Check - BULLISH
        if len(peaks) >= 3 and len(troughs) >= 3:
            p_series = peaks[-3:]
            t_series = troughs[-3:]
            descending_peaks = p_series[0][1] > p_series[1][1] > p_series[2][1]
            descending_troughs = t_series[0][1] > t_series[1][1] > t_series[2][1]
            if descending_peaks and descending_troughs:
                peak_slope = p_series[2][1] - p_series[0][1]
                trough_slope = t_series[2][1] - t_series[0][1]
                if peak_slope < trough_slope:
                    current_price = float(df['Close'].iloc[-1])
                    return {
                        "pattern": "Falling Wedge",
                        "confidence": "Medium-High",
                        "details": f"Bullish Reversal proof: Lower highs (₹{p_series[0][1]:.2f} -> ₹{p_series[2][1]:.2f}) and lower lows (₹{t_series[0][1]:.2f} -> ₹{t_series[2][1]:.2f}) converging downwards."
                    }
                
    except Exception as e:
        print(f"Mathematical scan error: {e}")
        
    return {"pattern": "None", "confidence": "None", "details": "No dominant bullish chart pattern detected by mathematical scanners."}

def detect_chart_pattern(symbol: str, df: pd.DataFrame) -> dict:
    """
    Slices the last 30 trading days of OHLCV data for a stock, formats it, 
    and sends it to the primary Euri AI (gpt-4.1-mini) model.
    Falls back gracefully to the Groq cascade list of models if Euri API fails.
    """
    if df is None or len(df) < 30:
        return {
            "pattern_name": "None",
            "confidence": "None",
            "direction": "None",
            "analysis_text": "Insufficient historical data available. Needs at least 30 trading days of history."
        }
        
    # Run the mathematical rule-based pattern scan first (Chartink-grade scanner)
    algo_result = run_algorithmic_pattern_scan(df)
    algo_pattern = algo_result["pattern"]
    algo_details = algo_result["details"]
        
    # Calculate indicators using full history before slicing
    close_series = df['Close']
    high_series = df['High']
    low_series = df['Low']
    
    rsi_val = 50.0
    cci_val = 0.0
    ema20_val = float(close_series.iloc[-1])
    sma50_val = float(close_series.iloc[-1])
    sma200_val = float(close_series.iloc[-1])
    cmp_val = float(close_series.iloc[-1])
    
    try:
        # RSI (14)
        delta = close_series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        ema_gain = gain.ewm(com=13, adjust=False).mean()
        ema_loss = loss.ewm(com=13, adjust=False).mean()
        rs = ema_gain / (ema_loss + 1e-9)
        rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])
    except Exception as e:
        print(f"RSI calculation error in ai_detector: {e}")
        
    try:
        # CCI (14)
        tp = (high_series + low_series + close_series) / 3
        sma_tp = tp.rolling(window=14).mean()
        mad_manual = tp.rolling(window=14).apply(lambda x: abs(x - x.mean()).mean(), raw=True)
        cci_val = float(((tp - sma_tp) / (0.015 * mad_manual + 1e-9)).iloc[-1])
    except Exception as e:
        print(f"CCI calculation error in ai_detector: {e}")
        
    try:
        # MA values
        ema20_val = float(close_series.ewm(span=20, adjust=False).mean().iloc[-1])
        sma50_val = float(close_series.rolling(window=50).mean().iloc[-1]) if len(df) >= 50 else float(close_series.iloc[-1])
        sma200_val = float(close_series.rolling(window=200).mean().iloc[-1]) if len(df) >= 200 else float(close_series.iloc[-1])
    except Exception as e:
        print(f"MA calculation error in ai_detector: {e}")

    # Take only the last 30 trading days of data for the prompt
    df_subset = df.iloc[-30:].copy()
    data_lines = []
    
    # Format standard compact data representation
    for _, row in df_subset.iterrows():
        date_str = row['Date'].strftime("%Y-%m-%d")
        data_lines.append(
            f"{date_str} | O: {row['Open']:.2f} | H: {row['High']:.2f} | L: {row['Low']:.2f} | C: {row['Close']:.2f} | V: {int(row['Volume'])}"
        )
    data_str = "\n".join(data_lines)
    
    system_prompt = (
        "You are an expert technical analyst specializing in classical chart pattern recognition. "
        "Analyze the provided 30-day daily OHLCV sequence, technical indicators, and rule-based mathematical scanner matches to identify classical price patterns and evaluate buy/exit triggers. "
        "During your analysis, please explicitly provide the reasoning of CCI, RSI, EMA, and SMA, explaining how they support or conflict with the identified pattern and which are the best technical conditions to buy the stock. "
        "If a pattern has been mathematically detected by the rule-based scanner, validate its neckline and breakout structure in your remarks. "
        "If no recognizable pattern is present, return pattern as 'None'. "
        "Do not hallucinate patterns — only report what is clearly supported by the price structure. "
        "Respond STRICTLY with a single valid JSON object in this exact schema, with no other text:\n"
        "{\n"
        '  "pattern_name": "<pattern name or None>",\n'
        '  "confidence": "<High | Medium | Low | None>",\n'
        '  "direction": "<Bullish | Bearish | Neutral | None>",\n'
        '  "analysis_text": "<detailed technical explanation of 3-4 sentences detailing chart pattern, volume action, and the reasoning for RSI, CCI, EMA, and SMA buy/exit zones>"\n'
        "}"
    )
    
    user_prompt = f"""
    Analyze the following 30 trading days of daily OHLCV data for {symbol} and identify any classical chart pattern.
    
    Rule-Based Mathematical Scanner proof computed for {symbol} on the last day:
    - Mathematically Scan Result: {algo_pattern}
    - Mathematical Proof & Extrema: {algo_details}

    Current Indicators computed for {symbol} on the last day:
    - Current Price (CMP): ₹{cmp_val:.2f}
    - RSI (14): {rsi_val:.1f}
    - CCI (14): {cci_val:.1f}
    - 20 EMA: ₹{ema20_val:.2f}
    - 50 SMA: ₹{sma50_val:.2f}
    - 200 SMA: ₹{sma200_val:.2f}
    
    Daily OHLCV Data (CSV format — Date, Open, High, Low, Close, Volume):
    {data_str}

    Instructions:
    - Detect one dominant pattern only. If the mathematical scan found a pattern, validate and prioritize it. If no clear pattern exists, set pattern_name to "None".
    - Do not hallucinate patterns. Only report what is clearly supported by price structure.
    - In your analysis, explicitly incorporate and reason about the RSI, CCI, EMA, and SMA indicators to justify the buy/exit setup.
    - Explain why these specific values represent the best technical parameters to buy or avoid the stock.
    - Return ONLY a raw JSON object — no markdown, no code fences, no explanation outside the JSON.

    Return exactly this JSON structure:
    {{
    "pattern_name": "e.g. Double Bottom | Ascending Triangle | Bullish Flag | None",
    "confidence": "High | Medium | Low | None",
    "direction": "Bullish | Bearish | Neutral | None",
    "analysis_text": "Detailed analysis. Explain the chart pattern, volume action, and why RSI, CCI, EMA, and SMA align to offer the best high-probability buying opportunity."
    }}
    """
    
    last_error = None
    
    # --- Try Euri API first (gpt-4.1-mini) ---
    if EURI_API_KEY:
        # Resolve EURI Base URL
        if EURI_BASE_URL:
            if EURI_BASE_URL.endswith("/chat/completions"):
                euri_url = EURI_BASE_URL
            else:
                euri_url = EURI_BASE_URL.rstrip("/") + "/chat/completions"
        else:
            euri_url = "https://api.euron.one/api/v1/euri/chat/completions"
            
        euri_headers = {
            "Authorization": f"Bearer {EURI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        euri_payload = {
            "model": "gpt-4.1-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 1000
        }
        
        try:
            print(f"Sending pattern analysis request for {symbol} to Euri API (gpt-4.1-mini)...")
            response = requests.post(euri_url, headers=euri_headers, json=euri_payload, timeout=25)
            if response.status_code == 200:
                resp_json = response.json()
                content = resp_json['choices'][0]['message']['content'].strip()
                parsed = _parse_ai_json(content)
                
                return {
                    "pattern_name": parsed.get("pattern_name", "None"),
                    "confidence": parsed.get("confidence", "None"),
                    "direction": parsed.get("direction", "None"),
                    "analysis_text": parsed.get("analysis_text", "Technical analysis was generated successfully."),
                    "model_used": "gpt-4.1-mini (Euri)",
                    "rsi": round(rsi_val, 1),
                    "cci": round(cci_val, 1),
                    "ema20": round(ema20_val, 2),
                    "sma50": round(sma50_val, 2),
                    "sma200": round(sma200_val, 2),
                    "cmp": round(cmp_val, 2),
                    "algo_pattern": algo_pattern,
                    "algo_details": algo_details
                }
            else:
                last_error = f"Euri API returned status code {response.status_code}: {response.text}"
                print(last_error)
        except Exception as e:
            last_error = f"Euri API request failed: {str(e)}"
            print(last_error)
    else:
        last_error = "EURI_API_KEY is not defined in the environment."
        print(last_error)
        
    # --- Fallback to Groq Cascade list ---
    if GROQ_API_KEY:
        groq_headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Cascade list of robust models on Groq
        models = [
            "openai/gpt-oss-20b",
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768"
        ]
        
        for model_name in models:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2
            }
            
            try:
                print(f"Falling back: sending request for {symbol} to Groq API using model {model_name}...")
                response = requests.post(GROQ_URL, headers=groq_headers, json=payload, timeout=20)
                if response.status_code == 200:
                    resp_json = response.json()
                    content = resp_json['choices'][0]['message']['content'].strip()
                    parsed = _parse_ai_json(content)
                    
                    return {
                        "pattern_name": parsed.get("pattern_name", "None"),
                        "confidence": parsed.get("confidence", "None"),
                        "direction": parsed.get("direction", "None"),
                        "analysis_text": parsed.get("analysis_text", "Technical analysis was generated successfully."),
                        "model_used": f"{model_name} (Groq)",
                        "rsi": round(rsi_val, 1),
                        "cci": round(cci_val, 1),
                        "ema20": round(ema20_val, 2),
                        "sma50": round(sma50_val, 2),
                        "sma200": round(sma200_val, 2),
                        "cmp": round(cmp_val, 2),
                        "algo_pattern": algo_pattern,
                        "algo_details": algo_details
                    }
                else:
                    last_error = f"Model {model_name} returned status code {response.status_code}: {response.text}"
                    print(last_error)
            except Exception as e:
                last_error = f"Model {model_name} failed: {str(e)}"
                print(last_error)
    else:
        if not last_error:
            last_error = "GROQ_API_KEY is missing from the environment credentials."
            
    # Fallback error structure if all options fail
    return {
        "pattern_name": "Error",
        "confidence": "None",
        "direction": "None",
        "analysis_text": f"AI Pattern Recognition engine experienced connectivity problems. Details: {last_error}",
        "model_used": "None",
        "algo_pattern": algo_pattern,
        "algo_details": algo_details
    }
