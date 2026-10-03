import os
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List
import upstox_client
from upstox_client.rest import ApiException
from core.interfaces import MarketDataProvider
from core.validator import validate_ohlcv_dataframe, DataValidationError


class UpstoxDataProvider(MarketDataProvider):
    """
    Historical data provider using the Upstox Developer API v2.
    Requires UPSTOX_ACCESS_TOKEN in the environment or passed during init.
    """

    def __init__(self, access_token: str = None):
        self.access_token = access_token or os.getenv("UPSTOX_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError("UPSTOX_ACCESS_TOKEN is missing. Provide it or set the env variable.")
            
        self.configuration = upstox_client.Configuration()
        self.configuration.access_token = self.access_token
        self.api_client = upstox_client.ApiClient(self.configuration)
        
        # Upstox v2 API for intraday and historical data
        self.history_api = upstox_client.HistoryApi(self.api_client)

    def _get_instrument_key(self, symbol: str, is_index: bool = False) -> str:
        """
        Maps standard symbols to Upstox internal instrument keys.
        Cash Equity: 'RELIANCE' -> 'NSE_EQ|INE002A01018'
        NIFTY 50 Index: 'NIFTY 50' -> 'NSE_INDEX|Nifty 50'
        
        Note: Upstox requires the ISIN for cash equities (NSE_EQ|ISIN).
        In production, load the daily instrument CSV to map these dynamically.
        """
        if is_index:
            if symbol.upper() == "NIFTY 50":
                return "NSE_INDEX|Nifty 50"
            elif symbol.upper() == "NIFTY BANK":
                return "NSE_INDEX|Nifty Bank"
            return f"NSE_INDEX|{symbol}"
        
        return f"NSE_EQ|{symbol}"

    def get_candles(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1minute" 
    ) -> pd.DataFrame:
        
        instrument_key = self._get_instrument_key(symbol, is_index=False)
        api_version = "2.0"
        
        try:
            # Format dates to YYYY-MM-DD
            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")

            response = self.history_api.get_historical_candle_data1(
                instrument_key, timeframe, end_str, start_str, api_version
            )
            
            if not response.data or not response.data.candles:
                return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

            # Upstox JSON format: [timestamp, open, high, low, close, volume, open_interest]
            records = []
            for candle in response.data.candles:
                records.append({
                    "timestamp": pd.to_datetime(candle[0]),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": int(candle[5])
                })

            df = pd.DataFrame(records)
            
            # Sort chronologically to prevent look-ahead bias
            df = df.sort_values("timestamp").reset_index(drop=True)
            
            # Run through the core validator before returning
            return validate_ohlcv_dataframe(df, symbol)

        except ApiException as e:
            raise RuntimeError(f"[{symbol}] Upstox API Exception: {e.body}") from e
        except DataValidationError as e:
            raise RuntimeError(f"[{symbol}] Data validation failed on Upstox payload: {e}") from e

    def get_index_candles(
        self,
        index_name: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1minute"
    ) -> pd.DataFrame:
        
        instrument_key = self._get_instrument_key(index_name, is_index=True)
        api_version = "2.0"
        
        try:
            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")

            response = self.history_api.get_historical_candle_data1(
                instrument_key, timeframe, end_str, start_str, api_version
            )
            
            if not response.data or not response.data.candles:
                return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

            records = []
            for candle in response.data.candles:
                records.append({
                    "timestamp": pd.to_datetime(candle[0]),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": int(candle[5]) if len(candle) > 5 else 0
                })

            df = pd.DataFrame(records)
            df = df.sort_values("timestamp").reset_index(drop=True)
            return validate_ohlcv_dataframe(df, index_name)

        except ApiException as e:
            raise RuntimeError(f"[{index_name}] Upstox API Exception: {e.body}") from e

    def get_quote(self, symbol: str) -> Dict[str, float]:
        """V1 placeholder. Live quotes require the MarketQuoteApi."""
        raise NotImplementedError("Live quote fetching requires MarketQuoteApi implementation.")