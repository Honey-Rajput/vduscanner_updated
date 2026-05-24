# watchlist.py
import os
import pandas as pd
from datetime import datetime
from config import IST_TIMEZONE, get_company_name

# Define local CSV persistence path
CSV_PATH = os.path.join(os.path.dirname(__file__), "watchlist.csv")
COLUMNS = ['symbol', 'company_name', 'added_date', 'entry_price', 'signal_strength_at_add', 'tag', 'notes']

def load_watchlist() -> pd.DataFrame:
    """
    Loads the persistent watchlist from watchlist.csv.
    Creates an empty DataFrame and CSV file if they do not exist.
    """
    if not os.path.exists(CSV_PATH):
        df = pd.DataFrame(columns=COLUMNS)
        try:
            df.to_csv(CSV_PATH, index=False)
        except Exception as e:
            print(f"Error creating default watchlist.csv: {e}")
        return df
        
    try:
        df = pd.read_csv(CSV_PATH)
        # Verify and insert any missing columns gracefully
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        # Return structured in the correct column order
        return df[COLUMNS].copy()
    except Exception as e:
        print(f"Error loading watchlist.csv: {e}")
        # Return empty structured dataframe as a fallback
        return pd.DataFrame(columns=COLUMNS)

def save_watchlist(df: pd.DataFrame) -> bool:
    """
    Saves the provided DataFrame to watchlist.csv.
    """
    try:
        # Ensure we only write standard columns
        df_to_save = df[COLUMNS].copy()
        df_to_save.to_csv(CSV_PATH, index=False)
        return True
    except Exception as e:
        print(f"Error saving watchlist.csv: {e}")
        return False

def add_stock(symbol: str, entry_price: float, signal_strength: float, company_name: str = None) -> bool:
    """
    Appends a new stock to the watchlist. Returns True if successful, 
    or False if it already exists.
    """
    df = load_watchlist()
    clean_symbol = symbol.strip().upper()
    
    if clean_symbol in df['symbol'].values:
        # Stock is already in the watchlist, skip appending duplicate
        return False
        
    if not company_name:
        company_name = get_company_name(clean_symbol)
        
    added_date = datetime.now(IST_TIMEZONE).strftime("%Y-%m-%d")
    
    new_row = {
        'symbol': clean_symbol,
        'company_name': company_name,
        'added_date': added_date,
        'entry_price': round(float(entry_price), 2),
        'signal_strength_at_add': round(float(signal_strength), 1),
        'tag': "Watching 👀",
        'notes': ""
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    return save_watchlist(df)

def remove_stock(symbol: str) -> bool:
    """
    Deletes a stock from the watchlist.
    """
    df = load_watchlist()
    clean_symbol = symbol.strip().upper()
    
    if clean_symbol not in df['symbol'].values:
        return False
        
    df = df[df['symbol'] != clean_symbol]
    return save_watchlist(df)

def update_tag(symbol: str, tag: str) -> bool:
    """
    Updates the status tag for a stock in the watchlist.
    """
    df = load_watchlist()
    clean_symbol = symbol.strip().upper()
    
    if clean_symbol not in df['symbol'].values:
        return False
        
    df.loc[df['symbol'] == clean_symbol, 'tag'] = tag
    return save_watchlist(df)

def update_notes(symbol: str, notes: str) -> bool:
    """
    Updates the notes field for a stock in the watchlist.
    """
    df = load_watchlist()
    clean_symbol = symbol.strip().upper()
    
    if clean_symbol not in df['symbol'].values:
        return False
        
    df.loc[df['symbol'] == clean_symbol, 'notes'] = notes
    return save_watchlist(df)

def export_csv() -> bytes:
    """
    Returns the watchlist data formatted as CSV bytes for Streamlit downloader.
    """
    df = load_watchlist()
    return df.to_csv(index=False).encode('utf-8')
