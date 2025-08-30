import time
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
import io

# -------------------------------
# Page Config
# -------------------------------
st.set_page_config(page_title="Crypto Dashboard", layout="wide")
st.title("📈 Crypto Multi-Coin Dashboard")
st.markdown("Professional crypto dashboard with multi-coin comparison using **CoinGecko API**")


# -------------------------------
# Fetch all coins
# -------------------------------

@st.cache_data
def get_all_coins():
    try:
        url = "https://api.coingecko.com/api/v3/coins/list"
        headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error fetching coins: {e}")
        return pd.DataFrame()


coins_df = get_all_coins()
if coins_df.empty:
    st.stop()

coin_options = {f"{row['name']} ({row['symbol'].upper()})": row["id"] for _, row in coins_df.iterrows()}

# -------------------------------
# Sidebar Settings
# -------------------------------
st.sidebar.header("Settings")

# Multi-coin selection
selected_coins = st.sidebar.multiselect(
    "Select coins to compare (2-5 coins max):",
    options=list(coin_options.keys()),
    default=[list(coin_options.keys())[0]]
)
selected_ids = [coin_options[c] for c in selected_coins]
currency = st.sidebar.selectbox("Select currency:", ["usd", "eur", "gbp", "jpy", "inr"])
days = st.sidebar.selectbox("Historical Range (days):", ["1", "7", "30", "90", "180", "365"], index=1)

st.sidebar.subheader("Indicators")
show_ma = st.sidebar.checkbox("Show MA7 & MA25", value=True)
show_ema = st.sidebar.checkbox("Show EMA12 & EMA26", value=True)
show_volume = st.sidebar.checkbox("Show Volume", value=True)

st.sidebar.subheader("Live Data Settings")
auto_refresh = st.sidebar.checkbox("Auto-refresh live data", value=True)
refresh_interval = st.sidebar.slider("Refresh interval (sec)", min_value=1, max_value=10, value=3)


# -------------------------------
# Fetch Coin Logos
# -------------------------------
@st.cache_data
def get_coin_logo(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        resp = requests.get(url, headers={"accept": "application/json"}, timeout=10).json()
        return resp.get("image", {}).get("small", "")
    except:
        return ""


# -------------------------------
# Tabs
# -------------------------------
tab1, tab2 = st.tabs(["Live Data", "Historical Data"])

# -------------------------------
# Live Data Tab
# -------------------------------
with tab1:
    st.subheader(f"Live Prices ({currency.upper()})")
    live_data = {c: [] for c in selected_ids}
    placeholder_chart = st.empty()


    def get_live_price(coin_id, currency="usd"):
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": coin_id, "vs_currencies": currency}
            headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            return data.get(coin_id, {}).get(currency, None)
        except:
            return None


    def update_live():
        df_plot = pd.DataFrame()
        metrics_col1, metrics_col2 = st.columns(2)
        for i, coin_id in enumerate(selected_ids):
            price = get_live_price(coin_id, currency)
            if price:
                live_data[coin_id].append({"time": datetime.now(), "price": price})
                df_temp = pd.DataFrame(live_data[coin_id])
                df_temp = df_temp.set_index("time")["price"]
                df_plot[coin_id] = df_temp
                # Display current price with logo
                logo_url = get_coin_logo(coin_id)
                col = metrics_col1 if i % 2 == 0 else metrics_col2
                col.image(logo_url, width=25)
                col.metric(label=coin_id, value=round(price, 8))
        placeholder_chart.line_chart(df_plot)


    if auto_refresh:
        st.info("Auto-refreshing live data...")
        for _ in range(50):
            update_live()
            time.sleep(refresh_interval)
        st.success("✅ Auto-refresh finished!")
    else:
        if st.button("Fetch Live Data"):
            update_live()

    # Download live CSV
    for coin_id in selected_ids:
        if live_data[coin_id]:
            csv_buffer = io.StringIO()
            pd.DataFrame(live_data[coin_id]).to_csv(csv_buffer, index=False)
            st.download_button(f"💾 Download {coin_id} Live CSV", csv_buffer.getvalue(), file_name=f"{coin_id}_live.csv")

# -------------------------------
# Historical Data Tab
# -------------------------------
with tab2:
    st.subheader(f"Historical Data ({currency.upper()})")


    def get_historical_data(coin_id, currency, days=1):
        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {"vs_currency": currency, "days": days}
            headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if "prices" not in data or "total_volumes" not in data:
                return None
            df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
            df["time"] = pd.to_datetime(df["timestamp"], unit="ms")
            df["open"] = df["price"].shift(1)
            df["close"] = df["price"]
            df["high"] = df["price"].rolling(2).max()
            df["low"] = df["price"].rolling(2).min()
            df["volume"] = pd.DataFrame(data["total_volumes"], columns=["timestamp", "volume"])["volume"]
            if show_ma:
                df["MA7"] = df["close"].rolling(7).mean()
                df["MA25"] = df["close"].rolling(25).mean()
            if show_ema:
                df["EMA12"] = df["close"].ewm(span=12, adjust=False).mean()
                df["EMA26"] = df["close"].ewm(span=26, adjust=False).mean()
            return df
        except:
            return None


    all_hist_data = {}
    for coin_id in selected_ids:
        df_hist = get_historical_data(coin_id, currency, days)
        if df_hist is not None:
            all_hist_data[coin_id] = df_hist

    if all_hist_data:
        fig = go.Figure()
        for coin_id, df_hist in all_hist_data.items():
            # Candlestick
            fig.add_trace(go.Candlestick(
                x=df_hist["time"],
                open=df_hist["open"],
                high=df_hist["high"],
                low=df_hist["low"],
                close=df_hist["close"],
                name=f"{coin_id} Candles"
            ))
            # Indicators
            if show_ma:
                for ma in ["MA7", "MA25"]:
                    if ma in df_hist.columns:
                        fig.add_trace(
                            go.Scatter(x=df_hist["time"], y=df_hist[ma], mode="lines", name=f"{coin_id} {ma}"))
            if show_ema:
                for ema in ["EMA12", "EMA26"]:
                    if ema in df_hist.columns:
                        fig.add_trace(
                            go.Scatter(x=df_hist["time"], y=df_hist[ema], mode="lines", name=f"{coin_id} {ema}"))
            # Volume
            if show_volume:
                fig.add_trace(go.Bar(
                    x=df_hist["time"],
                    y=df_hist["volume"],
                    name=f"{coin_id} Volume",
                    marker=dict(opacity=0.3),
                    yaxis="y2"
                ))

        fig.update_layout(
            title=f"Historical Data - Last {days} Days",
            xaxis_title="Time",
            yaxis_title=f"Price ({currency.upper()})",
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        # Download CSVs
        for coin_id, df_hist in all_hist_data.items():
            cols = ["time", "open", "high", "low", "close", "volume"]
            indicator_cols = [col for col in ["MA7", "MA25", "EMA12", "EMA26"] if col in df_hist.columns]
            csv_buffer = io.StringIO()
            df_hist[cols + indicator_cols].to_csv(csv_buffer, index=False)
            st.download_button(f"💾 Download {coin_id} Historical CSV", csv_buffer.getvalue(),
                               file_name=f"{coin_id}_historical.csv")
    else:
        st.warning("No historical data available for selected coins.")
