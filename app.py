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
    th { background-color: #1E2129 !important; color: #00FFC8 !important; font-size: 16px !important;}
    </style>
    """, unsafe_allow_html=True)

st.title("⚡ SNIPER Momentum Terminal")

with st.expander("🧠 Insider Strategy Analysis (Click to view)"):
    st.markdown("""
    🟢 **Early RSI (>= 58):** 60 దాటడానికి ముందే పట్టుకునే లాజిక్. 70 దాటితే 🚀 Super Bullish!  
    🔵 **EMA 20 Distance (Rubber Band):** స్టాక్ EMA 20 కి 8% కంటే ఎక్కువ దూరంలో ఉంటే 'Overextended' (ప్రమాదం). దగ్గరగా ఉంటే 'Perfect Entry'.  
    📉 **Pullback Volume:** ధర పడిపోయినప్పుడు వాల్యూమ్ తక్కువగా ఉంటే (Dry Volume), అది ఇన్స్టిట్యూషన్స్ హోల్డ్ చేస్తున్నారని అర్థం.
    """)

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
    else:
        return name if name.endswith(".NS") else name + ".NS"

with st.sidebar:
    st.header("🛡️ Risk Controller")
    cap_rupees = st.number_input("Capital (₹)", value=100000, step=5000)
    risk_pct = st.slider("Risk per Trade (%)", min_value=0.5, max_value=5.0, value=1.0, step=0.1)
    max_l = (cap_rupees * risk_pct) / 100
    st.markdown(f"**Max Risk per Trade:** ₹{max_l:.0f}")
    
    st.write("---")
    st.header("⚙️ Sniper Engine")
    strict_mode = st.checkbox("🔥 Enable Pro Filters (RSI, EMA 20, Volume)", value=True)

c1, c2, c3, c4 = st.columns([3, 2, 1.5, 1.5])
with c1: 
    p_input = st.text_input("Names", placeholder="NTPC, COAL INDIA...", label_visibility="collapsed")
with c2: 
    u_file = st.file_uploader("CSV", type="csv", label_visibility="collapsed")

with c3:
    if st.button("📥 LOAD DATA", type="secondary"):
        stocks = []
        if u_file:
            df_csv = pd.read_csv(u_file)
            for col in df_csv.columns:
                if df_csv[col].astype(str).str.contains('[A-Za-z]').any():
                    stocks = df_csv[col].dropna().astype(str).tolist()
                    break
        elif p_input:
            stocks = [x.strip() for x in p_input.replace('\n', ',').split(',') if x.strip()]
        
        if stocks: 
            st.session_state['final_list'] = stocks
            st.session_state['load_success'] = True
        else:
            st.session_state['load_success'] = False
        st.rerun()
        
    # ఈ ఒక్క చిన్న లైన్ మాత్రమే యాడ్ చేశాను, మీ లాజిక్ ఏమీ మారదు
    if st.session_state['load_success']:
        st.markdown(f"<div style='color:#00FFC8; font-weight:bold; text-align:center;'>✅ {len(st.session_state['final_list'])} Stocks Ready!</div>", unsafe_allow_html=True)

with c4:
    if st.button("🚀 SCAN STOCKS", type="primary"):
        if not st.session_state['final_list']:
            st.warning("Load Data First!")
        else:
            raw_data, logs = [], []
            p_bar = st.progress(0)
            status_txt = st.empty()
            
            for i, raw_name in enumerate(st.session_state['final_list']):
                time.sleep(0.2)
                if str(raw_name).isdigit() or len(str(raw_name)) < 2: continue
                
                status_txt.markdown(f"**Scanning:** {raw_name}...")
                ticker = get_nse_ticker(raw_name)
                
                try:
                    df = yf.Ticker(ticker).history(period="1y")
                    if df.empty or len(df) < 100:
                        logs.append({"Stock": raw_name, "Status": "No Data"})
                        continue
                    
                    last_p = float(df['Close'].iloc[-1])
                    prev_p = float(df['Close'].iloc[-2])
                    if last_p < 50: continue
                    
                    # --- INDICATORS CALCULATION ---
                    delta = df['Close'].diff()
                    gain = delta.clip(lower=0)
                    loss = -1 * delta.clip(upper=0)
                    ema_gain = gain.ewm(com=13, adjust=False).mean()
                    ema_loss = loss.ewm(com=13, adjust=False).mean()
                    rs = ema_gain / ema_loss
                    df['RSI'] = 100 - (100 / (1 + rs))
                    rsi_val = float(df['RSI'].iloc[-1])
                    
                    ema20 = float(df['Close'].ewm(span=20, adjust=False).mean().iloc[-1])
                    sma50 = float(df['Close'].rolling(50).mean().iloc[-1])
                    
                    avg_vol = float(df['Volume'].rolling(20).mean().iloc[-1])
                    today_vol = float(df['Volume'].iloc[-1])
                    
                    # 💡 NEW LOGIC: Distance from EMA 20 (%)
                    dist_from_ema = ((last_p - ema20) / ema20) * 100
                    
                    # 💡 NEW LOGIC: Pullback Volume Analysis
                    vol_status = "Normal"
                    if last_p < prev_p and today_vol < avg_vol:
                        vol_status = "📉 Dry Pullback (Safe)"
                    elif last_p < prev_p and today_vol > avg_vol:
                        vol_status = "🩸 Heavy Selling (Risky)"
                    elif last_p > prev_p and today_vol > avg_vol:
                        vol_status = "📈 Volume Breakout!"
                    
                    # --- STRICT FILTERS ---
                    if strict_mode:
                        if avg_vol < 100000:
                            logs.append({"Stock": raw_name, "Status": "Low Volume"})
                            continue
                        if last_p < ema20:
                            logs.append({"Stock": raw_name, "Status": "Below EMA 20"})
                            continue
                        if last_p < sma50:
                            logs.append({"Stock": raw_name, "Status": "Below SMA 50"})
                            continue
                        if rsi_val < 58:  
                            logs.append({"Stock": raw_name, "Status": f"RSI < 58 ({rsi_val:.1f})"})
                            continue

                    # ATR RISK
                    h_l = df['High'] - df['Low']
                    tr = pd.concat([h_l, abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)
                    risk_per_share = 1.5 * float(tr.rolling(14).mean().iloc[-1])
                    if risk_per_share <= 0: risk_per_share = last_p * 0.02
                    
                    # Labeling
                    rsi_label = f"{rsi_val:.1f} 🚀" if rsi_val >= 70 else (f"{rsi_val:.1f} 🔥" if rsi_val >= 60 else f"{rsi_val:.1f} 📈")
                    
                    # Danger Zone Check
                    ema_zone = f"Perfect ({dist_from_ema:.1f}%)" if dist_from_ema <= 8 else f"⚠️ Extended ({dist_from_ema:.1f}%)"

                    raw_data.append({
                        "Stock": raw_name, "Symbol": ticker, 
                        "Price": round(last_p, 2), "RSI": rsi_label,
                        "EMA 20 Zone": ema_zone,
                        "Volume Action": vol_status,
                        "SL": round(last_p - risk_per_share, 2), 
                        "Risk_Per_Share": risk_per_share
                    })
                        
                except Exception as e:
                    logs.append({"Stock": raw_name, "Status": "Data Error"})
                
                p_bar.progress((i + 1) / len(st.session_state['final_list']))
            
            status_txt.success("✨ Sniper Scan Complete!")
            st.session_state['raw_scan_data'] = raw_data
            st.session_state['debug_info'] = logs

# --- DYNAMIC RESULTS ---
if st.session_state['raw_scan_data']:
    st.divider()
    
    display_list = []
    for item in st.session_state['raw_scan_data']:
        q = int(max_l / item['Risk_Per_Share'])
        if (q * item['Price']) > cap_rupees: q = int(cap_rupees / item['Price'])
        
        if q > 0:
            display_list.append({
                "⭐ Stock": item['Stock'],
                "📊 RSI": item['RSI'],
                "🔵 EMA Zone": item['EMA 20 Zone'],
                "🔊 Vol Action": item['Volume Action'],
                "💲 Price": item['Price'], 
                "🛑 SL": item['SL'], 
                "📦 Qty": q, 
                "💰 Invest (₹)": round(q * item['Price'], 2)
            })
            
    if display_list:
        df_final = pd.DataFrame(display_list)
        st.markdown("### 🏆 Top Sniper Picks")
        
        # Color formatting
        def color_cells(val):
            if isinstance(val, str):
                if '⚠️ Extended' in val or '🩸 Heavy' in val: return 'color: #FF4B4B;'
                if 'Perfect' in val or 'Dry Pullback' in val or 'Breakout' in val: return 'color: #00FFC8;'
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
            st.metric("🛑 Total Risk (If SL Hit)", f"₹ {round(manual_qty * base_item['Risk_Per_Share'], 2)}")
        st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state['debug_info']:
    st.error("No stocks matched the strict criteria.")
    
if st.session_state['debug_info']:
    with st.expander("🔍 Rejection Details (Why stocks failed)"):
        st.table(pd.DataFrame(st.session_state['debug_info']))