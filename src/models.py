from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os
if os.environ.get("DATABASE_URL"):
    DATABASE_URL = os.environ["DATABASE_URL"]  
else:
    DATABASE_URL = "sqlite:///./trades.db"  

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelo de FailedTrade
class FailedTrade(Base):
    __tablename__ = "failed_trades"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True)
    signal = Column(Integer)
    trade_type = Column(String)
    reason = Column(String)
    entry_price = Column(Float)

# Modelo de Trade
class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True)
    signal = Column(Integer)
    trade_type = Column(String)
    success = Column(Integer)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)

# Crear las tablas en la base de datos
Base.metadata.create_all(bind=engine)




def log_trade(signal, trade_type, success, entry_price, exit_price=None):
    db = SessionLocal()
    trade_entry = Trade(
        timestamp=datetime.now(),
        signal=signal,
        trade_type=trade_type,
        success=success,
        entry_price=entry_price,
        exit_price=exit_price,
    )
    db.add(trade_entry)
    db.commit()
    db.refresh(trade_entry)
    db.close()


def log_failed_trade(signal, trade_type, reason, entry_price):
    db = SessionLocal()
    failed_trade_entry = FailedTrade(
        timestamp=datetime.now(),
        signal=signal,
        trade_type=trade_type,
        reason=reason,
        entry_price=entry_price,
    )
    db.add(failed_trade_entry)
    db.commit()
    db.refresh(failed_trade_entry)
    db.close()