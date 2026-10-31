import streamlit as st
import datetime
import pandas as pd
import yfinance as yf
import ta
import plotly.graph_objects as go

st.set_page_config(page_title="Raincheck Mirror Studio", page_icon="⚙️", layout="wide")

st.title("🎛️ Raincheck Fund Mirror Layout Studio")
st.markdown("""
This interface mirrors the official execution assets (**TQQQ, SQQQ, TBIL**) while preserving 
your custom breadth constituent indicators to drive the core Daily Sentiment Score.
""")

# ----------------------------------------------------
# SIGNAL CONTROLS (THE LOOK-UNDER-THE-HOOD ENGINE)
# ----------------------------------------------------
st.sidebar.header("📡 Internal Breadth Signals")
default_tickers = "MSFT, AAPL, NVDA, AMZN, META, GOOGL, GOOG, AVGO, TSLA, COST"
user_ticker_string = st.sidebar.text_area("Signal Target Tickers:", default_tickers)
custom_tickers = [t.strip().upper() for t in user_ticker_string.split(",") if t.strip()]

st.sidebar.subheader("💰 Asset Threshold Profiles")
max_tqqq_pct = st.sidebar.slider("Maximum TQQQ Target (%)", 50, 100, 75)
income_target_pct = st.sidebar.slider("Income Allocation Target (%)", 0, 50, 20)

@st.cache_data(ttl=3600)
def process_synchronized_mirror_engine(tickers, max_tqqq, base_income):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=730)
    buffer_start = start_date - datetime.timedelta(days=50)
    
    # Download Core Baseline Benchmarks
    qqq = yf.download("QQQ", start=buffer_start, end=end_date, progress=False)
    if qqq.empty:
        return pd.DataFrame()
        
    qqq['EMA9'] = ta.trend.ema_indicator(qqq['Close'], window=9)
    qqq['EMA21'] = ta.trend.ema_indicator(qqq['Close'], window=21)
    qqq['RSI'] = ta.momentum.rsi(qqq['Close'], window=14)
    
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
    valid_dates = qqq.loc[start_date:].index
    
    records = []
    trend_days = 0
    prev_state_positive = True
    
    for date in valid_dates:
        row = qqq.loc[date]
        
        # 1. Generate Algorithmic Sentiment Score
        macro = 0
        if pd.notna(row['EMA9']) and pd.notna(row['EMA21']):
            macro += 1.5 if row['Close'] > row['EMA9'] > row['EMA21'] else -1.5
        macro += 1.5 if (pd.notna(row['RSI']) and row['RSI'] > 50) else -1.5
        
        if date in df_breadth.index:
            daily_sig = df_breadth.loc[date]
            active = daily_sig.notna().sum()
            bull_pct = (daily_sig == 1).sum() / active if active > 0 else 0.5
            breadth_score = (bull_pct - 0.5) * 12
        else:
            bull_pct = 0.5
            breadth_score = 0
            
        score = max(-9, min(9, round(macro + breadth_score)))
        
        # Track Consecutive Trend History
        is_positive = score > 0
        if is_positive == prev_state_positive:
            trend_days += 1
        else:
            trend_days = 1
            prev_state_positive = is_positive
            
        # Detect pricing pullback mechanics
        idx_pos = qqq.index.get_loc(date)
        price_pullback = False
        if idx_pos > 0 and is_positive:
            price_pullback = qqq['Close'].iloc[idx_pos] < qqq['Close'].iloc[idx_pos - 1]

        # 2. Map Execution Weights Matching Raincheck Strategy Rules
        tqqq, sqqq, income, tbil = 0.0, 0.0, 0.0, 0.0
        
        if score < 0:  # BEARISH / SHORT REGIME
            if score <= -6:
                sqqq, tbil = 50.0, 50.0
                status = "🔮 Short Overlay: Deploying Active SQQQ Targets"
            else:
                tbil = 100.0
                status = "🍏 Capital Preservation: 100% Cash Yield Protection"
        elif score == 0:  # NEUTRAL CIRCUIT BREAKER
            tbil = 100.0
            status = "⚪ Neutral Stance: Safe-Haven Extraction"
        else:  # BULLISH / LONG REGIME
            if trend_days <= 1:
                tqqq, income, tbil = 67.0, base_income, round(100.0 - (67.0 + base_income), 1)
                status = "🚨 Uptrend Triggered: Initial Capital Deployment"
            elif price_pullback or score >= 7:
                tqqq, income, tbil = max_tqqq, base_income, round(100.0 - (max_tqqq + base_income), 1)
                status = "🚀 Aggressive Upside: Maximizing Long Momentum"
            elif 1 <= score <= 4:
                tqqq, income, tbil = 50.0, 30.0, 20.0
                status = "💎 Weakening Trend: Taking Profits & Sizing Down Leverage"
            else:
                tqqq, income, tbil = 70.0, base_income, round(100.0 - (70.0 + base_income), 1)
                status = "📈 Standard Allocation: Tracking Trend Continuity"

        records.append({
            "Date": date,
            "QQQ Price": round(float(row['Close']), 2),
            "Score": int(score),
            "Status": status,
            "TQQQ %": max(0.0, tqqq),
            "SQQQ %": max(0.0, sqqq),
            "Income %": max(0.0, income),
            "TBIL %": max(0.0, tbil)
        })
        
    return pd.DataFrame(records)

with st.spinner("Synchronizing asset frameworks and score metrics..."):
    df_mirror = process_synchronized_mirror_engine(custom_tickers, max_tqqq_pct, income_target_pct)

if not df_mirror.empty:
    # ----------------------------------------------------
    # HISTORICAL EVALUATION HOVER LOOKUP
    # ----------------------------------------------------
    st.subheader("🔍 Interactive Target Matrix Analysis")
    lookup_date = st.date_input("Pick Analysis Evaluation Date:", value=df_mirror["Date"].max().date(),
                                min_value=df_mirror["Date"].min().date(), max_value=df_mirror["Date"].max().date())
    
    selected_day = df_mirror[df_mirror["Date"].dt.date == lookup_date]
    
    if not selected_day.empty:
        r = selected_day.iloc
        st.info(f"**Automated State Diagnosis:** {r['Status']} (Day Signal: {r['Score']})")
        
        # Display 4 Metrics Grid
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("TQQQ Weight (3x Long)", f"{r['TQQQ %']}%")
        m2.metric("SQQQ Weight (3x Short)", f"{r['SQQQ %']}%")
        m3.metric("Income ETF Weight", f"{r['Income %']}%")
        m4.metric("TBIL Cash Reserve", f"{r['TBIL %']}%")
        
        # Render Donut Graph with Custom Assigned Palette String Colors
        fig_pie = go.Figure(data=[go.Pie(
            labels=['TQQQ (3x Long)', 'SQQQ (3x Short)', 'Income ETFs', 'TBIL Cash'],
            values=[r['TQQQ %'], r['SQQQ %'], r['Income %'], r['TBIL %']],
            hole=.4,
            marker=dict(colors=['#E11D48', '#9333EA', '#2563EB', '#16A34A']),
            sort=False
        )])
        fig_pie.update_layout(height=280, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")
    st.subheader("🗃️ Mirror Strategy Allocation Ledger")
    
    display_df = df_mirror.copy()
    display_df["Date"] = display_df["Date"].dt.date
    st.dataframe(display_df.sort_values(by="Date", ascending=False), use_container_width=True, hide_index=True)
else:
    st.error("Data pipeline mismatch. Verify internet connections.")
