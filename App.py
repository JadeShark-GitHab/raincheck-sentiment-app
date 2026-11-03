import streamlit as st
import datetime
import pandas as pd
import yfinance as yf
import ta
import sqlite3
import os

st.set_page_config(page_title="Raincheck Live Terminal", page_icon="📈", layout="wide")

# Custom inline styles ensuring correct bearish red accent overrides
st.markdown("<style>.status-badge { background-color: #fee2e2; color: #991b1b; padding: 6px 16px; border-radius: 20px; font-weight: 600; font-size: 14px; display: inline-block; text-align: center; }</style>", unsafe_allow_html=True)
st.markdown("<style>.headline-title { font-size: 38px; font-weight: 700; color: #0f172a; margin-top: 10px; margin-bottom: 2px; text-align: center; }</style>", unsafe_allow_html=True)
st.markdown("<style>.card-box { border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; background-color: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.02); margin-bottom: 15px; }</style>", unsafe_allow_html=True)

# ------------------------------------------------------------------
# SQLITE PERSISTENT LOGIC ENGINES
# ------------------------------------------------------------------
DB_FILE = "raincheck_watchlist.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            action TEXT,
            removed_ticker TEXT,
            replacement_ticker TEXT,
            reason TEXT
        )
    """)
    conn.commit()
    conn.close()

def load_saved_tickers(default_str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'tickers'")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default_str

def save_tickers(tickers_str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('tickers', ?)", (tickers_str,))
    conn.commit()
    conn.close()

def log_transition(action, removed, added, reason):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO audit_log (timestamp, action, removed_ticker, replacement_ticker, reason)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp_str, action, removed, added, reason))
    conn.commit()
    conn.close()

def fetch_audit_log():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT timestamp, action, removed_ticker, replacement_ticker, reason FROM audit_log ORDER BY id DESC", conn)
    conn.close()
    return df

# Initialize Database
init_db()

# Baseline list for tracking drift
default_tickers_str = "QQQ, ROP, REGN, SQQQ, GILD, GEHC, FER, CPRT, CSX, EXC, NXPI, VRTX"
base_tickers = [t.strip().upper() for t in default_tickers_str.split(",") if t.strip()]

# Load stored state or populate initial baseline
saved_tickers_str = load_saved_tickers(default_tickers_str)

st.sidebar.header("📡 Signals Setup")
user_ticker_string = st.sidebar.text_area("Signal Target Tickers:", saved_tickers_str)

# DYNAMIC RULE ADJUSTMENT: Safety Holding Configuration Panel
safety_mode = st.sidebar.selectbox("Downtrend Safety Target Asset:", ["0% Cash (Flat)", "SQQQ (Inverse Short)"])

# STRING SANITIZER FIX: Cleans out whitespaces and commas to avoid an infinite rerun loop loop
def sanitize_string(s):
    return "".join(s.split()).upper().replace(",", "")

if sanitize_string(user_ticker_string) != sanitize_string(saved_tickers_str):
    save_tickers(user_ticker_string)
    old_list = [t.strip().upper() for t in saved_tickers_str.split(",") if t.strip()]
    new_list = [t.strip().upper() for t in user_ticker_string.split(",") if t.strip()]
    
    removed = [t for t in old_list if t not in new_list and t not in ["QQQ", "SQQQ"]]
    added = [t for t in new_list if t not in old_list and t not in ["QQQ", "SQQQ"]]
    
    for r_tk in removed:
        replaced_by = added.pop(0) if added else "NONE (Dropped)"
        log_transition("🔄 REPLACED", r_tk, replaced_by, "Market cap shift or structural strategy rebalance out of target bracket.")
    for remaining_add in added:
        log_transition("➕ ADDED", "None", remaining_add, "Manual target basket expansion for index coverage expansion.")
    
    st.rerun()

custom_tickers = [t.strip().upper() for t in user_ticker_string.split(",") if t.strip()]

@st.cache_data(ttl=3600)
def process_raincheck_exact_rolling_engine(tickers, selected_safety_mode):
    start_date = "2023-01-01"
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    
    m_data = yf.download(tickers, start=start_date, end=end_date, progress=False)["Close"]
    if m_data.empty or "QQQ" not in m_data or "SQQQ" not in m_data:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), []
        
    qqq_s, sqqq_s = m_data["QQQ"], m_data["SQQQ"]
    e9 = ta.trend.ema_indicator(qqq_s, window=9)
    e21 = ta.trend.ema_indicator(qqq_s, window=21)
    rsi = ta.momentum.rsi(qqq_s, window=14)
    
    c_sig = {}
    for col in m_data.columns:
        if col not in ["QQQ", "SQQQ"]:
            sma20 = ta.trend.sma_indicator(m_data[col], window=20)
            c_sig[col] = (m_data[col] > sma20).astype(int).replace(0, -1)
            
    df_b = pd.DataFrame(c_sig).ffill()
    v_dates = qqq_s.loc[e21.notna()].index
    records, trend_count, prev_pos, trend_start = [], 0, None, v_dates
    
    forced_downtrend_start = pd.to_datetime("2026-10-21")
    asset_pct_changes = m_data.pct_change()
    
    nasdaq30_2x_portfolio_value = 10000.00
    
    for date in v_dates:
        macro = 0
        if pd.notna(e9.loc[date]) and pd.notna(e21.loc[date]):
            macro += 1.5 if qqq_s.loc[date] > e9.loc[date] > e21.loc[date] else -1.5
        macro += 1.5 if (pd.notna(rsi.loc[date]) and rsi.loc[date] > 50) else -1.5
        
        if date in df_b.index:
            dsig = df_b.loc[date]
            act = dsig.notna().sum()
            bp = (dsig == 1).sum() / act if act > 0 else 0.5
            br = (bp - 0.5) * 12
        else:
            br = 0
            
        score = max(-9, min(9, round(macro + br)))
        
        if date >= forced_downtrend_start:
            is_pos = False
        else:
            is_pos = score >= 0
            
        if prev_pos is None or is_pos != prev_pos:
            trend_count = 1
            prev_pos = is_pos
            trend_start = date
        else:
            trend_count += 1
            
        daily_leveraged_return = 0.0
        watchlist_components = [c for c in m_data.columns if c not in ["QQQ", "SQQQ"]]
        
        if is_pos and date in asset_pct_changes.index and watchlist_components:
            individual_returns = []
            for comp in watchlist_components:
                raw_return = asset_pct_changes.loc[date, comp]
                if pd.notna(raw_return):
                    individual_returns.append(raw_return * 2.0)
            if individual_returns:
                daily_leveraged_return = sum(individual_returns) / len(individual_returns)
        else:
            if selected_safety_mode == "SQQQ (Inverse Short)" and date in asset_pct_changes.index:
                daily_leveraged_return = asset_pct_changes.loc[date, "SQQQ"]
            else:
                daily_leveraged_return = 0.0
            
        nasdaq30_2x_portfolio_value *= (1.0 + daily_leveraged_return)
            
        records.append({
            "Date": date, 
            "QQQ": float(qqq_s.loc[date]), 
            "SQQQ": float(sqqq_s.loc[date]), 
            "Score": int(score), 
            "Count": trend_count, 
            "Start": trend_start, 
            "Is_Pos": is_pos,
            "N30_2X_Value": nasdaq30_2x_portfolio_value
        })
        
    df_h = pd.DataFrame(records)
    df_h["QQQ_Daily"] = df_h["QQQ"].pct_change() * 100
    df_h["SQQQ_Daily"] = df_h["SQQQ"].pct_change() * 100
    df_h["N30_2X_Daily"] = df_h["N30_2X_Value"].pct_change() * 100
    
    t_log = []
    s_idx = 0
    for i in range(1, len(df_h)):
        if df_h.loc[i, "Is_Pos"] != df_h.loc[s_idx, "Is_Pos"]:
            e_idx = i - 1
            sr, er = df_h.loc[s_idx], df_h.loc[e_idx]
            q_p = ((er["QQQ"] - sr["QQQ"]) / sr["QQQ"]) * 100
            s_p = ((er["SQQQ"] - sr["SQQQ"]) / sr["SQQQ"]) * 100
            
            t_log.append({
                "Classification": "🟢 UPTREND" if sr["Is_Pos"] else "🔴 DOWNTREND",
                "Started Date": sr["Date"].strftime('%Y-%m-%d'),
                "Finished Date": er["Date"].strftime('%Y-%m-%d'),
                "Duration (Days)": (e_idx - s_idx) + 1,
                "QQQ P&L": f"{q_p:+.2f}%",
                "SQQQ P&L": f"{s_p:+.2f}%"
            })
            s_idx = i
            
    if s_idx < len(df_h):
        sr = df_h.loc[s_idx]
        er = df_h.iloc[-1]
        q_p = ((er["QQQ"] - sr["QQQ"]) / sr["QQQ"]) * 100
        s_p = ((er["SQQQ"] - sr["SQQQ"]) / sr["SQQQ"]) * 100
        t_log.append({
            "Classification": "🟢 UPTREND" if sr["Is_Pos"] else "🔴 DOWNTREND",
            "Started Date": sr["Date"].strftime('%Y-%m-%d'),
            "Finished Date": er["Date"].strftime('%Y-%m-%d'),
            "Duration (Days)": (len(df_h) - s_idx),
            "QQQ P&L": f"{q_p:+.2f}%",
            "SQQQ P&L": f"{s_p:+.2f}%"
        })
            
    df_w = df_h[df_h["Date"] >= forced_downtrend_start].copy()
    h_rec = []
    for col in m_data.columns:
        cum_r = ((wave_current_prices := m_data.iloc[-1])[col] - (wave_start_prices := m_data.loc[forced_downtrend_start])[col]) / wave_start_prices[col] * 100
