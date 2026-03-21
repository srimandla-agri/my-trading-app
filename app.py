import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time

st.set_page_config(page_title="Pro Momentum Terminal", layout="wide")

if 'final_list' not in st.session_state: st.session_state['final_list'] = []
if 'raw_scan_data' not in st.session_state: st.session_state['raw_scan_data'] = []
if 'debug_info' not in st.session_state: st.session_state['debug_info'] = []
if 'load_success' not in st.session_state: st.session_state['load_success'] = False

st.markdown("""
    <style>
    [data-testid="stHeader"] {height: 0rem !important;}
    h1 { font-size: 1.8rem !important; margin-top: -30px; 
         background: -webkit-linear-gradient(45deg, #00FFC8, #0080FF); 
         -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
         font-weight: 800; letter-spacing: 1px;}
    .stButton>button { height: 45px !important; width: 100% !important; font-weight: bold !important; border-radius: 8px !important; }
    th { background-color: #1E2129 !important; color: #00FFC8 !important; }
    .stMetric { background-color: #1E2129; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1>⚡ SNIPER MOMENTUM TERMINAL</h1>", unsafe_allow_html=True)

TICKERS = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'INFY.NS', 'BHARTIARTL.NS',
    'SBIN.NS', 'LICI.NS', 'ITC.NS', 'HINDUNILVR.NS', 'LT.NS', 'BAJFINANCE.NS',
    'HCLTECH.NS', 'MARUTI.NS', 'SUNPHARMA.NS', 'ADANIENT.NS', 'KOTAKBANK.NS', 'TITAN.NS',
    'AXISBANK.NS', 'ULTRACEMCO.NS', 'ONGC.NS', 'ADANIPORTS.NS', 'NTPC.NS', 'JSWSTEEL.NS'
]

with st.sidebar:
    st.markdown("### 🛠️ Scan Settings")
    risk_per_trade = st.number_input("Risk Per Trade (₹)", value=2000, step=500)
    momentum_threshold = st.slider("Momentum Strength (%)", 1, 10, 3)
    
    if st.button("📥 LOAD DATA"):
        with st.status("🔍 Scanning Nifty Top 20 Stocks...", expanded=True) as status:
            st.session_state['final_list'] = []
            st.session_state['raw_scan_data'] = []
            st.session_state['debug_info'] = []
            
            for ticker in TICKERS:
                try:
                    st.write(f"Checking {ticker}...")
                    stock = yf.Ticker(ticker)
                    df = stock.history(period="1y")
                    
                    if len(df) < 50: continue
                    
                    cp = df['Close'].iloc[-1]
                    ma20 = df['Close'].rolling(20).mean().iloc[-1]
                    ma50 = df['Close'].rolling(50).mean().iloc[-1]
                    
                    change_1d = ((cp - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100
                    
                    if cp > ma20 > ma50 and change_1d > momentum_threshold:
                        sl = cp * 0.98
                        target = cp * 1.05
                        qty = int(risk_per_trade / (cp - sl)) if (cp - sl) > 0 else 0
                        
                        st.session_state['final_list'].append({
                            '⭐ Stock': ticker.replace('.NS',''),
                            '💰 Price': round(cp, 2),
                            '📈 Chg%': f"{round(change_1d, 2)}%",
                            '🛑 StopLoss': round(sl, 2),
                            '🎯 Target': round(target, 2),
                            '📦 Qty': qty,
                            '💎 Status': 'BULLISH'
                        })
                        
                        st.session_state['raw_scan_data'].append({
                            'Stock': ticker.replace('.NS',''),
                            'Price': cp,
                            'SL': sl
                        })
                except Exception as e:
                    st.session_state['debug_info'].append(f"Error on {ticker}: {e}")
            
            st.session_state['load_success'] = True
            status.update(label="✅ Scan Complete!", state="complete", expanded=False)

if st.session_state['load_success']:
    if not st.session_state['final_list']:
        st.warning("No stocks found matching the criteria. Try lowering the Momentum Strength.")
    else:
        df_final = pd.DataFrame(st.session_state['final_list'])
        
        c1, c2, c3, c4 = st.columns([3, 2, 1.5, 1.5])
        with c1: st.metric("📡 Stocks Scanned", len(TICKERS))
        with c2: st.metric("🔥 Momentum Picks", len(df_final))
        with c3: st.metric("🛡️ Risk Applied", f"₹{risk_per_trade}")
        with c4: st.metric("📊 Timeframe", "Daily")

        st.markdown("### 🚀 Live Signals")
        
        def color_cells(val):
            if 'BULLISH' in str(val): return 'color: #00FFC8; font-weight: bold'
            if '%' in str(val): return 'color: #00FFC8'
            return ''
            
        st.dataframe(df_final.style.applymap(color_cells), use_container_width=True)
        
        st.markdown("<br><h3 style='color:#FFA500;'>🎯 Trade Execution Planner</h3>", unsafe_allow_html=True)
        selected_stock = st.selectbox("👉 Choose Scanned Stock", df_final['⭐ Stock'].tolist())
        row = df_final[df_final['⭐ Stock'] == selected_stock].iloc[0]
        base_item = next(item for item in st.session_state['raw_scan_data'] if item['Stock'] == selected_stock)
        
        st.markdown(f"<div style='background-color:#1E2129; padding:20px; border-radius:10px; border: 1px solid #00FFC8;'>", unsafe_allow_html=True)
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            st.markdown(f"<h4 style='color:#00FFC8;'>{selected_stock}</h4>", unsafe_allow_html=True)
            manual_qty = st.number_input("📦 Adjust Quantity", min_value=1, value=int(row['📦 Qty']), step=1)
        with pc2:
            st.metric("💰 Total Investment", f"₹ {round(manual_qty * base_item['Price'], 2)}")
        with pc3:
            st.metric("🛑 Total Risk (If SL Hit)", f"₹ {round(manual_qty * (base_item['Price'] - base_item['SL']), 2)}")
        st.markdown("</div>", unsafe_allow_html=True)
        
else:
    st.info("👈 Click on 'LOAD DATA' in the sidebar to start the scanner.")

if st.session_state['debug_info']:
    with st.expander("🛠️ Debug Logs"):
        for log in st.session_state['debug_info']:
            st.write(log)
