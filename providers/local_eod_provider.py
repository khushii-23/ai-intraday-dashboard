from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd
from core.interfaces import MarketDataProvider
from core.validator import validate_ohlcv_dataframe


class LocalCSVDataProvider(MarketDataProvider):
    """
    File-based provider for offline plumbing and regression testing.
    Loads raw CSV data and runs it through validation.
    """

    def __init__(self, data_store: Optional[Dict[str, pd.DataFrame]] = None):
        self._data_store = data_store or {}

    def load_fixture(self, symbol: str, df: pd.DataFrame) -> None:
        """Load in-memory fixture for a symbol."""
        self._data_store[symbol] = validate_ohlcv_dataframe(df, symbol)

    def get_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1m"
    ) -> pd.DataFrame:
        if symbol not in self._data_store:
            raise ValueError(f"No fixture loaded for symbol: {symbol}")

        df = self._data_store[symbol]
        mask = (df["timestamp"] >= pd.to_datetime(start)) & (df["timestamp"] <= pd.to_datetime(end))
        filtered = df.loc[mask].copy().reset_index(drop=True)
        return filtered

    def get_index_candles(
        self,
        index_name: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1m"
    ) -> pd.DataFrame:
        return self.get_candles(index_name, start, end, timeframe)

    def get_quote(self, symbol: str) -> Dict[str, float]:
        if symbol not in self._data_store:
            raise ValueError(f"No fixture loaded for symbol: {symbol}")
        df = self._data_store[symbol]
        last_row = df.iloc[-1]
        return {
            "last_price": float(last_row["close"]),
            "volume": float(last_row["volume"]),
            "high": float(last_row["high"]),
            "low": float(last_row["low"]),
            "close": float(last_row["close"]),
        }