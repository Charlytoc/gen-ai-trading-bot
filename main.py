from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine

import os
import uvicorn
import pandas as pd

from apscheduler.schedulers.blocking import BlockingScheduler


from dotenv import load_dotenv
from threading import Thread  
from src.models import Trade, FailedTrade, SessionLocal
from src.trade_logic import trading_job

load_dotenv()

app = FastAPI()

if os.environ.get("DATABASE_URL"):
    DATABASE_URL = os.environ["DATABASE_URL"]  # Use Heroku's PostgreSQL URL
else:
    DATABASE_URL = "sqlite:///./trades.db"  # Fallback to SQLite for local development

engine = create_engine(DATABASE_URL)



access_token = os.environ.get("OANDA_API_KEY")
accountID = os.environ.get("OANDA_ACCOUNT_ID")
units = int(os.getenv('TRADE_UNITS', 3000)) 




@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    db = SessionLocal()
    
    # Query successful trades
    trades_operations = db.query(Trade).all()
    trades_df = pd.DataFrame(
        [
            {
                "timestamp": trade.timestamp,
                "signal": trade.signal,
                "trade_type": trade.trade_type,
                "success": trade.success,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
            }
            for trade in trades_operations
        ]
    )

    # Query failed trades
    failed_trades = db.query(FailedTrade).all()
    failed_trades_df = pd.DataFrame(
        [
            {
                "timestamp": failed_trade.timestamp,
                "signal": failed_trade.signal,
                "trade_type": failed_trade.trade_type,
                "reason": failed_trade.reason,
                "entry_price": failed_trade.entry_price,
            }
            for failed_trade in failed_trades
        ]
    )

    # Load the Jinja template
    with open("templates/dashboard.html", "r") as file:
        template = file.read()

    # Convert DataFrames to HTML
    trades_html = trades_df.to_html(index=False)
    failed_trades_html = failed_trades_df.to_html(index=False)

    # Replace placeholders in the template
    template = template.replace("{{successful_trades}}", trades_html)
    template = template.replace("{{failed_trades}}", failed_trades_html)

    db.close()
    return template





# def start_scheduler():
#     print("Running scheduler")
#     scheduler = BlockingScheduler()
#     scheduler.add_job(
#         trading_job,
#         "cron",
#         day_of_week="mon-fri",
#         hour="00-23",
#         minute="1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56",
#         start_date="2023-12-08 12:00:00",
#         timezone="America/Chicago",
#     )
#     scheduler.start()


if __name__ == "__main__":

    # scheduler_thread = Thread(target=start_scheduler)
    # scheduler_thread.start()

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
