import unittest
from datetime import datetime, timedelta
import pandas as pd
from core.validator import validate_ohlcv_dataframe, DataValidationError
from providers.local_eod_provider import LocalCSVDataProvider


class TestPhase1DataValidation(unittest.TestCase):

    def setUp(self):
        base_time = datetime(2026, 1, 15, 9, 15)
        self.valid_data = pd.DataFrame([
            {"timestamp": base_time, "open": 500.0, "high": 505.0, "low": 498.0, "close": 502.0, "volume": 1000},
            {"timestamp": base_time + timedelta(minutes=1), "open": 502.0, "high": 504.0, "low": 501.0, "close": 503.0, "volume": 1200},
            {"timestamp": base_time + timedelta(minutes=2), "open": 503.0, "high": 506.0, "low": 502.5, "close": 505.5, "volume": 800},
        ])

    def test_valid_dataframe_passes(self):
        result = validate_ohlcv_dataframe(self.valid_data, "RELIANCE")
        self.assertEqual(len(result), 3)

    def test_high_lower_than_low_raises(self):
        corrupt = self.valid_data.copy()
        corrupt.loc[1, "high"] = 490.0  # Invalid: High < Low
        with self.assertRaises(DataValidationError):
            validate_ohlcv_dataframe(corrupt, "RELIANCE")

    def test_unsorted_timestamps_raise_leakage_error(self):
        corrupt = self.valid_data.copy()
        # Invert chronological order
        corrupt = corrupt.iloc[::-1].reset_index(drop=True)
        with self.assertRaises(DataValidationError):
            validate_ohlcv_dataframe(corrupt, "RELIANCE")

    def test_duplicate_timestamps_raise_error(self):
        corrupt = pd.concat([self.valid_data, self.valid_data.iloc[[0]]]).reset_index(drop=True)
        corrupt = corrupt.sort_values("timestamp")
        with self.assertRaises(DataValidationError):
            validate_ohlcv_dataframe(corrupt, "RELIANCE")

    def test_local_provider_retrieval(self):
        provider = LocalCSVDataProvider()
        provider.load_fixture("TCS", self.valid_data)
        
        start = datetime(2026, 1, 15, 9, 15)
        end = datetime(2026, 1, 15, 9, 16)
        res = provider.get_candles("TCS", start, end)
        self.assertEqual(len(res), 2)
        
        quote = provider.get_quote("TCS")
        self.assertEqual(quote["last_price"], 505.5)


if __name__ == "__main__":
    unittest.main()