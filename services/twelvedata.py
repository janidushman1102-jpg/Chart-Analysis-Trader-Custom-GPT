import os
import math
import requests
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import VolumeWeightedAveragePrice

load_dotenv()

API_KEY = os.getenv("TWELVEDATA_API_KEY")
BASE_URL = "https://api.twelvedata.com"

NSE_SYMBOLS = set()  # auto-detect NSE stocks via Yahoo Finance

def safe_number(value, default=0):
    try:
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return default
        return round(value, 2)
    except Exception:
        return default

class TwelveDataService:

    def __init__(self):
        self.api_key = API_KEY

    def normalize_symbol(self, symbol):
        symbol = symbol.upper().strip()

        try:
            test = yf.Ticker(f"{symbol}.NS")
            df = test.history(period="5d", auto_adjust=True)

            if not df.empty:
                return f"{symbol}.NS"
        except Exception:
            pass

        return symbol

    def get_yahoo_data(self, symbol, interval="1day"):
        interval_map = {
            "15min": "15m",
            "1h": "60m",
            "4h": "60m",
            "1day": "1d"
        }

        if interval == "15min":
            period = "30d"
        elif interval == "1h":
            period = "90d"
        elif interval == "4h":
            period = "180d"
        else:
            period = "1y"

        df = yf.Ticker(symbol).history(
            period=period,
            interval=interval_map.get(interval, "1d"),
            auto_adjust=True
        )

        if df.empty:
            raise Exception(f"No Yahoo data found for {symbol}")

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()
        df.columns = [str(col).lower() for col in df.columns]

        required = ["open", "high", "low", "close", "volume"]

        for col in required:
            if col not in df.columns:
                raise Exception(f"Missing column {col}. Available: {list(df.columns)}")

        for col in required:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.dropna(subset=["close"])

    def get_twelvedata_data(self, symbol, interval="1day", outputsize=500):
        if not self.api_key:
            raise Exception("TWELVEDATA_API_KEY not configured")

        r = requests.get(
            f"{BASE_URL}/time_series",
            params={
                "symbol": symbol,
                "interval": interval,
                "outputsize": outputsize,
                "apikey": self.api_key
            },
            timeout=30
        )

        data = r.json()

        if "values" not in data:
            raise Exception(str(data))

        df = pd.DataFrame(data["values"])
        df = df.iloc[::-1].reset_index(drop=True)

        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def get_time_series(self, symbol, interval="1day", outputsize=500):
        symbol = self.normalize_symbol(symbol)

        if symbol.endswith(".NS"):
            return self.get_yahoo_data(symbol, interval)

        try:
            return self.get_twelvedata_data(symbol, interval, outputsize)
        except Exception:
            return self.get_yahoo_data(symbol, interval)

    def add_indicators(self, df):
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        df["ema20"] = EMAIndicator(close, 20).ema_indicator()
        df["ema50"] = EMAIndicator(close, 50).ema_indicator()
        df["ema200"] = EMAIndicator(close, 200).ema_indicator()
        df["rsi"] = RSIIndicator(close, 14).rsi()

        macd = MACD(close)
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()

        df["adx"] = ADXIndicator(high, low, close, 14).adx()
        df["atr"] = AverageTrueRange(high, low, close, 14).average_true_range()

        bb = BollingerBands(close, 20, 2)
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_lower"] = bb.bollinger_lband()

        try:
            df["vwap"] = VolumeWeightedAveragePrice(
                high=high, low=low, close=close, volume=volume
            ).volume_weighted_average_price()
        except Exception:
            df["vwap"] = close

        df["rvol"] = volume / volume.rolling(20).mean()
        return df.fillna(0)

    def trend(self, row):
        if row["close"] > row["ema20"] > row["ema50"] > row["ema200"]:
            return "STRONG_BULLISH"
        if row["close"] < row["ema20"] < row["ema50"] < row["ema200"]:
            return "STRONG_BEARISH"
        if row["close"] > row["ema200"]:
            return "BULLISH"
        return "BEARISH"

    def support_resistance(self, df):
        recent = df.tail(120)
        supports, resistances = [], []

        for i in range(2, len(recent)-2):
            low = recent.iloc[i]["low"]
            high = recent.iloc[i]["high"]

            if low < recent.iloc[i-1]["low"] and low < recent.iloc[i+1]["low"]:
                supports.append(round(float(low), 2))

            if high > recent.iloc[i-1]["high"] and high > recent.iloc[i+1]["high"]:
                resistances.append(round(float(high), 2))

        return {
            "supports": sorted(list(set(supports)))[-5:],
            "resistances": sorted(list(set(resistances)))[-5:]
        }

    def analyze(self, symbol, interval="1day"):
        df = self.add_indicators(self.get_time_series(symbol, interval))
        latest = df.iloc[-1]
        sr = self.support_resistance(df)

        price = safe_number(latest["close"])
        atr = max(safe_number(latest["atr"], 1), 1)

        if self.trend(latest) in ["BULLISH", "STRONG_BULLISH"]:
            trade_type = "LONG"
            stop_loss = price - atr
            target_1 = price + atr * 2
            target_2 = price + atr * 4
        else:
            trade_type = "SHORT"
            stop_loss = price + atr
            target_1 = price - atr * 2
            target_2 = price - atr * 4

        return {
            "symbol": symbol,
            "interval": interval,
            "price": price,
            "trend": self.trend(latest),
            "trade_type": trade_type,
            "entry": price,
            "stop_loss": round(stop_loss, 2),
            "target_1": round(target_1, 2),
            "target_2": round(target_2, 2),
            "ema20": safe_number(latest["ema20"]),
            "ema50": safe_number(latest["ema50"]),
            "ema200": safe_number(latest["ema200"]),
            "rsi": safe_number(latest["rsi"]),
            "adx": safe_number(latest["adx"]),
            "atr": safe_number(latest["atr"]),
            "rvol": safe_number(latest["rvol"]),
            "supports": sr["supports"],
            "resistances": sr["resistances"]
        }

    def multi_timeframe_analysis(self, symbol):
        normalized = self.normalize_symbol(symbol)
        tfs = ["1h","4h","1day"] if normalized.endswith(".NS") else ["15min","1h","4h","1day"]
        return {tf: self.analyze(symbol, tf) for tf in tfs}

_service = TwelveDataService()

def get_time_series(symbol, interval="1day"):
    return _service.get_time_series(symbol, interval)

def analyze(symbol, interval="1day"):
    return _service.analyze(symbol, interval)

def multi_timeframe_analysis(symbol):
    return _service.multi_timeframe_analysis(symbol)
