import yfinance as yf
import pandas as pd
import warnings
from indicators_exact import calculate_ema, calculate_rsi, calculate_atr
from backtest_clean import run_backtest

# 🔥 OPTIONAL (CLEAN LOGS)
warnings.filterwarnings("ignore")

def analyze_stock(name, sector_trends, nifty_ret):
    try:
        # � REPLACE ticker logic COMPLETELY with this:
        s_name = str(name).strip().upper()

        # remove everything wrong
        s_name = s_name.replace(".NS", "").replace("$", "")

        ticker = s_name + ".NS"
        df = yf.Ticker(ticker).history(period="2y")

        if df.empty or len(df) < 50:
            return None

        last_p = float(df['Close'].iloc[-1])
        prev_p = float(df['Close'].iloc[-2])

        # --- TREND FILTER ---
        if len(df) >= 200:
            ma200 = df['Close'].rolling(200).mean().iloc[-1]
            # TEMPORARILY DISABLED FOR TESTING
            # if last_p < ma200:
            #     return None
        else:
            ema20 = float(calculate_ema(df['Close'], 20).iloc[-1])
            ema50 = float(calculate_ema(df['Close'], 50).iloc[-1])
            if last_p < ema20 or last_p < ema50:
                return None

        # --- INDICATORS ---
        ema20 = float(calculate_ema(df['Close'], 20).iloc[-1])
        rsi = float(calculate_rsi(df['Close']).iloc[-1])
        atr = float(calculate_atr(df).iloc[-1])

        # --- METRICS ---
        high_52 = float(df['High'].tail(252).max())
        dist_52w = (high_52 - last_p) / high_52 * 100

        rs_rating = ((last_p - df['Close'].iloc[-50]) / df['Close'].iloc[-50]) * 100 - nifty_ret

        vol_mult = float(df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1])

        # --- BACKTEST ---
        winrate = float(run_backtest(df))

        risk_val = float(atr * 1.5)

        return {
            "Stock": name,
            "Price": round(float(last_p), 2),
            "RS": round(float(rs_rating), 2),
            "RSI": round(float(rsi), 2),
            "52W_Dist": round(float(dist_52w), 2),
            "Volume": round(float(vol_mult), 2),
            "WinRate": float(winrate),
            "SL": round(float(last_p - risk_val), 2),
            "Target": round(float(last_p + (risk_val * 2)), 2),
            "ATR": round(float(atr), 2)
        }

    except Exception as e:
        print(f"Error {name}:", e)
        return None
