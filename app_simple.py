import streamlit as st

# ✅ STEP 1 — ENABLE WIDE MODE (VERY IMPORTANT)
st.set_page_config(layout="wide")

import pandas as pd
from scanner_clean import analyze_stock
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings("ignore")

# ---------- STYLE ----------
st.markdown("""
<style>

/* 🔥 Make ALL inputs same height */
div[data-baseweb="input"] input {
    height: 48px !important;
    font-size: 16px;
}

/* File uploader same height */
section[data-testid="stFileUploader"] {
    height: 48px !important;
}

/* Remove extra padding inside uploader */
section[data-testid="stFileUploader"] > div {
    padding: 6px !important;
}

/* 🔥 Scan button EXACT same height */
div.stButton > button {
    height: 48px !important;
    width: 150%;
    font-size: 16px;
    border-radius: 8px;
}

/* Align vertically center */
div.row-widget.stHorizontal {
    align-items: center;
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 0rem;
    padding-left: 1rem;
    padding-right: 1rem;
}
.main .block-container {
    max-width: 100% !important;
    padding-left: 1rem;
    padding-right: 1rem;
}
[data-testid="stSidebar"] {
    width: 250px;
}
</style>
""", unsafe_allow_html=True)

# ---------- HELPERS ----------
def load_default_stocks():
    try:
        df = pd.read_csv("nifty500.csv")
        stocks = df["Symbol"].dropna().tolist()
    except:
        stocks = []

    # IPO / new listings (you can update anytime)
    ipo_stocks = ["TATATECH", "IREDA", "PAYTM", "NYKAA"]

    return list(set(stocks + ipo_stocks))

def clean_symbol(symbol):
    symbol = symbol.upper().strip().replace("$", "")
    if symbol.endswith(".NS"):
        symbol = symbol.replace(".NS", "")
    return symbol + ".NS"

@st.cache_data(ttl=3600)
def cached_analyze_stock(symbol):
    return analyze_stock(symbol, {}, 0)

def scan_all(stocks):
    results = []

    def process_stock(s):
        try:
            return cached_analyze_stock(clean_symbol(s))
        except:
            return None

    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = [executor.submit(process_stock, s) for s in stocks]
        for f in as_completed(futures):
            res = f.result()
            if res:
                results.append(res)

    return results

# ---------- UI ----------
st.title("Simple Scanner")

# Sidebar
with st.sidebar:
    st.header("Risk Settings")
    capital = st.number_input("Total Capital ₹", value=100000)
    risk_percent = st.slider("Risk per trade %", 0.5, 5.0, 1.0)
    max_risk = (capital * risk_percent) / 100
    st.write(f"Max Risk per Trade: ₹{max_risk:.0f}")

    st.header("Filters")
    min_rs = st.slider("Min RS", -10, 10, 0)
    min_rsi = st.slider("Min RSI", 0, 100, 50)
    min_wr = st.slider("Min WinRate", 0, 100, 50)

# ---------- INPUT ROW (PERFECT ALIGNMENT) ----------
st.subheader("Stock Input")

# 🔥 SAME HEIGHT + PERFECT ALIGNMENT
col1, col2, col3 = st.columns([4,3,1])

with col1:
    stock_input = st.text_input("Stocks", placeholder="SBIN, ITC, RELIANCE")

with col2:
    uploaded_file = st.file_uploader("Upload CSV", type="csv")

with col3:
    run = st.button("🚀 Scan")

# ---------- MAIN LOGIC ----------
# 🔥 AUTO MODE (runs once per session)
if "auto_run" not in st.session_state:
    st.session_state.auto_run = True

