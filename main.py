from fastapi import FastAPI, HTTPException
from services.twelvedata import (
    get_time_series,
    analyze,
    multi_timeframe_analysis
)

import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Trading GPT API",
    version="2.0.0",
    description="Institutional Trading Analysis API"
)


@app.get("/")
def root():
    return {
        "status": "running",
        "name": "Trading GPT API",
        "version": "2.0.0"
    }


@app.get("/candles")
def candles(symbol: str, interval: str = "1h"):
    try:
        df = get_time_series(symbol=symbol, interval=interval)

        if hasattr(df, "to_dict"):
            return {
                "symbol": symbol,
                "interval": interval,
                "rows": len(df),
                "data": df.tail(100).to_dict(orient="records")
            }

        return df

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analyze")
def analyze_endpoint(symbol: str, interval: str = "1h"):
    try:
        return analyze(symbol=symbol, interval=interval)

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/multi-timeframe")
def multi_timeframe(symbol: str):
    try:
        return multi_timeframe_analysis(symbol=symbol)

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/symbol-search")
def symbol_search(symbol: str):

    response = requests.get(
        "https://api.twelvedata.com/symbol_search",
        params={
            "symbol": symbol,
            "apikey": os.getenv("TWELVEDATA_API_KEY")
        },
        timeout=30
    )

    return response.json()


@app.get("/test")
def test():

    response = requests.get(
        "https://api.twelvedata.com/time_series",
        params={
            "symbol": "AAPL",
            "interval": "1day",
            "outputsize": 10,
            "apikey": os.getenv("TWELVEDATA_API_KEY")
        },
        timeout=30
    )

    return response.json()


@app.get("/health")
def health():
    return {"status": "healthy"}
