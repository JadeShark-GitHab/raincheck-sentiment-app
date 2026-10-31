import streamlit as st
import datetime
import pandas as pd
import yfinance as yf
import ta
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="Raincheck Wave Studio", page_icon="🛡️", layout="wide")

st.title("🛡️ Raincheck Systematic Wave Studio & Benchmarker")
st.markdown("""
This institutional framework evaluates **TQQQ, SQQQ, and TBIL** tracking execution. 
It features automated **Trend Reversal Markers**, **Active Cycle P&L monitoring**, and a **Custom Date Range Benchmarker**.
""")

# ----------------------------------------------------
# SYSTEM INTERACTION SIDEBAR PANEL
# ----------------------------------------------------
st.sidebar.header("📡 Internal Breadth Signals")
default_tickers = "MSFT, AAPL, NVDA, AMZN, META, GOOGL, GOOG, AVGO, TSLA, COST"
user_ticker_string = st.sidebar.text_area("Signal Target Tickers:", default_tickers)
custom_tickers = [t.strip().upper() for t in user_ticker_string.split(",") if t.strip()]

st.sidebar.subheader("💰 Strategy Allocation Profile")
max_tqqq_pct = st.sidebar.slider("Maximum TQQQ Target (%)", 50, 100, 75)
income_target_pct = st.sidebar.slider("Income Allocation Target (%)", 0, 50, 20)

@st.cache_data(ttl=3600)
def process_comprehensive_wave_studio(tickers, max_tqqq, base_income):
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
    
    # Calculate Signals
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
    prev_state_positive = None
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
        
        # --- TREND REVERSAL MARKERS LOOP ---
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

        # Sizing Assignment Rules
        tqqq_w, sqqq_w, inc_w, tbil_w = 0.0, 0.0, 0.0, 0.0
        if score < 0:
            regime_label = "Short Regime"
            if score <= -6:
                sqqq_w, tbil_w = 50.0, 50.0
                status = "Short Overlay (Active SQQQ)"
            else:
                tbil_w = 100.0
                status = "Defensive Cash Buffer"
        elif score == 0:
            tbil_w = 100.0
            status = "Neutral Circuit Breaker"
            regime_label = "Neutral State"
        else:
            regime_label = "Long Regime"
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
            "Regime_Type": regime_label,
            "Regime_Start": current_regime_start,
            "Trend_Duration": trend_days,
            "Reversal_Event": "⚠️ REVERSAL TRIGGERED" if is_reversal else "Continuation",
            "TQQQ %": max(0.0, tqqq_w),
            "SQQQ %": max(0.0, sqqq_w),
            "Income %": max(0.0, inc_w),
            "TBIL %": max(0.0, tbil_w)
        })
        
    df_sim = pd.DataFrame(records)
    
    # Calculate performance return arrays
    df_sim["QQQ_Ret"] = df_sim["QQQ_Close"].pct_change().fillna(0)
    df_sim["TQQQ_Ret"] = df_sim["TQQQ_Close"].pct_change().fillna(0)
    df_sim["SQQQ_Ret"] = df_sim["SQQQ_Close"].pct_change().fillna(0)
    df_sim["TBIL_Ret"] = df_sim["TBIL_Close"].pct_change().fillna(0)
    df_sim["Inc_Ret"] = (df_sim["QQQ_Ret"] * 0.6) + (0.08 / 252)
    
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
    return df_sim

with st.spinner("Processing advanced wave models..."):
    df_master = process_comprehensive_wave_studio(custom_tickers, max_tqqq_pct, income_target_pct)

if not df_master.empty:
    df_master["Date_Only"] = df_master["Date"].dt.date
    min_sim_date = df_master["Date_Only"].min()
    max_sim_date = df_master["Date_Only"].max()
    
    # ----------------------------------------------------
    # ENHANCEMENT 3: CUSTOM DATE RANGE BENCHMARKER
    # ----------------------------------------------------
    st.subheader("📆 Custom Date Range Performance Benchmarker")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        custom_start = st.date_input("Custom Range Start Date:", value=min_sim_date, min_value=min_sim_date, max_value=max_sim_date)
    with col_d2:
        custom_end = st.date_input("Custom Range End Date:", value=max_sim_date, min_value=min_sim_date, max_value=max_sim_date)
        
    if custom_start < custom_end:
        range_df = df_master[(df_master["Date_Only"] >= custom_start) & (df_master["Date_Only"] <= custom_end)].copy()
        if not range_df.empty:
            range_df["Strat_Win_Cum"] = (1 + range_df["Strat_Ret"]).cumprod()
            range_df["QQQ_Win_Cum"] = (1 + range_df["QQQ_Ret"]).cumprod()
            
            strat_pnl = (range_df["Strat_Win_Cum"].iloc[-1] - 1) * 100
            qqq_pnl = (range_df["QQQ_Win_Cum"].iloc[-1] - 1) * 100
            
            p1, p2, p3 = st.columns(3)
            p1.metric("Custom Strategy P&L", f"{strat_pnl:+.2f}%")
            p2.metric("Custom QQQ Buy & Hold P&L", f"{qqq_pnl:+.2f}%")
            p3.metric("Custom Range Alpha Differential", f"{(strat_pnl - qqq_pnl):+.2f}%")
            
            # Interactive Line Graph for Custom Range
            fig_range = go.Figure()
            fig_range.add_trace(go.Scatter(x=range_df["Date_Only"], y=range_df["Strat_Win_Cum"]*100-100, name="Tactical Strategy", line=dict(color="#16A34A")))
            fig_range.add_trace(go.Scatter(x=range_df["Date_Only"], y=range_df["QQQ_Win_Cum"]*100-100, name="QQQ Buy & Hold", line=dict(color="#7f7f7f")))
            fig_range.update_layout(title="Custom Range Growth Trajectory (%)", hovermode="x unified", height=250, margin=dict(l=40, r=40, t=30, b=30))
            st.plotly_chart(fig_range, use_container_width=True)
            
    st.markdown("---")
    
    # ----------------------------------------------------
    # ENHANCEMENT 1 & 2: REVERSAL MARKERS & ACTIVE CYCLE P&L DISPLAY
    # ----------------------------------------------------
    st.subheader("🔍 Rolling Trend Cycle Matrix Lookup")
