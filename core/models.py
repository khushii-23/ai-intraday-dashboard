from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date,
    Boolean, ForeignKey, UniqueConstraint, Index, Text
)
from core.database import Base


class Instrument(Base):
    """Universe tracking, liquidity flags, and survivorship-bias mitigation."""
    __tablename__ = "instruments"

    symbol = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=True)
    lot_size = Column(Integer, default=1, nullable=False)
    tick_size = Column(Float, default=0.05, nullable=False)
    is_delisted = Column(Boolean, default=False, nullable=False)
    is_mis_eligible = Column(Boolean, default=True, nullable=False)


class Candle1M(Base):
    """1-minute OHLCV price bars for traded stocks."""
    __tablename__ = "candles_1m"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), ForeignKey("instruments.symbol"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "timestamp", name="uix_stock_candle_timestamp"),
        Index("ix_stock_time", "symbol", "timestamp"),
    )


class IndexCandle(Base):
    """Benchmark index candles (NIFTY 50, BANK NIFTY, India VIX)."""
    __tablename__ = "index_candles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_name = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("index_name", "timestamp", name="uix_index_candle_timestamp"),
        Index("ix_index_time", "index_name", "timestamp"),
    )


class CorporateAction(Base):
    """Corporate actions to detect ex-dates and adjustment events."""
    __tablename__ = "corporate_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), ForeignKey("instruments.symbol"), nullable=False)
    action_type = Column(String(50), nullable=False)  # DIVIDEND, SPLIT, BONUS, RIGHTS
    ex_date = Column(Date, nullable=False)
    ratio = Column(String(50), nullable=True)
    remarks = Column(Text, nullable=True)


class MarketRegime(Base):
    """Point-in-time market regime classifications."""
    __tablename__ = "market_regimes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, unique=True)
    nifty_trend = Column(String(20), nullable=False)  # BULLISH, BEARISH, SIDEWAYS
    india_vix = Column(Float, nullable=True)
    breadth_pct = Column(Float, nullable=True)
    regime = Column(String(30), nullable=False)        # BULLISH, BEARISH, HIGH_VOLATILITY, NEUTRAL


class NewsItem(Base):
    """Official exchange announcements and news items."""
    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), ForeignKey("instruments.symbol"), nullable=True)
    headline = Column(Text, nullable=False)
    source = Column(String(50), nullable=False)        # NSE, BSE, RBI, SEBI
    published_at = Column(DateTime(timezone=True), nullable=False)
    ingested_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    url = Column(String(500), nullable=True)
    dedupe_hash = Column(String(64), unique=True, nullable=False)


class Prediction(Base):
    """Append-only log of model recommendations and risk evaluations."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    symbol = Column(String(50), ForeignKey("instruments.symbol"), nullable=False)
    model_version = Column(String(50), nullable=False)
    decision = Column(String(10), nullable=False)      # LONG, WAIT, NO_TRADE
    raw_probability = Column(Float, nullable=False)
    calibrated_probability = Column(Float, nullable=False)
    expected_move_pct = Column(Float, nullable=False)
    horizon_minutes = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_price = Column(Float, nullable=False)
    target_price = Column(Float, nullable=False)
    market_regime = Column(String(30), nullable=False)
    trade_quality_score = Column(Float, nullable=False)


class PredictionOutcome(Base):
    """Verification record comparing predictions against subsequent market moves."""
    __tablename__ = "prediction_outcomes"

    prediction_id = Column(Integer, ForeignKey("predictions.id"), primary_key=True)
    actual_direction = Column(String(10), nullable=False)
    hit_target_first = Column(Boolean, nullable=False)
    hit_stop_first = Column(Boolean, nullable=False)
    exit_price = Column(Float, nullable=False)
    exit_timestamp = Column(DateTime(timezone=True), nullable=False)
    gross_move_pct = Column(Float, nullable=False)


class PaperTrade(Base):
    """Simulated trade execution tracking."""
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=True)
    symbol = Column(String(50), ForeignKey("instruments.symbol"), nullable=False)
    side = Column(String(10), nullable=False)          # LONG, SHORT
    qty = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    stop_loss = Column(Float, nullable=False)
    target = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="OPEN", nullable=False)  # OPEN, TARGET_HIT, STOP_HIT, SQUARED_OFF
    gross_pnl = Column(Float, nullable=True)
    total_costs = Column(Float, nullable=True)
    net_pnl = Column(Float, nullable=True)


class RiskConfig(Base):
    """User-level risk settings and exposure caps."""
    __tablename__ = "risk_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    capital = Column(Float, default=4000.0, nullable=False)
    max_risk_per_trade_pct = Column(Float, default=0.5, nullable=False)  # 0.5% = ₹20
    max_daily_loss_pct = Column(Float, default=1.0, nullable=False)      # 1.0% = ₹40
    max_trades_per_day = Column(Integer, default=3, nullable=False)
    max_simultaneous_positions = Column(Integer, default=1, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class DailyRiskState(Base):
    """Daily trade counts, cumulative loss, and circuit breakers."""
    __tablename__ = "daily_risk_state"

    trade_date = Column(Date, primary_key=True)
    trades_executed = Column(Integer, default=0, nullable=False)
    realized_daily_pnl = Column(Float, default=0.0, nullable=False)
    is_trading_disabled = Column(Boolean, default=False, nullable=False)
    disabled_reason = Column(String(100), nullable=True)