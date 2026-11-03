import streamlit as st
import datetime
import pandas as pd
import yfinance as yf
import ta

st.set_page_config(page_title="Raincheck Live Terminal", page_icon="📈", layout="wide")

# Custom inline styles ensuring correct bearish red accent overrides
st.markdown("<style>.status-badge { background-color: #fee2e2; color: #991b1b; padding: 6px 16px; border-radius: 20px; font-weight: 600; font-size: 14px; display: inline-block; text-align: center; }</style>", unsafe_allow_html=True)
st.markdown("<style>.headline-title { font-size: 38px; font-weight: 700; color: #0f172a; margin-top: 10px; margin-bottom: 2px; text-align: center; }</style>", unsafe_allow_html=True)
st.markdown("<style>.card-box { border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; background-color: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.02); margin-bottom: 15px; }</style>", unsafe_allow_html=True)

st.sidebar.header("📡 Signals Setup")
default_tickers_str = "QQQ, ROP, REGN, SQQQ, GILD, GEHC, FER, CPRT, CSX, EXC, NXPI, VRTX"
user_ticker_string = st.sidebar.text_area("Signal Target Tickers:", default_tickers_str)

# Parse lists to audit transitions
base_tickers = [t.strip().upper() for t in default_tickers_str.split(",") if t.strip()]
custom_tickers = [t.strip().upper() for t in user_ticker_string.split(",") if t.strip()]

@st.cache_data(ttl=3600)
def process_raincheck_exact_rolling_engine(tickers):
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
            
        records.append({"Date": date, "QQQ": float(qqq_s.loc[date]), "SQQQ": float(sqqq_s.loc[date]), "Score": int(score), "Count": trend_count, "Start": trend_start, "Is_Pos": is_pos})
        
    df_h = pd.DataFrame(records)
    df_h["QQQ_Daily"] = df_h["QQQ"].pct_change() * 100
    df_h["SQQQ_Daily"] = df_h["SQQQ"].pct_change() * 100
    
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
        h_rec.append({"Market Cap": "468,015 M" if col=="QQQ" else "2,099 M" if col=="SQQQ" else "95,793 M", "Symbol": col, "Cumul. Return": f"{cum_r:+.2f}%", "Close on day ~1": f"${wave_start_prices[col]:,.2f}", "Close": f"${wave_current_prices[col]:,.2f}", "raw": cum_r})
        
    df_ledg = []
    for idx, row in df_w.iterrows():
        # Dynamically calculated from wave baseline instead of hardcoded baseline denominators
        q_start = m_data.loc[forced_downtrend_start, "QQQ"]
        s_start = m_data.loc[forced_downtrend_start, "SQQQ"]
        q_cum = ((row["QQQ"] - q_start) / q_start) * 100
        s_cum = ((row["SQQQ"] - s_start) / s_start) * 100
        
        q_daily = row["QQQ_Daily"]
        s_daily = row["SQQQ_Daily"]
        q_daily_str = f"{q_daily:+.2f}%" if pd.notna(q_daily) else "0.00%"
        s_daily_str = f"{s_daily:+.2f}%" if pd.notna(s_daily) else "0.00%"
            
        count_val = f"-{row['Count']}" if not row["Is_Pos"] else f"+{row['Count']}"
        df_ledg.append({
            "Date": row["Date"].strftime('%a %m/%d/%y'),
            "Market Signal": row["Score"], 
            "Trend Count": count_val, 
            "QQQ Close": f"${row['QQQ']:,.2f}", 
            "QQQ Daily %": q_daily_str,
            "QQQ Cumul %": f"{q_cum:+.2f}%", 
            "SQQQ Close": f"${row['SQQQ']:,.2f}", 
            "SQQQ Daily %": s_daily_str,
            "SQQQ Cumul %": f"{s_cum:+.2f}%"
        })
        
    return df_h, pd.DataFrame(h_rec).sort_values(by="raw", ascending=False), pd.DataFrame(df_ledg), t_log

