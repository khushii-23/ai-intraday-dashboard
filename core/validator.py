import pandas as pd


class DataValidationError(Exception):
    """Raised when incoming market data violates integrity constraints."""
    pass


def validate_ohlcv_dataframe(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Applies strict anti-leakage and financial sanity checks:
    1. Mandatory columns check
    2. Strict chronological order (no future-dated rows out of order)
    3. No duplicate timestamps
    4. Price relationship logic: Low <= Open, Close <= High
    5. Non-negative volume
    """
    required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        raise DataValidationError(f"[{symbol}] Missing mandatory columns: {missing}")

    if df.empty:
        return df

    # Enforce datetime type
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # 1. Anti-leakage / Monotonicity check
    if not df["timestamp"].is_monotonic_increasing:
        raise DataValidationError(f"[{symbol}] Timestamps are not strictly monotonically increasing")

    # 2. Duplicate check
    duplicates = df[df.duplicated(subset=["timestamp"], keep=False)]
    if not duplicates.empty:
        raise DataValidationError(f"[{symbol}] Found {len(duplicates)} duplicate timestamp bars")

    # 3. Bar integrity checks
    invalid_high_low = df[df["high"] < df["low"]]
    if not invalid_high_low.empty:
        raise DataValidationError(f"[{symbol}] High < Low detected at {invalid_high_low['timestamp'].iloc[0]}")

    invalid_open = df[(df["open"] > df["high"]) | (df["open"] < df["low"])]
    if not invalid_open.empty:
        raise DataValidationError(f"[{symbol}] Open outside High-Low range at {invalid_open['timestamp'].iloc[0]}")

    invalid_close = df[(df["close"] > df["high"]) | (df["close"] < df["low"])]
    if not invalid_close.empty:
        raise DataValidationError(f"[{symbol}] Close outside High-Low range at {invalid_close['timestamp'].iloc[0]}")

    # 4. Volume check
    negative_vol = df[df["volume"] < 0]
    if not negative_vol.empty:
        raise DataValidationError(f"[{symbol}] Negative volume detected at {negative_vol['timestamp'].iloc[0]}")

    return df