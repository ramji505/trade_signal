from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(32), unique=True, nullable=False)
    exchange = Column(String(16), default="NSE")
    lot_size = Column(Integer, default=50)
    active = Column(Boolean, default=True)


class Candle(Base):
    __tablename__ = "candles"

    id = Column(Integer, primary_key=True, index=True)
    instrument_symbol = Column(String(32), index=True, nullable=False)
    timeframe = Column(String(8), index=True, nullable=False)  # 1m, 3m, 5m, 10m, 15m
    timestamp = Column(DateTime, index=True, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    vwap = Column(Float, nullable=True)


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(String(64), unique=True, index=True, nullable=False)
    symbol = Column(String(32), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    direction = Column(String(8), nullable=False)  # BUY, SELL, WAIT
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    target_1 = Column(Float, nullable=True)
    target_2 = Column(Float, nullable=True)
    score = Column(Integer, nullable=False)
    timeframe = Column(String(8), default="5m")
    market_regime = Column(String(32), nullable=False)
    status = Column(String(32), default="ACTIVE")  # ACTIVE, TARGET_HIT, STOP_HIT, TIMEOUT
    strategy_version = Column(String(16), default="v1.0")
    indicators_snapshot = Column(JSON, nullable=True)


class SignalEvaluation(Base):
    __tablename__ = "signal_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(String(64), ForeignKey("signals.signal_id"), nullable=False)
    horizon_minutes = Column(Integer, nullable=False)  # 1, 3, 5, 10, 15, 20
    evaluated_at = Column(DateTime, default=datetime.utcnow)
    exit_price = Column(Float, nullable=True)
    mfe = Column(Float, nullable=True)  # Max Favorable Excursion
    mae = Column(Float, nullable=True)  # Max Adverse Excursion
    result = Column(String(32), nullable=False)  # TARGET_HIT, STOP_HIT, NO_DECISIVE_MOVE, TIMEOUT
    points_pnl = Column(Float, nullable=True)
