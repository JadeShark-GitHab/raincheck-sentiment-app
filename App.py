import streamlit as st
import datetime
import pandas as pd
import yfinance as yf
import ta
import plotly.graph_objects as go

st.set_page_config(page_title="Raincheck Tactical Terminal", page_icon="🛡️", layout="wide")

st.title("🦅 Raincheck System Cycle & Timeline Terminal")
st.markdown("Automated market signal diagnostics, execution asset allocation mapping, and comprehensive trend cycle log analytics.")

# ----------------------------------------------------
# SYSTEM INTERACTION CONTROL PANEL
# ----------------------------------------------------
st.sidebar.header("📡 Breadth Signals Setup")
default_tickers = "MSFT, AAPL, NVDA, AMZN, META, GOOGL, GOOG, AVGO, TSLA, COST"
user_ticker_string = st.sidebar.text_area("Signal Target Universe:", default_tickers)
custom_tickers = [t.strip().upper() for t in user_ticker_string.split(",") if t.strip()]

st.sidebar.subheader("💰 Strategy Sizing Constraints")
max_tqqq_pct = st.sidebar.slider("Maximum TQQQ Target (%)", 50, 100, 75)
income_target_pct = st.sidebar.slider("Income Target Allocation (%)", 0, 50, 20)

@st.cache_data(ttl=3600)
def process_comprehensive_timeline_engine(tickers, max_tqqq, base_income):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=730)
    buffer_start = start_date - datetime.timedelta(days=60)
    
    # Download Core Assets
    assets = ["QQQ", "TQQQ", "SQQQ", "TBIL"]
    market_data = yf.download(assets, start=buffer_start, end=end_date, progress=False)
    
    if "Close" not in market_data or market_data["Close"]["QQQ"].empty:
        return pd.DataFrame(), []
        
    qqq_close = market_data["Close"]["QQQ"]
    tqqq_close = market_data["Close"]["TQQQ"]
    sqqq_close = market_data["Close"]["SQQQ"]
    tbil_close = market_data["Close"]["TBIL"] if "TBIL" in market_data["Close"] else pd.Series(50.0, index=qqq_close.index)
    
    # Calculate Signal Metrics
    ema9 = ta.trend.ema_indicator(qqq_close, window=9)
    ema21 = ta.trend.ema_indicator(qqq_close, window=21)
    rsi = ta.momentum.rsi(qqq_close, window=14)
    
    # Process Breadth Matrices
    constituent_data = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=buffer_start, end=end_date, progress=False)
            if not df.empty and "Close" in df:
                sma20 = ta.trend.sma_indicator(df['Close'], window=20)
                constituent_data[ticker] = (df['Close'] > sma20).astype(int).replace(0, -1)
        except:
            continue
            
    df_breadth = pd.DataFrame(constituent_data).ffill()
    valid_dates = qqq_close.loc[start_date:].index
    
    records = []
    trend_days = 0
    prev_state_positive = None
    current_regime_start = valid_dates[0]
    
    for date in valid_dates:
        row = qqq_close.loc[date]
        
        macro = 0
        if pd.notna(ema9.loc[date]) and pd.notna(ema21.loc[date]):
            macro += 1.5 if qqq_close.loc[date] > ema9.loc[date] > ema21.loc[date] else -1.5
        macro += 1.5 if (pd.notna(rsi.loc[date]) and rsi.loc[date] > 50) else -1.5
        
        if date in df_breadth.index:
            daily_sig = df_breadth.loc[date]
            active = daily_sig.notna().sum()
            bull_pct = (daily_sig == 1).sum() / active if active > 0 else 0.5
            breadth_score = (bull_pct - 0.5) * 12
        else:
            bull_pct = 0.5
            breadth_score = 0
            
        score = max(-9, min(9, round(macro + breadth_score)))
        is_positive = score > 0
        
        is_reversal = False
        if prev_state_positive is None:
            prev_state_positive = is_positive
            trend_days = 1
        elif is_positive == prev_state_positive:
            trend_days += 1
        else:
            is_reversal = True
            trend_days = 1
            prev_state_positive = is_positive
            current_regime_start = date
            
        idx_pos = qqq_close.index.get_loc(date)
        price_pullback = False
        if idx_pos > 0 and is_positive:
            price_pullback = qqq_close.iloc[idx_pos] < qqq_close.iloc[idx_pos - 1]

        tqqq_w, sqqq_w, inc_w, tbil_w = 0.0, 0.0, 0.0, 0.0
        if score < 0:
            regime_label = "🔴 Downtrend Bearish"
            if score <= -6:
                sqqq_w, tbil_w = 50.0, 50.0
                status = "Short Overlay (SQQQ Active)"
            else:
                tbil_w = 100.0
                status = "100% Cash Yield Buffer"
        elif score == 0:
            tbil_w = 100.0
            status = "Neutral Circuit Breaker"
            regime_label = "⚪ Neutral Stance"
        else:
            regime_label = "🟢 Uptrend Bullish"
            if trend_days <= 1:
                tqqq_w, inc_w, tbil_w = 67.0, base_income, round(100.0 - (67.0 + base_income), 1)
                status = "Initial Trend Alignment"
            elif price_pullback or score >= 7:
                tqqq_w, inc_w, tbil_w = max_tqqq, base_income, round(100.0 - (max_tqqq + base_income), 1)
                status = "Aggressive Pullback/Strength Sizing"
            elif 1 <= score <= 4:
                tqqq_w, inc_w, tbil_w = 50.0, 30.0, 20.0
                status = "Weak Signal / Sizing Down Leverage"
            else:
                tqqq_w, inc_w, tbil_w = 70.0, base_income, round(100.0 - (70.0 + base_income), 1)
                status = "Standard Trend Continuation"

        records.append({
            "Date": date,
            "QQQ_Close": float(row),
            "TQQQ_Close": float(tqqq_close.loc[date]),
            "SQQQ_Close": float(sqqq_close.loc[date]),
            "TBIL_Close": float(tbil_close.loc[date]),
            "Score": int(score),
            "Status": status,
            "Regime_Type": regime_label,
            "Regime_Start": current_regime_start,
            "TQQQ_Pct": max(0.0, tqqq_w),
            "SQQQ_Pct": max(0.0, sqqq_w),
            "Income_Pct": max(0.0, inc_w),
            "TBIL_Pct": max(0.0, tbil_w)
        })
        
    df_sim = pd.DataFrame(records)
    
    # Performance matrix arrays
    df_sim["QQQ_Ret"] = df_sim["QQQ_Close"].pct_change().fillna(0)
    df_sim["TQQQ_Ret"] = df_sim["TQQQ_Close"].pct_change().fillna(0)
    df_sim["SQQQ_Ret"] = df_sim["SQQQ_Close"].pct_change().fillna(0)
    df_sim["TBIL_Ret"] = df_sim["TBIL_Close"].pct_change().fillna(0)
    df_sim["Inc_Ret"] = (df_sim["QQQ_Ret"] * 0.6) + (0.08 / 252)
    
    strat_returns = [0.0]
    for i in range(1, len(df_sim)):
        t_w = df_sim.loc[i-1, "TQQQ_Pct"] / 100.0
        s_w = df_sim.loc[i-1, "SQQQ_Pct"] / 100.0
        in_w = df_sim.loc[i-1, "Income_Pct"] / 100.0
        tb_w = df_sim.loc[i-1, "TBIL_Pct"] / 100.0
        
        daily_perf = (t_w * df_sim.loc[i, "TQQQ_Ret"] + 
                      s_w * df_sim.loc[i, "SQQQ_Ret"] + 
                      in_w * df_sim.loc[i, "Inc_Ret"] + 
                      tb_w * df_sim.loc[i, "TBIL_Ret"])
        strat_returns.append(daily_perf)
    df_sim["Strat_Ret"] = strat_returns
    
    # --- BLOCK: COMPILE STRUCTURAL HISTORICAL TREND CYCLES LOG ---
    timeline_events = []
    current_regime = df_sim.iloc[0]["Regime_Type"]
    start_idx = 0
    
    for i in range(1, len(df_sim)):
        # Detect state switch or final row edge boundary
        if df_sim.iloc[i]["Regime_Type"] != current_regime or i == len(df_sim) - 1:
            end_idx = i - 1 if df_sim.iloc[i]["Regime_Type"] != current_regime else i
            
            slice_df = df_sim.iloc[start_idx:end_idx+1]
            cycle_strat_ret = ((1 + slice_df["Strat_Ret"]).cumprod().iloc[-1] - 1) * 100
            cycle_qqq_ret = ((1 + slice_df["QQQ_Ret"]).cumprod().iloc[-1] - 1) * 100
            
            timeline_events.append({
                "Trend Classification": current_regime,
                "Start Date": df_sim.iloc[start_idx]["Date"].strftime('%Y-%m-%d'),
                "Finished Date": df_sim.iloc[end_idx]["Date"].strftime('%Y-%m-%d'),
                "Trading Days Duration": len(slice_df),
                "Strategy Return": f"{cycle_strat_ret:+.2f}%",
                "QQQ Buy & Hold Return": f"{cycle_qqq_ret:+.2f}%"
            })
            
            current_regime = df_sim.iloc[i]["Regime_Type"]
            start_idx = i
            
    return df_sim, timeline_events

