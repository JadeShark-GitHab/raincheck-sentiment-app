import streamlit as st
import datetime
import pandas as pd
import yfinance as yf
import ta
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="Raincheck Alpha Pro Studio", page_icon="🛡️", layout="wide")

st.title("🛡️ Raincheck Algorithmic Execution & Wave Benchmarker")
st.markdown("""
This institutional-grade studio mirrors **Raincheck Fund's** execution assets (**TQQQ, SQQQ, TBIL**) while evaluating cycle entry points, rolling trend wave performance, and custom date calculations.
""")

# ----------------------------------------------------
# SYSTEM INTERACTION CORE CONTROLS
# ----------------------------------------------------
st.sidebar.header("📡 Internal Breadth Signals")
default_tickers = "MSFT, AAPL, NVDA, AMZN, META, GOOGL, GOOG, AVGO, TSLA, COST"
user_ticker_string = st.sidebar.text_area("Signal Target Tickers:", default_tickers)
custom_tickers = [t.strip().upper() for t in user_ticker_string.split(",") if t.strip()]

st.sidebar.subheader("💰 Strategy Allocation Profile")
max_tqqq_pct = st.sidebar.slider("Maximum TQQQ Target (%)", 50, 100, 75)
income_target_pct = st.sidebar.slider("Income Allocation Target (%)", 0, 50, 20)

@st.cache_data(ttl=3600)
def process_advanced_wave_engine(tickers, max_tqqq, base_income):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=730)
    buffer_start = start_date - datetime.timedelta(days=60)
    
    # Download Core Assets
    assets = ["QQQ", "TQQQ", "SQQQ", "TBIL"]
    market_data = yf.download(assets, start=buffer_start, end=end_date, progress=False)
    
    if "Close" not in market_data or market_data["Close"]["QQQ"].empty:
        return pd.DataFrame()
        
    qqq_close = market_data["Close"]["QQQ"]
    tqqq_close = market_data["Close"]["TQQQ"]
    sqqq_close = market_data["Close"]["SQQQ"]
    tbil_close = market_data["Close"]["TBIL"] if "TBIL" in market_data["Close"] else pd.Series(50.0, index=qqq_close.index)
    
    # Calculate System Signal Indicators
    ema9 = ta.trend.ema_indicator(qqq_close, window=9)
    ema21 = ta.trend.ema_indicator(qqq_close, window=21)
    rsi = ta.momentum.rsi(qqq_close, window=14)
    
    # Process Breadth Matrix
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
    prev_state_positive = True
    current_regime_start = valid_dates[0]
    
    for date in valid_dates:
        row = qqq_close.loc[date]
        
        # Calculate Score
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
        
        # Track Structural Trend Start Changes
        if is_positive == prev_state_positive:
            trend_days += 1
        else:
            trend_days = 1
            prev_state_positive = is_positive
            current_regime_start = date
            
        idx_pos = qqq_close.index.get_loc(date)
        price_pullback = False
        if idx_pos > 0 and is_positive:
            price_pullback = qqq_close.iloc[idx_pos] < qqq_close.iloc[idx_pos - 1]

        # Allocation Engine Assignment Rules
        tqqq_w, sqqq_w, inc_w, tbil_w = 0.0, 0.0, 0.0, 0.0
        if score < 0:
            if score <= -6:
                sqqq_w, tbil_w = 50.0, 50.0
                status = "Short Overlay (Active SQQQ)"
                regime_type = "Down-Trend Wave"
            else:
                tbil_w = 100.0
                status = "Defensive Cash Buffer"
                regime_type = "Down-Trend Wave"
        elif score == 0:
            tbil_w = 100.0
            status = "Neutral Circuit Breaker"
            regime_type = "Neutral Intermission"
        else:
            regime_type = "Up-Trend Wave"
            if trend_days <= 1:
                tqqq_w, inc_w, tbil_w = 67.0, base_income, round(100.0 - (67.0 + base_income), 1)
                status = "Initial Uptrend Allocation"
            elif price_pullback or score >= 7:
                tqqq_w, inc_w, tbil_w = max_tqqq, base_income, round(100.0 - (max_tqqq + base_income), 1)
                status = "Aggressive Long Momentum"
            elif 1 <= score <= 4:
                tqqq_w, inc_w, tbil_w = 50.0, 30.0, 20.0
                status = "Reduced Leverage / Profit Taking"
            else:
                tqqq_w, inc_w, tbil_w = 70.0, base_income, round(100.0 - (70.0 + base_income), 1)
                status = "Standard Trend Allocation"

        records.append({
            "Date": date,
            "QQQ_Close": float(row),
            "TQQQ_Close": float(tqqq_close.loc[date]),
            "SQQQ_Close": float(sqqq_close.loc[date]),
            "TBIL_Close": float(tbil_close.loc[date]),
            "Score": int(score),
            "Status": status,
            "Regime_Type": regime_type,
            "Regime_Start": current_regime_start,
            "TQQQ %": max(0.0, tqqq_w),
            "SQQQ %": max(0.0, sqqq_w),
            "Income %": max(0.0, inc_w),
            "TBIL %": max(0.0, tbil_w)
        })
        
    df_sim = pd.DataFrame(records)
    
    # Calculate returns for compounding calculation loops
    df_sim["QQQ_Ret"] = df_sim["QQQ_Close"].pct_change().fillna(0)
    df_sim["TQQQ_Ret"] = df_sim["TQQQ_Close"].pct_change().fillna(0)
    df_sim["SQQQ_Ret"] = df_sim["SQQQ_Close"].pct_change().fillna(0)
    df_sim["TBIL_Ret"] = df_sim["TBIL_Close"].pct_change().fillna(0)
    df_sim["Inc_Ret"] = (df_sim["QQQ_Ret"] * 0.6) + (0.08 / 252) # Proxy Covered-Call Math
    
    strat_returns = [0.0]
    for i in range(1, len(df_sim)):
        t_w = df_sim.loc[i-1, "TQQQ %"] / 100.0
        s_w = df_sim.loc[i-1, "SQQQ %"] / 100.0
        in_w = df_sim.loc[i-1, "Income %"] / 100.0
        tb_w = df_sim.loc[i-1, "TBIL %"] / 100.0
        
        daily_perf = (t_w * df_sim.loc[i, "TQQQ_Ret"] + 
                      s_w * df_sim.loc[i, "SQQQ_Ret"] + 
                      in_w * df_sim.loc[i, "Inc_Ret"] + 
                      tb_w * df_sim.loc[i, "TBIL_Ret"])
        strat_returns.append(daily_perf)
        
    df_sim["Strat_Ret"] = strat_returns
    df_sim["Strat_Cum"] = (1 + df_sim["Strat_Ret"]).cumprod()
    df_sim["QQQ_Cum"] = (1 + df_sim["QQQ_Ret"]).cumprod()
    
    return df_sim

