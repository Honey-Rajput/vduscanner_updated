import sys
import os

# Mock streamlit
class st:
    @staticmethod
    def empty():
        class StatusBox:
            def text(self, msg):
                print(msg)
            def empty(self):
                pass
        return StatusBox()
        
    @staticmethod
    def progress(val):
        class ProgBar:
            def progress(self, v):
                print(f"Progress: {v}")
            def empty(self):
                pass
        return ProgBar()
        
    class sidebar:
        @staticmethod
        def error(msg):
            print("ERROR:", msg)

    session_state = {}

import pandas as pd
from datetime import datetime
import yfinance as yf
from config import IST_TIMEZONE, LOOKBACK_DAYS

raw_symbols = ["RELIANCE", "TCS", "HDFCBANK", "INFY"]

all_tickers_ns = []
for s in raw_symbols:
    formatted = s.strip().upper()
    if not formatted.endswith(".NS"):
        formatted = f"{formatted}.NS"
    all_tickers_ns.append(formatted)
    
today_date_str = datetime.now(IST_TIMEZONE).strftime('%Y-%m-%d')
universe_key = "WATCHLIST"
cache_key_p1 = f"p1_quotes_{universe_key}_{today_date_str}"

if cache_key_p1 in st.session_state:
    open_price_map, close_price_map, volume_map, high_price_map, low_price_map = st.session_state[cache_key_p1]
    print("Phase 1/3: Loaded real-time quotes from session cache!")
else:
    open_price_map = {}
    close_price_map = {}
    volume_map = {}
    high_price_map = {}
    low_price_map = {}
    
    print("Phase 1/3: Downloading real-time quotes for selected universe...")
    import time
    chunk_size = 300
    ticker_chunks = [all_tickers_ns[i:i + chunk_size] for i in range(0, len(all_tickers_ns), chunk_size)]
    
    for idx, chunk in enumerate(ticker_chunks):
        retries = 0
        max_retries = 3
        backoff = 2.0
        while retries <= max_retries:
            try:
                quotes_df = yf.download(tickers=chunk, period="1d", progress=False, threads=False)
                if not quotes_df.empty:
                    if isinstance(quotes_df.columns, pd.MultiIndex):
                        price_types = quotes_df.columns.get_level_values(0).unique().tolist()
                        tickers_in_idx = quotes_df.columns.get_level_values(1).unique().tolist()
                        def _get_field_series(field):
                            if field in price_types:
                                s = quotes_df[field].iloc[-1]
                                return s
                            return pd.Series(dtype=float)
                        close_series = _get_field_series('Close')
                        open_series = _get_field_series('Open')
                        volume_series = _get_field_series('Volume')
                        high_series = _get_field_series('High')
                        low_series = _get_field_series('Low')
                    else:
                        ticker_key = chunk[0]
                        close_series = pd.Series({ticker_key: quotes_df['Close'].iloc[-1]})
                        open_series = pd.Series({ticker_key: quotes_df['Open'].iloc[-1]}) if 'Open' in quotes_df else close_series
                        volume_series = pd.Series({ticker_key: quotes_df['Volume'].iloc[-1]}) if 'Volume' in quotes_df else pd.Series({ticker_key: 0})
                        high_series = pd.Series({ticker_key: quotes_df['High'].iloc[-1]}) if 'High' in quotes_df else close_series
                        low_series = pd.Series({ticker_key: quotes_df['Low'].iloc[-1]}) if 'Low' in quotes_df else close_series

                    for k, v in close_series.items():
                        clean_k = str(k).replace(".NS", "").upper()
                        if not pd.isna(v) and float(v) > 0:
                            close_price_map[clean_k] = float(v)
                            if k in open_series.index and not pd.isna(open_series[k]):
                                open_price_map[clean_k] = float(open_series[k])
                            if k in volume_series.index and not pd.isna(volume_series[k]):
                                volume_map[clean_k] = int(volume_series[k])
                            if k in high_series.index and not pd.isna(high_series[k]):
                                high_price_map[clean_k] = float(high_series[k])
                            if k in low_series.index and not pd.isna(low_series[k]):
                                low_price_map[clean_k] = float(low_series[k])
                    break
                else:
                    raise ValueError("Empty DataFrame returned")
            except Exception as chunk_ex:
                retries += 1
                if retries > max_retries:
                    print(f"Error downloading quote chunk: {chunk_ex}")
                    break
                time.sleep(backoff)
                backoff *= 2.0
                
        time.sleep(1.0)
    
    st.session_state[cache_key_p1] = (open_price_map, close_price_map, volume_map, high_price_map, low_price_map)

scan_symbols = [s for s in raw_symbols if close_price_map.get(s.strip().upper(), 0.0) > 200.0]
print(f"scan_symbols: {scan_symbols}")

n_stocks = len(scan_symbols)
print(f"n_stocks: {n_stocks}")

scan_timeframe = "Daily (1d)"

cache_key_p2 = f"p2_bulk_{universe_key}_{scan_timeframe}_{today_date_str}"
bulk_data = {}
if n_stocks > 0:
    if cache_key_p2 in st.session_state:
        bulk_data = st.session_state[cache_key_p2]
    else:
        if "Weekly" in scan_timeframe:
            yf_interval = "1wk"
            yf_period = "4y"
        elif "Monthly" in scan_timeframe:
            yf_interval = "1mo"
            yf_period = "17y"
        else:
            yf_interval = "1d"
            yf_period = f"{LOOKBACK_DAYS}d"

        chunk_size = 100
        sym_chunks = [scan_symbols[i:i + chunk_size] for i in range(0, len(scan_symbols), chunk_size)]
        
        def download_chunk(chunk_idx, chunk):
            chunk_data = {}
            chunk_ns = [f"{s.strip().upper()}.NS" for s in chunk]
            try:
                df_bulk = yf.download(tickers=chunk_ns, period=yf_period, interval=yf_interval, progress=False, threads=False)
                for sym in chunk:
                    sym_ns = f"{sym.strip().upper()}.NS"
                    try:
                        if isinstance(df_bulk.columns, pd.MultiIndex):
                            all_tickers_bulk = df_bulk.columns.get_level_values(1).unique().tolist()
                            matched = next((t for t in all_tickers_bulk if t.upper() == sym_ns.upper()), None)
                            if matched is None:
                                continue
                            ticker_df = df_bulk.xs(matched, axis=1, level=1).copy()
                        else:
                            if len(chunk_ns) == 1:
                                ticker_df = df_bulk.copy()
                            else:
                                continue

                        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
                        if all(col in ticker_df.columns for col in required_cols):
                            ticker_df = ticker_df[required_cols].dropna(subset=['Close'])
                            ticker_df = ticker_df[ticker_df['Volume'] > 0]
                            if not ticker_df.empty:
                                ticker_df = ticker_df.reset_index()
                                ticker_df.rename(columns={ticker_df.columns[0]: 'Date'}, inplace=True)
                                ticker_df['Date'] = pd.to_datetime(ticker_df['Date']).dt.tz_localize(None)
                                chunk_data[sym.strip().upper()] = ticker_df
                    except Exception as sym_ex:
                        print(f"Error extracting {sym_ns} from bulk download: {sym_ex}")
            except Exception as chunk_ex:
                print(f"Error downloading parallel chunk {chunk_idx+1}: {chunk_ex}")
            return chunk_data

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for chunk_idx, chunk in enumerate(sym_chunks):
                futures.append(executor.submit(download_chunk, chunk_idx, chunk))
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                bulk_data.update(future.result())
        
        st.session_state[cache_key_p2] = bulk_data

print("Bulk data keys:", len(bulk_data.keys()))