with st.spinner("Processing structural execution logs and timeline maps..."):
    df_raw, timeline_log = process_comprehensive_timeline_engine(custom_tickers, max_tqqq_pct, income_target_pct)

if not df_raw.empty:
    df_raw["Date_Only"] = df_raw["Date"].dt.date
    
    # ----------------------------------------------------
    # SECTION 1: LIVE TRACKER COMMAND POST (CURRENT TREND)
    # ----------------------------------------------------
    st.subheader("📡 Live Command Post: Active System Stance")
    current_state = df_raw.iloc[-1]
    
    # Find active cycle historical data array
    active_wave_df = df_raw[df_raw["Regime_Start"] == current_state["Regime_Start"]]
    current_wave_strat_pnl = ((1 + active_wave_df["Strat_Ret"]).cumprod().iloc[-1] - 1) * 100
    
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.metric("Current Active Trend", str(current_state["Regime_Type"]))
    with sc2:
        st.metric("Current Cycle Start Date", current_state["Regime_Start"].strftime('%B %d, %Y'))
    with sc3:
        st.metric("Current Trend Rolling P&L", f"{current_wave_strat_pnl:+.2f}%")
        
    st.markdown("#### Current Target Portfolio Allocation Allocation Change:")
    st.info(f"Active Allocation Profile Status: **{current_state['Status']}** (System Base Calculation Score: **{current_state['Score']}**)")
    
    ac1, ac2, ac3, ac4 = st.columns(4)
    ac1.metric("TQQQ Target (3x Long)", f"{current_state['TQQQ_Pct']}%")
    ac2.metric("SQQQ Target (3x Short)", f"{current_state['SQQQ_Pct']}%")
    ac3.metric("Income ETF Target", f"{current_state['Income_Pct']}%")
    ac4.metric("TBIL Cash Reserve", f"{current_state['TBIL_Pct']}%")
    
