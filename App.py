import streamlit as st
import datetime
import pandas as pd
import yfinance as yf
import ta
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="Advanced Backtest Engine", page_icon="📈", layout="wide")

st.title("🎛️ Tactical Backtest & Allocation Matrix Studio")
st.markdown("Replicate the flagship systematic rules, backtest cumulative returns against QQQ, and analyze dynamic portfolio allocation shifts.")

# ----------------------------------------------------
# SYSTEM INTERACTION CONTROL PANEL
# ----------------------------------------------------
st.sidebar.header("⚙️ Core Controls")

# Custom ticker workspace for the Internal Breadth Engine
default_tickers = "MSFT, AAPL, NVDA, AMZN, META, GOOGL, GOOG, AVGO, TSLA, COST"
user_ticker_string = st.sidebar.text_area("Breadth Constituents Basket:", default_tickers)
custom_tickers = [t.strip().upper() for t in user_ticker_string.split(",") if t.strip()]

st.sidebar.subheader("💰 Strategy Allocation Weights")
max_tqqq = st.sidebar.slider("Max TQQQ Exposure (%)", 50, 100, 75)
base_income = st.sidebar.slider("Income ETF Target (%)", 0, 50, 20)

@st.cache_data(ttl=3600)
def run_advanced_simulation(tickers, max_leverage, income_weight):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=730)
    buffer_start = start_date - datetime.timedelta(days=50)
    
    # Download Core Baseline Benchmarks
    assets_to_download = ["QQQ", "TQQQ", "TBIL"]
    market_data = yf.download(assets_to_download, start=buffer_start, end=end_date, progress=False)
    
    if "Close" not in market_data or market_data["Close"]["QQQ"].empty:
        return pd.DataFrame()
        
    qqq_close = market_data["Close"]["QQQ"]
    tqqq_close = market_data["Close"]["TQQQ"]
    
    # Fallback simulation vector if TBIL historical price data is flat/unstable
    tbil_close = market_data["Close"]["TBIL"] if "TBIL" in market_data["Close"] else pd.Series(50.0, index=qqq_close.index)
    
    # Calculate System Indicators on QQQ
    ema9 = ta.trend.ema_indicator(qqq_close, window=9)
    ema21 = ta.trend.ema_indicator(qqq_close, window=21)
    rsi = ta.momentum.rsi(qqq_close, window=14)
    
    # Process Breadth Data Universe
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
    
    # Sync structural index frame
    valid_dates = qqq_close.loc[start_date:].index
    records = []
    
    for idx, date in enumerate(valid_dates):
        # 1. Generate Algorithmic Sentiment Score
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
        
        # 2. Map Capital Allocations Dynamically
        if score > 0:
            scale = score / 9.0
            tqqq_pct = max(50.0, round(max_leverage * scale, 1))
            inc_pct = income_weight
            tbil_pct = max(0.0, round(100.0 - (tqqq_pct + inc_pct), 1))
            if tqqq_pct + inc_pct > 100.0:
                inc_pct = round(100.0 - tqqq_pct, 1)
                tbil_pct = 0.0
            profile = "🟢 Bullish Uptrend"
        else:
            tqqq_pct, inc_pct, tbil_pct = 0.0, 0.0, 100.0
            profile = "🔴 Downtrend Defense"
            
        records.append({
            "Date": date,
            "QQQ_Close": float(qqq_close.loc[date]),
            "TQQQ_Close": float(tqqq_close.loc[date]),
            "TBIL_Close": float(tbil_close.loc[date]),
            "Score": int(score),
            "Profile": profile,
            "TQQQ %": tqqq_pct,
            "Income %": inc_pct,
            "TBIL %": tbil_pct
        })
        
    df_sim = pd.DataFrame(records)
    
    # 3. Compile Cumulative Performance Metrics
    df_sim["QQQ_Return"] = df_sim["QQQ_Close"].pct_change().fillna(0)
    df_sim["TQQQ_Return"] = df_sim["TQQQ_Close"].pct_change().fillna(0)
    df_sim["TBIL_Return"] = df_sim["TBIL_Close"].pct_change().fillna(0)
    
    # Approximate Income ETF performance (QQQ Return + static writing yield cushion)
    df_sim["Income_Return"] = (df_sim["QQQ_Return"] * 0.6) + (0.08 / 252) 
    
    strat_returns = []
    for i in range(len(df_sim)):
        if i == 0:
            strat_returns.append(0.0)
            continue
            
        # Strategy shifts allocations based on the PRIOR day's closed signal score
        t_pct = df_sim.loc[i-1, "TQQQ %"] / 100.0
        inc_pct = df_sim.loc[i-1, "Income %"] / 100.0
        tb_pct = df_sim.loc[i-1, "TBIL %"] / 100.0
        
        daily_perf = (t_pct * df_sim.loc[i, "TQQQ_Return"] + 
                      inc_pct * df_sim.loc[i, "Income_Return"] + 
                      tb_pct * df_sim.loc[i, "TBIL_Return"])
        strat_returns.append(daily_perf)
        
    df_sim["Strat_Return"] = strat_returns
    
    # Compound total tracking curves from a baseline index starting value of $10,000
    df_sim["Buy_Hold_QQQ"] = (1 + df_sim["QQQ_Return"]).cumprod() * 10000
    df_sim["Tactical_Strategy"] = (1 + df_sim["Strat_Return"]).cumprod() * 10000
    
    return df_sim

