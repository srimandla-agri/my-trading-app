import yfinance as yf
from backtest_clean import run_backtest

df = yf.Ticker("SBIN.NS").history(period="2y")

print("WinRate:", run_backtest(df))
