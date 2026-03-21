import streamlit as st
import pandas as pd
import yfinance as yf

# 1. పేజీ సెట్టింగ్స్
st.set_page_config(page_title="My Trading App", layout="centered")

# 2. టైటిల్
st.title("My Trading App 🎉")
st.write("If you see this, your app is working perfectly!")

# 3. బెలూన్లు (ఇది వస్తేనే యాప్ లోడ్ అయినట్టు)
st.balloons()

# 4. ఒక చిన్న డేటా టెస్ట్
ticker = st.text_input("Enter Stock Symbol", "AAPL")
data = yf.download(ticker, period="1mo")
st.write(f"Showing data for {ticker}:")
st.line_chart(data['Close'])