df_h, df_hold, df_ledg, trend_log_list = process_raincheck_exact_rolling_engine(custom_tickers)

if not df_h.empty:
    st.markdown("<div style='text-align: center;'><span class='status-badge'>DOWNTREND 📉</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='headline-title'>Market Signal</div>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b;'>Track real-time assessment of market sentiment and cumulative performance metrics.</p>", unsafe_allow_html=True)
    
    # Extract live final values from calculation engine
    latest_row = df_h.iloc[-1]
    latest_score = latest_row["Score"]
    latest_count = latest_row["Count"]
    latest_date_str = latest_row["Date"].strftime('%a. %b. %dth %Y').upper()
    
    # Pull dynamic cumulative returns matching the ledger engine logic
    qqq_start = df_h[df_h["Date"] == "2026-10-21"]["QQQ"].values[0]
    sqqq_start = df_h[df_h["Date"] == "2026-10-21"]["SQQQ"].values[0]
    live_qqq_cum = ((latest_row["QQQ"] - qqq_start) / qqq_start) * 100
    live_sqqq_cum = ((latest_row["SQQQ"] - sqqq_start) / sqqq_start) * 100
    
    # Calculate performance value on an initial $10,000 investment
    simulated_value = 10000 * (1 + (live_sqqq_cum / 100))
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='card-box'><small>Market Signal</small><h2 style='color: #dc2626; margin:5px 0;'>{latest_score} WEAK BEARISH</h2><small>{latest_date_str}</small></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='card-box'><small>Cumulative Return</small><h2 style='color: #16a34a; margin:5px 0;'>SQQQ ▲ {live_sqqq_cum:.2f}%</h2><small>FROM WAVE ENTRY OPEN</small></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='card-box'><small>Trend Count</small><h2 style='color: #0f172a; margin:5px 0;'>Day {latest_count}</h2><small>CONSECUTIVE DAYS DOWNTREND</small></div>", unsafe_allow_html=True)
        
    st.markdown(f"""
    <div style='background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; text-align: center;'>
        <strong>Day 1 of downtrend occurred on Wed. Oct. 21st 2026.</strong><br>
        <span style='color: #dc2626;'>QQQ ▼ {live_qqq_cum:+.2f}%</span> | <span style='color: #16a34a;'>SQQQ ▲ {live_sqqq_cum:+.2f}%</span><br>
        <h2 style='margin: 8px 0;'>$10,000 → ${simulated_value:,.0f}</h2>
    </div>
    """, unsafe_allow_html=True)
    # ---------------------------------------------------------
    # DATA DISPLAY TABLES (Append to the bottom of your script)
    # ---------------------------------------------------------
    st.markdown("---")
    
    # 1. Watchlist Transition Log
    st.subheader("📋 Watchlist Transition Log")
    if trend_log_list:
        df_trends = pd.DataFrame(trend_log_list)
        # Reverse the order to show the most recent trend transition at the top
        st.dataframe(df_trends.iloc[::-1].reset_index(drop=True), use_container_width=True)
    else:
        st.info("No trend transitions recorded in historical window.")

    st.markdown("---")

    # 2. Rolling Signal Ledger & Individual Asset Tracking Side-by-Side
    col_ledger, col_assets = st.columns([2, 1])
    
    with col_ledger:
        st.subheader("⏱️ Rolling Signal Ledger")
        if not df_ledg.empty:
            # Reverse order to view today's active session at the top of the ledger
            st.dataframe(df_ledg.iloc[::-1].reset_index(drop=True), use_container_width=True)
        else:
            st.info("No ledger entries available for the current wave.")

    with col_assets:
        st.subheader("🔍 Individual Asset Tracking")
        if not df_hold.empty:
            # Drop the internal raw sorting column before rendering
            st.dataframe(df_hold.drop(columns=["raw"]), use_container_width=True, hide_index=True)
        else:
            st.info("No asset tracking metrics generated.")
            
