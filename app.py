import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
import concurrent.futures

st.set_page_config(page_title="PRO Swing Trading Terminal", layout="wide")

if 'final_list' not in st.session_state: st.session_state['final_list'] = []
if 'raw_scan_data' not in st.session_state: st.session_state['raw_scan_data'] = []
if 'debug_info' not in st.session_state: st.session_state['debug_info'] = []
if 'load_success' not in st.session_state: st.session_state['load_success'] = False

SECTOR_INDICES = {
    "Financial Services": "^NSEBANK", "Technology": "^CNXIT", "Healthcare": "^CNXPHARMA",
    "Consumer Cyclical": "^CNXAUTO", "Consumer Defensive": "^CNXFMCG", "Basic Materials": "^CNXMETAL",
    "Energy": "^CNXENERGY", "Industrials": "^CNXINFRA", "Real Estate": "^CNXREALTY", "Communication Services": "^CNXMEDIA"
}

st.markdown("""
    <style>
    [data-testid="stHeader"] {height: 0rem !important;}
    h1 { font-size: 1.8rem !important; margin-top: -30px; 
         background: -webkit-linear-gradient(45deg, #FF9933, #FF4B4B); 
         -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
         font-weight: 800; letter-spacing: 1px;}
    .stButton>button { height: 45px !important; width: 100% !important; font-weight: bold !important; border-radius: 8px !important; }
    th { background-color: #1E2129 !important; color: #FF9933 !important; font-size: 16px !important;}
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 PRO Swing Trading Terminal")

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
        
        nifty_50d_ret = ((close - nifty['Close'].iloc[-50]) / nifty['Close'].iloc[-50]) * 100
        health_text = f"<span style='color:#FF9933;'>**NIFTY 50:** {close:.0f}</span> | **Trend:** {status} | **RSI:** {rsi:.1f}"
        return health_text, nifty_50d_ret
    except: return "NIFTY 50: Status Unavailable", 0

market_health, nifty_50d_ret = get_market_health()
st.markdown(f"<div style='padding:10px; background-color:#1E2129; border-radius:8px; text-align:center; border:1px solid #FF9933; margin-bottom:15px;'>🧭 {market_health}</div>", unsafe_allow_html=True)

@st.cache_data(ttl=900)
def get_all_sector_trends():
    sector_trends = {}
    for sec, ticker in SECTOR_INDICES.items():
        try:
            df_sec = yf.Ticker(ticker).history(period="3mo")
            if len(df_sec) < 50: continue
            delta = df_sec['Close'].diff()
            gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
            loss = (-1 * delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
            sec_rsi_val = float((100 - (100 / (1 + (gain / loss)))).iloc[-1])
            sector_trends[sec] = f"{sec_rsi_val:.1f} 🚀" if sec_rsi_val >= 60 else f"{sec_rsi_val:.1f} ⚠️"
        except: sector_trends[sec] = "N/A"
    return sector_trends

def get_nse_ticker(name):
    name = str(name).strip().upper()
    if " " in name or "LTD" in name or "LIMITED" in name or "CORP" in name:
        clean_name = name.replace(" LIMITED", "").replace(" LTD", "").replace(" (INDIA)", "").replace(" CORPORATION", "").strip()
        try:
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={clean_name}"
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
            for quote in res.get('quotes', []):
                if quote.get('exchange') == 'NSI': return quote['symbol']
            return clean_name.split()[0] + ".NS"
        except: return clean_name.split()[0] + ".NS"
    else: return name if name.endswith(".NS") else name + ".NS"

def analyze_stock(raw_name, sector_trends_dict, strict_mode, nifty_50d_ret):
    if len(str(raw_name)) < 2: return {"success": False, "log": None}
    ticker = get_nse_ticker(raw_name)
    
    try:
        yticker = yf.Ticker(ticker)
        df = yticker.history(period="2y") 
        
        if len(df) < 200: return {"success": False, "log": {"Stock": raw_name, "Status": "Not enough data for 200 MA"}}
        
        last_p, prev_p = float(df['Close'].iloc[-1]), float(df['Close'].iloc[-2])
        if last_p < 50: return {"success": False, "log": {"Stock": raw_name, "Status": "Price < 50"}}
        
        today_vol = float(df['Volume'].iloc[-1])
        turnover = last_p * today_vol 
        
        high_52w = float(df['High'].tail(252).max())
        dist_from_52w = ((high_52w - last_p) / high_52w) * 100
        
        stock_50d_ret = ((last_p - df['Close'].iloc[-50]) / df['Close'].iloc[-50]) * 100
        rs_rating = stock_50d_ret - nifty_50d_ret
        rs_str = f"👑 Alpha (+{rs_rating:.1f}%)" if rs_rating > 5 else (f"🟢 Outperforming (+{rs_rating:.1f}%)" if rs_rating > 0 else f"🔴 Weak ({rs_rating:.1f}%)")
        
        stock_sector = "Unknown"
        for _ in range(2): 
            try:
                info_dict = yticker.info
                stock_sector = info_dict.get('sector', info_dict.get('industry', 'Unknown'))
                if stock_sector != "Unknown": break
            except: time.sleep(0.5)
            
        sector_trend = sector_trends_dict.get(stock_sector, "N/A")
        short_sector = stock_sector.replace(" Services", "").replace(" Defensive", "").replace(" Cyclical", "")
        
        ema20 = float(df['Close'].ewm(span=20, adjust=False).mean().iloc[-1])
        sma50 = float(df['Close'].rolling(50).mean().iloc[-1])
        sma200 = float(df['Close'].rolling(200).mean().iloc[-1])
        
        avg_vol = float(df['Volume'].rolling(20).mean().iloc[-1])
        dist_from_ema = ((last_p - ema20) / ema20) * 100
        
        vol_mult = today_vol / avg_vol if avg_vol > 0 else 1
        vol_status = "Normal"
        
        if vol_mult >= 3.0 and last_p > prev_p: vol_status = f"🔥 MEGA SPIKE ({vol_mult:.1f}x)"
        elif last_p < prev_p and today_vol < avg_vol: vol_status = f"📉 Dry Pullback ({vol_mult:.1f}x)"
        elif last_p < prev_p and today_vol > avg_vol: vol_status = f"🩸 Heavy Selling ({vol_mult:.1f}x)"
        elif last_p > prev_p and today_vol > avg_vol: vol_status = f"📈 Breakout ({vol_mult:.1f}x)"
        
        if strict_mode:
            if turnover < 10000000: 
                return {"success": False, "log": {"Stock": raw_name, "Status": "Turnover < 1 Crore"}}
            if dist_from_52w > 25: 
                return {"success": False, "log": {"Stock": raw_name, "Status": f"Too far from 52W High ({dist_from_52w:.1f}%)"}}
            if rs_rating < -5: 
                return {"success": False, "log": {"Stock": raw_name, "Status": f"Weak vs Nifty ({rs_rating:.1f}%)"}}
            if last_p < ema20 or last_p < sma50 or last_p < sma200:
                return {"success": False, "log": {"Stock": raw_name, "Status": "Failed Trend Filters (Below MAs)"}}

        tr = pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
        risk_per_share = 1.5 * float(tr.rolling(14).mean().iloc[-1])
        if risk_per_share <= 0: risk_per_share = last_p * 0.02 
        
        ema_zone = f"Perfect ({dist_from_ema:.1f}%)" if dist_from_ema <= 8 else f"⚠️ Extended ({dist_from_ema:.1f}%)"
        high_dist_str = f"Near High ({dist_from_52w:.1f}%)" if dist_from_52w <= 10 else f"{dist_from_52w:.1f}% Away"

        tv_symbol = ticker.replace(".NS", "")
        tv_link = f"https://in.tradingview.com/chart/?symbol=NSE:{tv_symbol}"

        data = {
            "Stock": raw_name, "Ticker": ticker, "Sector": short_sector, "Sec_Trend": sector_trend,
            "RS (Nifty)": rs_str, "52W High": high_dist_str, "EMA Zone": ema_zone, "Vol Action": vol_status, 
            "Price": round(last_p, 2), "SL": round(last_p - risk_per_share, 2),
            "Risk_Per_Share": risk_per_share, "Chart": tv_link
        }
        return {"success": True, "data": data}
    except Exception: return {"success": False, "log": {"Stock": raw_name, "Status": "Error Fetching Data"}}

with st.sidebar:
    st.header("🛡️ Pro Risk Controller")
    cap_rupees = st.number_input("Capital (₹)", value=100000, step=5000)
    risk_pct = st.slider("Risk per Trade (%)", min_value=0.5, max_value=5.0, value=1.0, step=0.1)
    max_l = (cap_rupees * risk_pct) / 100
    st.markdown(f"**Max Risk per Trade:** ₹{max_l:.0f}")
    st.write("---")
    strict_mode = st.checkbox("🔥 Enable Pro Swing Filters", value=True)

c1, c2, c3, c4 = st.columns([3, 2, 1.5, 1.5])
with c1: p_input = st.text_input("Names", placeholder="NTPC, ITC...", label_visibility="collapsed")
with c2: u_file = st.file_uploader("CSV", type="csv", label_visibility="collapsed")
with c3:
    if st.button("📥 LOAD DATA", type="secondary"):
        stocks = []
        if u_file:
            df_csv = pd.read_csv(u_file)
            for col in df_csv.columns:
                if df_csv[col].astype(str).str.contains('[A-Za-z]').any():
                    stocks = df_csv[col].dropna().astype(str).tolist()
                    break
        elif p_input: stocks = [x.strip() for x in p_input.replace('\n', ',').split(',') if x.strip()]
        
        st.session_state['final_list'] = stocks
        st.session_state['load_success'] = bool(stocks)
        st.rerun()
        
    if st.session_state['load_success']:
        st.markdown(f"<div style='color:#FF9933; font-weight:bold; text-align:center;'>✅ {len(st.session_state['final_list'])} Ready!</div>", unsafe_allow_html=True)

with c4:
    if st.button("🚀 SCAN STOCKS", type="primary"):
        if not st.session_state['final_list']: st.warning("Load Data First!")
        else:
            raw_data, logs = [], []
            with st.spinner("Analyzing Sectors & Preparing Setup..."):
                sector_trends_dict = get_all_sector_trends()

            p_bar = st.progress(0)
            status_txt = st.empty()
            status_txt.markdown(f"**⚡ Scanning {len(st.session_state['final_list'])} stocks...**")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(analyze_stock, name, sector_trends_dict, strict_mode, nifty_50d_ret): name for name in st.session_state['final_list']}
                for i, future in enumerate(concurrent.futures.as_completed(futures)):
                    res = future.result()
                    if res['success']: raw_data.append(res['data'])
                    elif res['log']: logs.append(res['log'])
                    p_bar.progress((i + 1) / len(st.session_state['final_list']))
            
            status_txt.success("✨ Pro Scan Complete!")
            st.session_state['raw_scan_data'] = raw_data
            st.session_state['debug_info'] = logs
            st.session_state['scan_triggered'] = True 

if st.session_state['raw_scan_data']:
    st.divider()
    
    if st.session_state.get('scan_triggered', False) or 'df_final' not in st.session_state:
        st.session_state['df_final'] = pd.DataFrame(st.session_state['raw_scan_data'])
        st.session_state['scan_triggered'] = False
        
    st.markdown("### 🏆 Top Swing Picks (✏️ **Double-click Price or SL to Edit!**)")
    st.markdown("<span style='color:grey; font-size:14px;'>*Click 'Open 📊' to see TradingView chart.*</span>", unsafe_allow_html=True)
    
    def color_cells(val):
        if isinstance(val, str):
            if '⚠️' in val or '🩸' in val or 'Away' in val or 'Weak' in val or '🔴' in val: return 'color: #FF4B4B;'
            if 'Perfect' in val or 'Dry Pullback' in val or 'Near High' in val or 'Outperforming' in val or '🟢' in val: return 'color: #00FFC8;'
            if 'MEGA SPIKE' in val or 'Alpha' in val or '👑' in val: return 'color: #FFD700; font-weight: bold;'
        return ''
    
    df_to_display = st.session_state['df_final']
    styled_df = df_to_display.style.map(color_cells) if hasattr(df_to_display.style, 'map') else df_to_display.style.applymap(color_cells)
    
    edited_df = st.data_editor(
        styled_df,
        use_container_width=True,
        hide_index=True,
        disabled=['Stock', 'Sector', 'Sec_Trend', 'RS (Nifty)', '52W High', 'EMA Zone', 'Vol Action', 'Chart'], 
        column_config={
            "Risk_Per_Share": None, 
            "Ticker": None, 
            "RS (Nifty)": st.column_config.TextColumn("⚖️ RS (Nifty)"),
            "52W High": st.column_config.TextColumn("🎯 52W High"),
            "Chart": st.column_config.LinkColumn("📺 Chart", display_text="Open 📊"),
            "Price": st.column_config.NumberColumn("💲 Price", format="%.2f", step=0.5),
            "SL": st.column_config.NumberColumn("🛑 SL (ATR)", format="%.2f", step=0.5)
        }
    )
    
    needs_rerun = False
    for idx in edited_df.index:
        old_price = st.session_state['df_final'].at[idx, 'Price']
        new_price = edited_df.at[idx, 'Price']
        old_sl = st.session_state['df_final'].at[idx, 'SL']
        new_sl = edited_df.at[idx, 'SL']
        
        if new_price != old_price and new_sl == old_sl:
            risk_amt = st.session_state['df_final'].at[idx, 'Risk_Per_Share']
            edited_df.at[idx, 'SL'] = round(new_price - risk_amt, 2)
            needs_rerun = True
            
    if needs_rerun:
        st.session_state['df_final'] = edited_df
        st.rerun()
    else:
        st.session_state['df_final'] = edited_df
    
    st.markdown("<br><h3 style='color:#FF9933;'>🎯 Trade Execution Planner</h3>", unsafe_allow_html=True)
    selected_stock = st.selectbox("👉 Choose Stock to view Final Plan", st.session_state['df_final']['Stock'].tolist())
    
    row = st.session_state['df_final'][st.session_state['df_final']['Stock'] == selected_stock].iloc[0]
    calc_price, calc_sl = float(row['Price']), float(row['SL'])
    new_risk_per_share = calc_price - calc_sl if (calc_price - calc_sl) > 0 else 1 
    
    calc_qty = max(1, int(max_l / new_risk_per_share))
    if (calc_qty * calc_price) > cap_rupees: calc_qty = max(1, int(cap_rupees / calc_price))
    
    st.markdown(f"<div style='background-color:#1E2129; padding:20px; border-radius:10px; border: 1px solid #FF9933;'>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(f"<h4 style='color:#FF9933; margin-top:0px;'>{selected_stock}</h4><span style='color:white; font-size:14px;'>{row['Sector']} | RSI: {row['Sec_Trend']}</span>", unsafe_allow_html=True)
    with col2: st.metric("📦 Adjusted Quantity", f"{calc_qty} Shares")
    with col3: st.metric("💰 Total Invest", f"₹ {round(calc_qty * calc_price, 2)}")
    with col4: st.metric("🛑 Total Risk", f"₹ {round(calc_qty * new_risk_per_share, 2)}")
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state['debug_info']:
    st.error("No stocks matched the Strict Pro Filters.")
    with st.expander("🔍 Rejection Details (Why stocks failed)"):
        st.table(pd.DataFrame(st.session_state['debug_info']))
