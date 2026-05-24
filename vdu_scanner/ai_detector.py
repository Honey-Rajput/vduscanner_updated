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

def detect_chart_pattern(symbol: str, df: pd.DataFrame) -> dict:
    """
    Slices the last 30 trading days of OHLCV data for a stock, formats it, 
    and sends it to the Groq Llama-3 AI technical analyst model.
    Falls back gracefully across models to ensure maximum availability.
    """
    if df is None or len(df) < 30:
        return {
            "pattern_name": "None",
            "confidence": "None",
            "direction": "None",
            "analysis_text": "Insufficient historical data available. Needs at least 30 trading days of history."
        }
        
    if not GROQ_API_KEY:
        return {
            "pattern_name": "Error",
            "confidence": "None",
            "direction": "None",
            "analysis_text": "GROQ_API_KEY is missing from the environment credentials. Please check your .env file."
        }
        
    # Take only the last 30 trading days of data
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
        "You are an expert AI technical analyst specializing in classical chart patterns. "
        "Your task is to analyze the provided 30-day stock OHLCV sequence for classic price patterns. "
        "You MUST recognize shapes such as Double Bottom/Top, Head & Shoulders, Cup & Handle, Triangles (Ascending, Descending, Symmetrical), "
        "Flags, Pennants, Wedges, Channels, or Rectangles. "
        "You MUST respond STRICTLY with a single, valid JSON object containing no other text."
    )
    
    user_prompt = f"""
    Analyze the daily price trend of {symbol} for pattern formations in the last 30 trading days.
    
    Daily OHLCV Data:
    {data_str}
    
    Please return a single JSON object in exactly this format:
    {{
      "pattern_name": "Name of pattern, or 'None' if no clear pattern is detected (e.g. 'Double Bottom', 'Ascending Triangle', 'Bullish Flag')",
      "confidence": "High", "Medium", "Low", or "None",
      "direction": "Bullish", "Bearish", "Neutral", or "None",
      "analysis_text": "Provide a brief 2 to 3 sentence analysis explaining key support/resistance levels, breakout criteria, or target zones."
    }}
    """
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Cascade list of robust models on Groq to handle rate limiting or service outages
    models = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
    last_error = None
    
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
            response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=20)
            if response.status_code == 200:
                resp_json = response.json()
                content = resp_json['choices'][0]['message']['content'].strip()
                parsed = json.loads(content)
                
                # Standardize output keys
                return {
                    "pattern_name": parsed.get("pattern_name", "None"),
                    "confidence": parsed.get("confidence", "None"),
                    "direction": parsed.get("direction", "None"),
                    "analysis_text": parsed.get("analysis_text", "Technical analysis was generated successfully.")
                }
            else:
                last_error = f"Model {model_name} returned status code {response.status_code}: {response.text}"
        except Exception as e:
            last_error = f"Model {model_name} failed: {str(e)}"
            
    # Fallback error structure if all models in cascade fail
    return {
        "pattern_name": "Error",
        "confidence": "None",
        "direction": "None",
        "analysis_text": f"AI Pattern Recognition engine experienced connectivity problems. Details: {last_error}"
    }