if run or st.session_state.auto_run:
    st.session_state.auto_run = False

    stocks = []

    # CSV
    if uploaded_file is not None:
        df_upload = pd.read_csv(uploaded_file)
        stocks = df_upload.iloc[:, 0].dropna().astype(str).tolist()

    # Manual
    elif stock_input:
        stocks = [s.strip() for s in stock_input.split(",") if s.strip()]

    else:
        stocks = load_default_stocks()   # 🔥 AUTO NIFTY 500

    if not stocks:
        st.warning("Enter stocks or upload CSV")
        st.stop()

    # ✅ 2. FIX BLUE BOX (REMOVE WASTE SPACE)
    with st.spinner("Scanning..."):
        results = scan_all(stocks)

    if not results:
        st.error("No data fetched")
        st.stop()

    df = pd.DataFrame(results).round(2)

    # Rename
    df = df.rename(columns={
        "Price": "Price ₹",
        "RS": "RS Strength",
        "52W_Dist": "52W Distance %",
        "Volume": "Vol x",
        "WinRate": "Win %",
        "SL": "StopLoss"
    })

    # ---------- ATR LOGIC ----------
    risk_mult = 1.5
    reward_mult = 3

    df["StopLoss"] = df["Price ₹"] - (df["ATR"] * risk_mult)
    df["Target"] = df["Price ₹"] + (df["ATR"] * reward_mult)

    # ---------- POSITION SIZING ----------
    df["Risk per Share"] = (df["Price ₹"] - df["StopLoss"]).replace(0, 1)
    df["Qty"] = (max_risk / df["Risk per Share"]).astype(int)
    df["Investment"] = df["Qty"] * df["Price ₹"]

    # ---------- SCORE ----------
    def calculate_score(row):
        score = 0

        # 🔥 RS Strength (MOST IMPORTANT)
        if row["RS Strength"] > 5:
            score += 4
        elif row["RS Strength"] > 0:
            score += 2

        # 🔥 RSI (momentum)
        if row["RSI"] > 65:
            score += 3
        elif row["RSI"] > 55:
            score += 2

        # 🔥 Win Rate (confidence)
        if row["Win %"] > 70:
            score += 3
        elif row["Win %"] > 60:
            score += 2

        # 🔥 Near 52W High (breakout zone)
        if "52W Distance %" in row and row["52W Distance %"] < 10:
            score += 2

        # 🔥 Volume (if exists)
        if "Vol x" in row and row["Vol x"] > 1.2:
            score += 1

        return score

    def get_grade(score):
        if score >= 10:
            return "🔥 A+"
        elif score >= 8:
            return "🟢 A"
        elif score >= 6:
            return "🟡 B"
        else:
            return "🔴 Weak"

    df["Score"] = df.apply(calculate_score, axis=1)
    df["Grade"] = df["Score"].apply(get_grade)

    # ---------- FILTER ----------
    df = df[
        (df["RS Strength"] >= min_rs) &
        (df["RSI"] >= min_rsi) &
        (df["Win %"] >= min_wr)
    ]

    if df.empty:
        st.warning("No strong stocks found")
        st.stop()

    df = df.sort_values(["Score", "RS Strength"], ascending=[False, False])

    st.session_state["df"] = df   # ✅ SAVE

# ---------- DISPLAY SECTION ----------
if "df" in st.session_state:

    df = st.session_state["df"]

    st.markdown("### 📊 Top Picks (Smart Ranked)")

    col1, col2 = st.columns([1,5])

    with col1:
        mode = st.radio("View", ["Top 3", "Top 10", "All"])

    with col2:
        st.write(f"Total rows: {len(df)}")

    if mode == "Top 3":
        display_df = df.head(3)
    elif mode == "Top 10":
        display_df = df.head(10)
    else:
        display_df = df

    st.dataframe(
        display_df,
        use_container_width=True,
        height=600,
        hide_index=True
    )

    # ---------- TRADE PLANNER ----------
    st.subheader("Trade Planner")

    selected = st.selectbox("Select Stock", display_df["Stock"])
    row = df[df["Stock"] == selected].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Qty", int(row["Qty"]))
    c2.metric("Investment ₹", f"{row['Investment']:.0f}")
    c3.metric("Target ₹", f"{row['Target']:.2f}")
    c4.metric("StopLoss ₹", f"{row['StopLoss']:.2f}")