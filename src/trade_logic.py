from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import pandas as pd
import os
import pandas_ta as ta
from apscheduler.schedulers.blocking import BlockingScheduler
import uvicorn
from oandapyV20 import API
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
from oandapyV20.contrib.requests import MarketOrderRequest
from oanda_candles import Pair, Gran, CandleClient


access_token = os.environ.get("OANDA_API_KEY")
accountID = os.environ.get("OANDA_ACCOUNT_ID")


def ema_signal(df, current_candle, backcandles):
    df_slice = df.reset_index().copy()
    # Get the range of candles to consider
    start = max(0, current_candle - backcandles)
    end = current_candle
    relevant_rows = df_slice.iloc[start:end]

    # Check if all EMA_fast values are below EMA_slow values
    if all(relevant_rows["EMA_fast"] < relevant_rows["EMA_slow"]):
        return 1
    elif all(relevant_rows["EMA_fast"] > relevant_rows["EMA_slow"]):
        return 2
    else:
        return 0


def total_signal(df, current_candle, backcandles):
    if (
        ema_signal(df, current_candle, backcandles) == 2
        and df.Close[current_candle] <= df["BBL_15_1.5"][current_candle]
        # and df.RSI[current_candle]<60
    ):
        return 2
    if (
        ema_signal(df, current_candle, backcandles) == 1
        and df.Close[current_candle] >= df["BBU_15_1.5"][current_candle]
        # and df.RSI[current_candle]>40
    ):

        return 1
    return 0




def get_candles(n):
    client = CandleClient(access_token, real=False)
    collector = client.get_collector(Pair.EUR_USD, Gran.M5)
    candles = collector.grab(n)
    return candles


# candles = get_candles(3)
# for candle in candles:
#     print(float(str(candle.bid.o))>1)
#     print(candle)


def count_opened_trades():
    client = API(access_token=access_token)
    r = trades.OpenTrades(accountID=accountID)
    client.request(r)
    return len(r.response["trades"])


def get_candles_frame(n):
    candles = get_candles(n)
    dfstream = pd.DataFrame(columns=["Open", "Close", "High", "Low"])

    i = 0
    for candle in candles:
        dfstream.loc[i, ["Open"]] = float(str(candle.bid.o))
        dfstream.loc[i, ["Close"]] = float(str(candle.bid.c))
        dfstream.loc[i, ["High"]] = float(str(candle.bid.h))
        dfstream.loc[i, ["Low"]] = float(str(candle.bid.l))
        i = i + 1

    dfstream["Open"] = dfstream["Open"].astype(float)
    dfstream["Close"] = dfstream["Close"].astype(float)
    dfstream["High"] = dfstream["High"].astype(float)
    dfstream["Low"] = dfstream["Low"].astype(float)

    dfstream["ATR"] = ta.atr(dfstream.High, dfstream.Low, dfstream.Close, length=7)
    dfstream["EMA_fast"] = ta.ema(dfstream.Close, length=30)
    dfstream["EMA_slow"] = ta.ema(dfstream.Close, length=50)
    dfstream["RSI"] = ta.rsi(dfstream.Close, length=10)
    my_bbands = ta.bbands(dfstream.Close, length=15, std=1.5)
    dfstream = dfstream.join(my_bbands)

    # Adding MACD
    dfstream["MACD"], dfstream["MACD_signal"], dfstream["MACD_hist"] = ta.macd(
        dfstream.Close, fast=12, slow=26, signal=9
    )

    # Adding Stochastic Oscillator
    dfstream["Stoch_K"], dfstream["Stoch_D"] = ta.stoch(
        dfstream.High, dfstream.Low, dfstream.Close, fastk=14, fastd=3
    )

    return dfstream

