from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import pandas as pd


class MarketDataProvider(ABC):
    """
    Abstract interface for market data ingestion.
    Guarantees consistent column schema, UTC/IST timezone handling,
    and chronological ordering to prevent look-ahead bias.
    """

    @abstractmethod
    def get_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1m"
    ) -> pd.DataFrame:
        """
        Returns a DataFrame with columns:
        ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        Index must be monotonically increasing.
        """
        pass

    @abstractmethod
    def get_index_candles(
        self,
        index_name: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1m"
    ) -> pd.DataFrame:
        """Fetch benchmark index bars (e.g., NIFTY 50, INDIA VIX)."""
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Dict[str, float]:
        """Returns point-in-time snapshot: last_price, volume, high, low, close."""
        pass


class NewsProvider(ABC):
    """Abstract interface for corporate announcements and financial news."""

    @abstractmethod
    def fetch_since(
        self,
        since: datetime,
        symbols: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns list of news records with keys:
        ['symbol', 'headline', 'source', 'published_at', 'url']
        """
        pass


class BrokerProvider(ABC):
    """Abstract execution gateway. Implemented strictly as PaperBroker for v1."""

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None
    ) -> Dict[str, Any]:
        pass