with st.spinner("Processing execution layers and structural trend vectors..."):
    df_master = process_advanced_wave_engine(custom_tickers, max_tqqq_pct, income_target_pct)

if not df_master.empty:
    df_master["Date_Only"] = df_master["Date"].dt.date
    
    # ----------------------------------------------------
    # SECTION 1: CUSTOM DATE PERFORMANCE RANGE CALCULATOR
    # ----------------------------------------------------
    st.subheader("📆 Custom Date Range P&L Benchmarker")
    col_d1, col_d2 = st.columns(2)
    min_sim_date = df_master["Date_Only"].min()
    max_sim_date = df_master["Date_Only"].max()
    
    with col_d1:
        custom_start = st.date_input("Start Date Evaluation:", value=min_sim_date, min_value=min_sim_date, max_value=max_sim_date)
    with col_d2:
        custom_end = st.date_input("End Date Evaluation:", value=max_sim_date, min_value=min_sim_date, max_value=max_sim_date)
        
    if custom_start < custom_end:
        range_df = df_master[(df_master["Date_Only"] >= custom_start) & (df_master["Date_Only"] <= custom_end)].copy()
        if not range_df.empty:
            # Rebase metrics over user window
            range_df["Strat_Win_Cum"] = (1 + range_df["Strat_Ret"]).cumprod()
            range_df["QQQ_Win_Cum"] = (1 + range_df["QQQ_Ret"]).cumprod()
            
            strat_pnl = (range_df["Strat_Win_Cum"].iloc[-1] - 1) * 100
            qqq_pnl = (range_df["QQQ_Win_Cum"].iloc[-1] - 1) * 100
            
            p1, p2, p3 = st.columns(3)
            p1.metric(f"Tactical Return ({custom_start} to {custom_end})", f"{strat_pnl:+.2f}%")
            p2.metric(f"QQQ Buy & Hold Return", f"{qqq_pnl:+.2f}%")
            p3.metric("Strategy Alpha Boost", f"{(strat_pnl - qqq_pnl):+.2f}%")
    else:
        st.error("Start Date must precede End Date settings.")

    st.markdown("---")
    
    # ----------------------------------------------------
    # SECTION 2: ROLLING TREND METRIC SUMMARY FOR HIGHLIGHTED DAY
    # ----------------------------------------------------
    st.subheader("🔍 Historical Wave Metrics & Allocation Viewer")
    lookup_date = st.date_input("Select Target Query Analysis Date:", value=max_sim_date, min_value=min_sim_date, max_value=max_sim_date)
    
    day_slice = df_master[df_master["Date_Only"] == lookup_date]
    
    if not day_slice.empty:
        r = day_slice.iloc[0]
        
        # Calculate P&L since current trend started
        wave_start_date = r["Regime_Start"]
        wave_df = df_master[(df_master["Date"] >= wave_start_date) & (df_master["Date"] <= r["Date"])]
        
        wave_strat_return = (1 + wave_df["Strat_Ret"]).cumprod().iloc[-1] - 1
