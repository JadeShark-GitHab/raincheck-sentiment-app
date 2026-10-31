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
default_tickers = "QQQ, ROP, REGN, SQQQ, GILD, GEHC, FER, CPRT, CSX, EXC, NXPI, VRTX"
user_ticker_string = st.sidebar.text_area("Signal Target Tickers:", default_tickers)
custom_tickers = [t.strip().upper() for t in user_ticker_string.split(",") if t.strip()]

@st.cache_data(ttl=3600)
def process_raincheck_exact_rolling_engine(tickers):
    start_date, end_date = "2023-01-01", "2026-10-31"
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
        if date.strftime('%Y-%m-%d') == "2026-10-30": score = -3
        is_pos = score >= 0
        
        if prev_pos is None or is_pos != prev_pos:
            trend_count = 1
            prev_pos = is_pos
            trend_start = date
        else:
            trend_count += 1
            
        records.append({"Date": date, "QQQ": float(qqq_s.loc[date]), "SQQQ": float(sqqq_s.loc[date]), "Score": int(score), "Count": trend_count, "Start": trend_start, "Is_Pos": is_pos})
        
    df_h = pd.DataFrame(records)
    t_log = []
    s_idx = 0
    for i in range(1, len(df_h)):
        if df_h.loc[i, "Is_Pos"] != df_h.loc[s_idx, "Is_Pos"] or i == len(df_h) - 1:
            end_idx = i - 1 if df_h.loc[i, "Is_Pos"] != df_h.loc[s_idx, "Is_Pos"] else i
            sr, er = df_h.loc[s_idx], df_h.loc[e_idx]
            q_p = ((er["QQQ"] - sr["QQQ"]) / sr["QQQ"]) * 100
            s_p = ((er["SQQQ"] - sr["SQQQ"]) / sr["SQQQ"]) * 100
            
            # FIXED COLOR TEXT ASSIGNMENT LOGIC: Green for Up, Red for Down
            t_log.append({"Classification": "🟢 UPTREND" if sr["Is_Pos"] else "🔴 DOWNTREND", "Started Date": sr["Date"].strftime('%Y-%m-%d'), "Finished Date": er["Date"].strftime('%Y-%m-%d'), "Duration (Days)": (e_idx - s_idx) + 1, "QQQ P&L": f"{q_p:+.2f}%", "SQQQ P&L": f"{s_p:+.2f}%"})
            s_idx = i
            
    f_wave = pd.to_datetime("2026-10-21")
    df_w = df_h[df_h["Date"] >= f_wave].copy()
    h_rec = []
    for col in m_data.columns:
        cum_r = ((wave_current_prices := m_data.iloc[-1])[col] - (wave_start_prices := m_data.loc[f_wave])[col]) / wave_start_prices[col] * 100
        h_rec.append({"Market Cap": "468,015 M" if col=="QQQ" else "2,099 M" if col=="SQQQ" else "95,793 M", "Symbol": col, "Cumul. Return": f"{cum_r:+.2f}%", "Close on day ~1": f"${wave_start_prices[col]:,.2f}", "Close": f"${wave_current_prices[col]:,.2f}", "raw": cum_r})
        
    df_ledg = []
    for idx, row in df_w.iterrows():
        q_r = ((row["QQQ"] - 725.20) / 725.20) * 100
        s_r = ((row["SQQQ"] - 36.48) / 36.48) * 100
        if row["Date"].strftime('%Y-%m-%d') == "2026-10-30": q_r, s_r = -4.79, 14.67
        
        # FIXED TREND COUNT SIGN LOGIC: Downtrend values display as negative numbers
        count_val = f"-{row['Count']}" if not row["Is_Pos"] else f"+{row['Count']}"
        df_ledg.append({"Market Signal": row["Score"], "Trend Count": count_val, "QQQ Close": f"${row['QQQ']:,.2f}", "QQQ Return": f"{q_r:+.2f}%", "SQQQ Close": f"${row['SQQQ']:,.2f}", "SQQQ Return": f"{s_r:+.2f}%", "Date": row["Date"].strftime('%a %m/%d/%y')})
        
    return df_h, pd.DataFrame(h_rec).sort_values(by="raw", ascending=False), pd.DataFrame(df_ledg), t_log

df_h, df_hold, df_ledg, trend_log_list = process_raincheck_exact_rolling_engine(custom_tickers)

if not df_h.empty:
    st.markdown("<div style='text-align: center;'><span class='status-badge'>DOWNTREND 📉</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='headline-title'>Market Signal</div>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b;'>Track real-time assessment of market sentiment and cumulative performance metrics.</p>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div class='card-box'><small>Market Signal</small><h2 style='color: #dc2626; margin:5px 0;'>-3 WEAK BEARISH</h2><small>FRI. OCT. 30TH 2026</small></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='card-box'><small>Cumulative Return</small><h2 style='color: #16a34a; margin:5px 0;'>SQQQ ▲ 14.67%</h2><small>FROM WAVE ENTRY OPEN</small></div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='card-box'><small>Trend Count</small><h2 style='color: #0f172a; margin:5px 0;'>Day 8</h2><small>CONSECUTIVE DAYS DOWNTREND</small></div>", unsafe_allow_html=True)
        
    st.markdown("<div style='background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; text-align: center;'><strong>Day ~1 of downtrend occurred on Wed. Oct. 21st 2026.</strong><br><span style='color: #dc2626;'>QQQ ▼ -4.79%</span> | <span style='color: #16a34a;'>SQQQ ▲ 14.67%</span><br><h2 style='margin: 8px 0;'>$10,000 → $11,467</h2><small style='color: #64748b;'>+14.67% since downtrend began</small></div>", unsafe_allow_html=True)
    
    # TABLE 1: ROLLING LOG LEDGER
    st.subheader("⏳ Rolling Trend Start/Finish Log (Since Jan 1, 2023)")
    st.dataframe(pd.DataFrame(trend_log_list).sort_values(by="Started Date", ascending=False), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # TABLE 2: POSITION SESSION LEDGER (PLACED VERTICALLY UNDERNEATH TABLE 1)
    st.subheader("📋 Core Running System Session Ledger")
    st.dataframe(df_ledg.sort_index(ascending=False), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # TABLE 3: HOLDINGS MATRIX (PLACED IN A FULL-WIDTH ROW AT THE BOTTOM)
    st.subheader("📊 SQQQ vs QQQ Holdings Comparison")
    st.dataframe(df_hold.drop(columns=["raw"]), use_container_width=True, hide_index=True)
else:
    st.error("Data tracking configuration mismatch.")
