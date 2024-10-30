
import os
import pandas as pd

import oandapyV20.endpoints.trades as trades
import pandas_ta as ta 
from oanda_candles import Pair, Gran, CandleClient
from oandapyV20 import API
import oandapyV20.endpoints.orders as orders
from oandapyV20.contrib.requests import MarketOrderRequest
from oandapyV20.contrib.requests import TakeProfitDetails, StopLossDetails

from dotenv import load_dotenv
from src.models import  log_failed_trade, log_trade

load_dotenv()


access_token = os.environ.get("OANDA_API_KEY")
accountID = os.environ.get("OANDA_ACCOUNT_ID")
units = int(os.getenv('TRADE_UNITS', 3000)) 

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
    # Temporarily disable strict condition checking for testing purposes
    ema_condition = ema_signal(df, current_candle, backcandles)

    # For buy: Allow buy signal when EMA fast crosses above EMA slow AND price is below upper band
    if ema_condition == 2 or (df.Close[current_candle] <= df["BBU_15_1.5"][current_candle]):
        return 2  # Buy signal
    
    # For sell: Allow sell signal when EMA fast crosses below EMA slow AND price is above lower band
    if ema_condition == 1 or (df.Close[current_candle] >= df["BBL_15_1.5"][current_candle]):
        return 1  # Sell signal

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


def trading_job():
    print("Running trading job")
    dfstream = get_candles_frame(70)
    signal = total_signal(dfstream, len(dfstream) - 1, 7)

    print(f"Signal received: {signal}")  # Debugging output
   
    slatr = 1.1 * dfstream.ATR.iloc[-1]
    TPSLRatio = 1.5
    max_spread = 16e-5

    candle = get_candles(1)[-1]
    candle_open_bid = float(str(candle.bid.o))
    candle_open_ask = float(str(candle.ask.o))
    
    spread = candle_open_ask - candle_open_bid
    
    print(f"Spread: {spread}, SLATR: {slatr}, Candle Open Bid: {candle_open_bid}, Candle Open Ask: {candle_open_ask}") 

    SLBuy = candle_open_bid - slatr - spread
    SLSell = candle_open_ask + slatr + spread

    TPBuy = candle_open_ask + slatr * TPSLRatio + spread
    TPSell = candle_open_bid - slatr * TPSLRatio - spread

    client = API(access_token=access_token)

    # Sell
    if signal == 1 and count_opened_trades() == 0 and spread < max_spread:
        mo = MarketOrderRequest(
            instrument="EUR_USD",
            units=-units,
            takeProfitOnFill=TakeProfitDetails(price=TPSell).data,
            stopLossOnFill=StopLossDetails(price=SLSell).data,
        )
        r = orders.OrderCreate(accountID, data=mo.data)
        rv = client.request(r)
        print(rv)
        log_trade(signal, "Sell", True, candle_open_bid)
    else:
        reason = "Conditions not met for Sell trade."
        log_failed_trade(signal, "Sell", reason, candle_open_bid)

    if signal == 2 and count_opened_trades() == 0 and spread < max_spread:
        mo = MarketOrderRequest(
            instrument="EUR_USD",
            units=units,
            takeProfitOnFill=TakeProfitDetails(price=TPBuy).data,
            stopLossOnFill=StopLossDetails(price=SLBuy).data,
        )
        r = orders.OrderCreate(accountID, data=mo.data)
        rv = client.request(r)
        print(rv)
        log_trade(signal, "Buy", True, candle_open_ask)
    else:
        reason = "Conditions not met for Buy trade."
        log_failed_trade(signal, "Buy", reason, candle_open_ask)