# Execute Core Backtest Machine
with st.spinner("Processing tactical returns and allocation modeling matrix..."):
    sim_df = run_advanced_simulation(custom_tickers, max_tqqq, base_income)

if not sim_df.empty:
    # ----------------------------------------------------
    # RUN CHART VISUALIZATION
    # ----------------------------------------------------
    st.subheader("📈 Cumulative Growth Comparison (2-Year Backtest)")
    
    final_qqq = sim_df["Buy_Hold_QQQ"].iloc[-1]
    final_strat = sim_df["Tactical_Strategy"].iloc[-1]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Final Strategy Value (Base $10k)", f"${final_strat:,.2f}")
    c2.metric("Final QQQ Buy & Hold Value", f"${final_qqq:,.2f}")
    c3.metric("Strategy Alpha Outperformance", f"{((final_strat - final_qqq)/final_qqq)*100:+.2f}%")
    
    fig_growth = go.Figure()
    fig_growth.add_trace(go.Scatter(x=sim_df["Date"], y=sim_df["Tactical_Strategy"], mode='lines', name='Tactical Engine Strategy', line=dict(color='#2ca02c', width=2.5)))
    fig_growth.add_trace(go.Scatter(x=sim_df["Date"], y=sim_df["Buy_Hold_QQQ"], mode='lines', name='Pure QQQ Buy & Hold', line=dict(color='#7f7f7f', width=1.5)))
    fig_growth.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.02, x=0), margin=dict(l=40, r=40, t=20, b=40), height=400)
    st.plotly_chart(fig_growth, use_container_width=True)
    
    st.markdown("---")
    
    # ----------------------------------------------------
    # HISTORICAL ALLOCATION MAPPER LOOKUP MODULE
    # ----------------------------------------------------
    st.subheader("🔍 Historical Score Allocation Matrix Lookup")
    
    # Date Picker for historical lookup
    lookup_date = st.date_input("Pick a Date to Analyze Strategy Stance:", value=sim_df["Date"].max().date(),
                                min_value=sim_df["Date"].min().date(), max_value=sim_df["Date"].max().date())
    
    selected_row = sim_df[sim_df["Date"].dt.date == lookup_date]
    
    if not selected_row.empty:
        r = selected_row.iloc[0]
        
        # AUTOMATED INFO TEXT LOGIC BASED ON SENTIMENT SCORE
        st.markdown(f"#### 🛡️ System Diagnostic Stance For {lookup_date.strftime('%B %d, %Y')}")
        
        if r["Score"] > 0:
            st.success(f"**Score: +{r['Score']} ({r['Profile']})** | Market internals are structurally sound. The macro indicators confirm strong buyer velocity, and the majority of underlying stocks are holding their medium-term trends.")
            st.markdown(f"""
            **Automated Asset Sizing Response:**
            *   **TQQQ Core:** Scaled upward to **{r['TQQQ %']}%** of the total portfolio value to capture high-beta leveraged index growth.
            *   **Income Stability:** Leveraged with a fixed target of **{r['Income %']}%** to compound yield distributions.
            *   **Uninvested Capital:** Remaining cash buffer of **{r['TBIL %']}%** parked safely in short-term T-Bills.
            """)
        elif r["Score"] == 0:
            st.info(f"**Score: 0 (Neutral Border State)** | The market is experiencing extreme structural fragility. Underlying breadth is breaking down, signaling high risk for a complete trend reversal.")
            st.markdown("**Automated Asset Sizing Response:** The system triggers an allocation shift to **100% Cash Defense (TBIL)**. Zero leverage allowed.")
        else:
            st.error(f"**Score: {r['Score']} ({r['Profile']})** | Market breakdown confirmed. QQQ momentum handles are trading in bearish configurations, and defensive overlays have taken complete dominance.")
            st.markdown(f"""
            **Automated Asset Sizing Response:**
            *   **Risk Liquidation:** TQQQ and Income structures are locked at **0.0%** exposure.
            *   **Capital Preservation:** Portfolio exposure completely defaults to **100.0% Cash Reserve (TBIL)** to eliminate compounding decay drawdown velocity.
            """)
            
