def run_backtest(df):
    try:
        data = df.tail(252).copy()
        data['EMA20'] = data['Close'].ewm(span=20).mean()

        wins = 0
        total = 0

        for i in range(1, len(data) - 10):

            # Entry condition: price crosses above EMA20
            if data['Close'].iloc[i] > data['EMA20'].iloc[i] and \
               data['Close'].iloc[i-1] <= data['EMA20'].iloc[i-1]:

                total += 1

                future_high = data['High'].iloc[i+1:i+11].max()

                # Win condition: +5% move
                if future_high > data['Close'].iloc[i] * 1.05:
                    wins += 1

        if total == 0:
            return 0

        return round((wins / total) * 100, 1)

    except Exception as e:
        print("Backtest Error:", e)
        return 0
