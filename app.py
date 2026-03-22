import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import concurrent.futures

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="PRO Swing Trading Terminal", layout="wide")

if 'final_list' not in st.session_state: st.session_state['final_list'] = []
if 'df_main' not in st.session_state: st.session_state['df_main'] = pd.DataFrame()
if 'load_status' not in st.session_state: st.session_state['load_status'] = ""

SECTOR_INDICES = {
    "Financial Services": "^NSEBANK", "Technology": "^CNXIT", "Healthcare": "^CNXPHARMA",
    "Consumer Cyclical": "^CNXAUTO", "Consumer Defensive": "^CNXFMCG", "Basic Materials": "^CNXMETAL",
    "Energy": "^CNXENERGY", "Industrials": "^CNXINFRA", "Real Estate": "^CNXREALTY", "Communication Services": "^CNXMEDIA"
}

# --- 2. CSS STYLING ---
st.markdown("""
    <style>
    [data-testid="stHeader"] {height: 0rem !important;}
    h1 { font-size: 1.8rem !important; margin-top: -30px; 
         background: -webkit-linear-gradient(45deg, #FF9933, #FF4B4B); 
         -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
         font-weight: 800; text-align: center;}
    .stButton>button { height: 45px !important; width: 100% !important; font-weight: bold !important; border-radius: 8px !important; }
    th { background-color: #1E2129 !important; color: #FF9933 !important; font-size: 14px !important;}
    div[data-testid="stMetricValue"] { font-size: 24px !important; color: #FF9933 !important; }
    .main { background-color: #0E1117; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 PRO SWING TRADING TERMINAL")

# --- 3. CORE ANALYTICS ENGINE ---

@st.cache_data(ttl=900) 
def get_market_health():
    try:
        nifty = yf.Ticker("^NSEI").history(period="6mo")
        close = nifty['Close'].iloc[-1]
        ema20 = nifty['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
        delta = nifty['Close'].diff()
        gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        loss = (-1 * delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        rsi = float((100 - (100 / (1 + (gain / loss)))).iloc[-1])
        status = "Bullish 🟢" if close > ema20 and rsi > 55 else ("Bearish 🔴" if close < ema20 and rsi < 45 else "Sideways 🟡")
        nifty_ret = ((close - nifty['Close'].iloc[-50]) / nifty['Close'].iloc[-50]) * 100
        return f"**NIFTY 50:** {close:.0f} | **Trend:** {status} | **RSI:** {rsi:.1f}", nifty_ret
    except: return "NIFTY 50: N/A", 0

@st.cache_data(ttl=900)
def get_all_sector_trends():
    sector_trends = {}
    for sec, ticker in SECTOR_INDICES.items():
        try:
            df_sec = yf.Ticker(ticker).history(period="3mo")
            delta = df_sec['Close'].diff()
            gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
            loss = (-1 * delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
            rsi = float((100 - (100 / (1 + (gain / loss)))).iloc[-1])
            sector_trends[sec] = f"{rsi:.1f} 🚀" if rsi >= 60 else f"{rsi:.1f} ⚠️"
        except: sector_trends[sec] = "N/A"
    return sector_trends

def run_backtest(df):
    try:
        data = df.tail(252).copy()
        data['E20'] = data['Close'].ewm(span=20).mean()
        wins, total = 0, 0
        for i in range(1, len(data)-10):
            if data['Close'].iloc[i] > data['E20'].iloc[i] and data['Close'].iloc[i-1] <= data['E20'].iloc[i-1]:
                total += 1
                if data['High'].iloc[i+1:i+11].max() > data['Close'].iloc[i] * 1.05: wins += 1
        return f"{(wins/total*100):.0f}%" if total > 0 else "0%"
    except: return "0%"

def analyze_stock(raw_name, sector_trends_dict, nifty_50d_ret):
    s_name = str(raw_name).strip().upper()
    ticker = s_name + ".NS" if ".NS" not in s_name else s_name
    try:
        yt = yf.Ticker(ticker)
        df = yt.history(period="2y")
        if len(df) < 50: return None
        
        last_p = float(df['Close'].iloc[-1])
        prev_p = float(df['Close'].iloc[-2])
        
        # --- INTERNAL FILTERS (200 MA & NEW LISTING) ---
        if len(df) >= 200:
            ma200 = df['Close'].rolling(window=200).mean().iloc[-1]
            if last_p < ma200: return None 
        else:
            e20_i, e50_i = float(df['Close'].ewm(span=20).mean().iloc[-1]), float(df['Close'].ewm(span=50).mean().iloc[-1])
            if last_p < e20_i or last_p < e50_i: return None

        ema20 = float(df['Close'].ewm(span=20).mean().iloc[-1])
        high_52w = float(df['High'].tail(252).max())
        dist_52w = ((high_52w - last_p) / high_52w) * 100
        
        rs_rating = (((last_p - df['Close'].iloc[-50]) / df['Close'].iloc[-50]) * 100) - nifty_50d_ret
        rs_str = "👑 Alpha" if rs_rating > 5 else ("🟢 Good" if rs_rating > 0 else "🔴 Weak")
        
        vol_mult = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
        if vol_mult >= 3.0 and last_p > prev_p: vol_status = "🔥 MEGA SPIKE"
        elif last_p > prev_p and vol_mult > 1.2: vol_status = "📈 Breakout"
        elif last_p < prev_p and vol_mult < 0.8: vol_status = "📉 Dry Pullback"
        else: vol_status = "Normal"
        
        tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
        risk_val = 1.5 * float(tr.rolling(14).mean().iloc[-1])
        
        info = yt.info
        sec = info.get('sector', 'Unknown')

        return {
            "Stock": s_name, "Sector": sec[:10], "Sec_Trend": sector_trends_dict.get(sec, "N/A"),
            "RS Alpha": rs_str, "52W High": f"{dist_52w:.1f}%", 
            "EMA Zone": "Perfect ✅" if abs(last_p - ema20)/ema20 < 0.05 else "⚠️ Extended",
            "Vol Action": vol_status, "WinRate": run_backtest(df), "Price": round(last_p, 2),
            "Target (1:2)": round(last_p + (risk_val * 2), 2), "SL": round(last_p - risk_val, 2),
            "Risk_Amt": risk_val
        }
    except: return None

# --- 4. STYLING LOGIC ---
def apply_traffic_styles(val):
    if isinstance(val, str):
        if '%' in val:
            try:
                num = float(val.replace('%', '').strip())
                if num >= 60.0 or num <= 5.0: return 'color: #00FFC8; font-weight: bold;'
                if num >= 40.0 or num <= 15.0: return 'color: #FFA500;'
                return 'color: #FF4B4B;'
            except: pass
        if any(x in val for x in ['👑 Alpha', '🟢 Good', 'Perfect ✅', '📈 Breakout', '🔥 MEGA']):
            return 'color: #00FFC8; font-weight: bold;'
        if any(x in val for x in ['📉 Dry Pullback', 'Normal']): return 'color: #FFFF00;'
        if any(x in val for x in ['⚠️ Extended', '🔴 Weak']): return 'color: #FF4B4B;'
    return ''

# --- 5. UI COMPONENTS ---
m_h, n_ret = get_market_health()
st.markdown(f"<div style='padding:10px; background-color:#1E2129; border-radius:8px; text-align:center; border:1px solid #FF9933; margin-bottom:15px;'>🧭 {m_h}</div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("🛡️ Pro Risk Controller")
    cap = st.number_input("Total Capital (₹)", value=100000)
    risk_p = st.slider("Risk per Trade %", 0.5, 5.0, 1.0, 0.1)
    max_risk = (cap * risk_p) / 100
    st.markdown(f"**Max Risk per Trade:** ₹{max_risk:.0f}")
    st.divider()
    auto_filter = st.checkbox("💎 Alpha + High WinRate (>65%)", value=False)

c1, c2, c3, c4 = st.columns([3, 2, 1.5, 1.5])
with c1: p_in = st.text_input("Names", "SBIN, ITC, TATAMOTORS, COALINDIA", label_visibility="collapsed")
with c2: u_file = st.file_uploader("CSV", type="csv", label_visibility="collapsed")

load_area = st.empty()

with c3:
    if st.button("📥 LOAD DATA"):
        stocks = []
        if u_file: stocks = pd.read_csv(u_file).iloc[:, 0].dropna().astype(str).tolist()
        elif p_in: stocks = [x.strip() for x in p_in.split(",") if x.strip()]
        if stocks:
            st.session_state['final_list'] = stocks
            st.session_state['load_status'] = f"✅ Ready: {len(stocks)} Stocks"

if st.session_state['load_status']:
    load_area.markdown(f"<div style='color:#FF9933; font-weight:bold; margin-bottom:10px;'>{st.session_state['load_status']}</div>", unsafe_allow_html=True)

with c4:
    if st.button("🚀 SCAN STOCKS", type="primary"):
        if st.session_state['final_list']:
            sec_trends = get_all_sector_trends()
            results = []
            p_bar = st.progress(0)
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exe:
                futures = {exe.submit(analyze_stock, n, sec_trends, n_ret): n for n in st.session_state['final_list']}
                for i, f in enumerate(concurrent.futures.as_completed(futures)):
                    res = f.result()
                    if res: results.append(res)
                    p_bar.progress((i+1)/len(st.session_state['final_list']))
            st.session_state['df_main'] = pd.DataFrame(results)

# --- 6. ERROR-FREE DATA EDITOR ---
if not st.session_state['df_main'].empty:
    df_to_show = st.session_state['df_main'].copy()
    
    if auto_filter:
        df_to_show['wr_num'] = pd.to_numeric(df_to_show['WinRate'].str.replace('%',''), errors='coerce').fillna(0)
        df_to_show = df_to_show[(df_to_show['wr_num'] > 65) & (df_to_show['RS Alpha'] == '👑 Alpha')]
        df_to_show = df_to_show.drop(columns=['wr_num'])

    if df_to_show.empty:
        st.warning("⚠️ No stocks match the Alpha + 65% WinRate criteria.")
    else:
        st.markdown("### 🏆 Top Picks (Price Sync Enabled)")
        
        # Capture the edited data
        edited_data = st.data_editor(
            df_to_show.style.map(apply_traffic_styles),
            use_container_width=True, hide_index=True,
            disabled=["Stock", "Sector", "Sec_Trend", "RS Alpha", "52W High", "EMA Zone", "Vol Action", "WinRate"],
            column_config={
                "Risk_Amt": None, "Price": st.column_config.NumberColumn("💲 Price", format="%.2f", step=0.1),
                "SL": st.column_config.NumberColumn("🛑 SL", format="%.2f"),
                "Target (1:2)": st.column_config.NumberColumn("🎯 Target", format="%.2f")
            },
            key="v15_editor"
        )

        # 🧠 STABLE SYNC: Compare row by row carefully to avoid IndexError
        needs_rerun = False
        for idx in range(len(edited_data)):
            original_idx = df_to_show.index[idx]
            new_p = edited_data.iloc[idx]['Price']
            old_p = st.session_state['df_main'].at[original_idx, 'Price']
            
            if new_p != old_p:
                risk_amt = st.session_state['df_main'].at[original_idx, 'Risk_Amt']
                st.session_state['df_main'].at[original_idx, 'Price'] = new_p
                st.session_state['df_main'].at[original_idx, 'SL'] = round(new_p - risk_amt, 2)
                st.session_state['df_main'].at[original_idx, 'Target (1:2)'] = round(new_p + (risk_amt * 2), 2)
                needs_rerun = True

        if needs_rerun:
            st.rerun()

    st.divider()
    st.subheader("🎯 Trade Execution Planner")
    if not df_to_show.empty:
        stocks_available = df_to_show['Stock'].tolist()
        pick = st.selectbox("👉 Select Stock:", stocks_available)
        row = st.session_state['df_main'][st.session_state['df_main']['Stock'] == pick].iloc[0]
        
        risk_per_sh = row['Price'] - row['SL'] if row['Price'] > row['SL'] else 1
        qty = int(max_risk / risk_per_sh)
        
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("📦 Quantity", f"{qty} Shrs")
        p2.metric("💰 Investment", f"₹{round(qty * row['Price'], 2)}")
        p3.metric("🎯 Target (1:2)", f"₹{row['Target (1:2)']}")
        p4.metric("🛑 Stoploss", f"₹{row['SL']}")
