import os
import pandas as pd
import numpy as np

from tradingagents.logging import get_logger

# sklearn is an optional dependency (used for TSF calculation)
try:
    from sklearn.linear_model import LinearRegression
    _sklearn_available = True
except ImportError:
    LinearRegression = None
    _sklearn_available = False
    get_logger(__name__).warning("scikit-learn not installed. TSF indicators will return NaN.")

logger = get_logger(__name__)

# Graceful TA-Lib availability check
try:
    import talib
    _ta_available = True
except ImportError:
    _ta_available = False
    logger.warning("TA-Lib not installed. Candlestick patterns and TA-Lib indicators unavailable.")

STOCKSTATS_TO_TALIB = {
    "close_50_sma": "SMA50",
    "close_200_sma": "SMA200",
    "close_10_ema": "EMA10",
    "macd": "outMACD",
    "macds": "outMACDSignal",
    "macdh": "outMACDHist",
    "rsi": "RSI14",
    "boll": "BBANDSMIDDLE",
    "boll_ub": "BBANDSUPPER",
    "boll_lb": "BBANDSLOWER",
    "atr": "ATR14",
    "vwma": "VWMA",
}


class FeatureCalculator:
    """Calculates technical indicators for stock data."""

    patterns = [
        "CDL2CROWS",
        "CDL3BLACKCROWS",
        "CDL3INSIDE",
        "CDL3LINESTRIKE",
        "CDL3OUTSIDE",
        "CDL3STARSINSOUTH",
        "CDL3WHITESOLDIERS",
        "CDLABANDONEDBABY",
        "CDLADVANCEBLOCK",
        "CDLBELTHOLD",
        "CDLBREAKAWAY",
        "CDLCLOSINGMARUBOZU",
        "CDLCONCEALBABYSWALL",
        "CDLCOUNTERATTACK",
        "CDLDARKCLOUDCOVER",
        "CDLDOJI",
        "CDLDOJISTAR",
        "CDLDRAGONFLYDOJI",
        "CDLENGULFING",
        "CDLEVENINGDOJISTAR",
        "CDLEVENINGSTAR",
        "CDLGAPSIDESIDEWHITE",
        "CDLGRAVESTONEDOJI",
        "CDLHAMMER",
        "CDLHANGINGMAN",
        "CDLHARAMI",
        "CDLHARAMICROSS",
        "CDLHIGHWAVE",
        "CDLHIKKAKE",
        "CDLHIKKAKEMOD",
        "CDLHOMINGPIGEON",
        "CDLIDENTICAL3CROWS",
        "CDLINNECK",
        "CDLINVERTEDHAMMER",
        "CDLKICKING",
        "CDLKICKINGBYLENGTH",
        "CDLLADDERBOTTOM",
        "CDLLONGLEGGEDDOJI",
        "CDLLONGLINE",
        "CDLMARUBOZU",
        "CDLMATCHINGLOW",
        "CDLMATHOLD",
        "CDLMORNINGDOJISTAR",
        "CDLMORNINGSTAR",
        "CDLONNECK",
        "CDLPIERCING",
        "CDLRICKSHAWMAN",
        "CDLRISEFALL3METHODS",
        "CDLSEPARATINGLINES",
        "CDLSHOOTINGSTAR",
        "CDLSHORTLINE",
        "CDLSPINNINGTOP",
        "CDLSTALLEDPATTERN",
        "CDLSTICKSANDWICH",
        "CDLTAKURI",
        "CDLTASUKIGAP",
        "CDLTHRUSTING",
        "CDLTRISTAR",
        "CDLUNIQUE3RIVER",
        "CDLUPSIDEGAP2CROWS",
        "CDLXSIDEGAP3METHODS",
    ]
    original_features = [
        # Original features
        "OBV",
        "RSI6",
        "RSI12",
        "RSI14",
        "SMA3",
        "EMA6",
        "EMA12",
        "ATR14",
        "MFI14",
        "ADX14",
        "ADX20",
        "MOM1",
        "MOM3",
        "CCI12",
        "CCI20",
        "ROCR3",
        "ROCR12",
        "outMACD",
        "outMACDSignal",
        "outMACDHist",
        "WILLR",
        "TSF10",
        "TSF20",
        "TRIX",
        "BBANDSUPPER",
        "BBANDSMIDDLE",
        "BBANDSLOWER",
        "DONCHIAN_LOWER",
        "DONCHIAN_UPPER",
        "DONCHIAN_MIDDLE",
        "VIX",
    ]

    def __init__(self, data):
        """Initializes the calculator with stock data.

        Args:
            data (pd.DataFrame): DataFrame with columns like 'Open', 'High', 'Low', 'Close', 'Volume'.
                                 Index should be datetime.
        """
        self._date_column = "date"
        self._open_column = "open"  # Added for candlestick patterns
        self._close_column = "close"
        self._high_column = "high"
        self._low_column = "low"
        self._volume_column = "volume"
        self._required_cols = ["open", "high", "low", "close", "volume"]
        self.potential_features = (
            self.original_features + self.patterns
        )  # Append new features

        # Convert column names to lowercase
        data.columns = data.columns.str.lower()

        if not isinstance(data.index, pd.DatetimeIndex):
            data[self._date_column] = pd.to_datetime(data[self._date_column], utc=True)
            data.set_index(self._date_column, inplace=True)
            data.sort_index(inplace=True)
        self.data = data.copy()
        # Ensure required columns are present

        if not all(col in self.data.columns for col in self._required_cols):
            raise ValueError(f"Input data must contain columns: {self._required_cols}")

    def _calculate_tsf(self, period):
        """Calculates the Time Series Forecast (Linear Regression)."""
        if not _sklearn_available:
            return pd.Series([np.nan] * len(self.data), index=self.data.index)

        tsf = [np.nan] * (period - 1)
        model = LinearRegression()
        prices = self.data[self._close_column].values
        for i in range(period - 1, len(prices)):
            x = np.arange(period).reshape(-1, 1)
            y = prices[i - period + 1 : i + 1]
            model.fit(x, y)
            # Predict the next point (at index period)
            prediction = model.predict(np.array([[period]]))[0]
            tsf.append(prediction)
        return pd.Series(tsf, index=self.data.index)

    def _calculate_candlestick_patterns(self):
        """Calculates the specified TA-Lib candlestick patterns."""
        if not _ta_available:
            raise RuntimeError("TA-Lib not available")

        open_col = self.data[self._open_column]
        high_col = self.data[self._high_column]
        low_col = self.data[self._low_column]
        close_col = self.data[self._close_column]

        # Collect all pattern results in a dictionary to avoid fragmentation
        pattern_results = {}
        for pattern in self.patterns:
            pattern_func = getattr(talib, pattern)
            pattern_results[pattern] = pattern_func(
                open_col, high_col, low_col, close_col
            )

        # Add all patterns at once using pd.concat to avoid fragmentation
        if pattern_results:
            pattern_df = pd.DataFrame(pattern_results, index=self.data.index)
            self.data = pd.concat([self.data, pattern_df], axis=1)

    def _add_vix_data(self, vix_path=None):
        """Loads VIX data and adds close price as a feature to self.data.
        Args:
            vix_path (str, optional): Path to VIX CSV file.
                                     Defaults to data/global/^VIX_5Y_1D.csv relative to project root.
        """
        if vix_path is None:
            # Get project root (3 levels up from this file)
            project_root = os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            )
            vix_path = os.path.join(project_root, "data", "global", "^VIX_5Y_1D.csv")

        try:
            # Load VIX data
            vix_df = pd.read_csv(vix_path)
            vix_df.columns = vix_df.columns.str.lower()

            # Convert date column to datetime and set as index
            if "date" in vix_df.columns:
                vix_df["date"] = pd.to_datetime(vix_df["date"], utc=True)
                vix_df.set_index("date", inplace=True)

            # Extract close column and rename
            if "close" in vix_df.columns:
                vix_close = vix_df[["close"]].rename(columns={"close": "VIX"})

                # Merge with self.data on index (date), using left join to keep all stock data
                self.data = self.data.join(vix_close, how="left")

                # Forward fill NaN values in case of missing VIX data for some dates
                self.data["VIX"] = self.data["VIX"].ffill()

                logger.info(f"VIX data added successfully from {vix_path}")
            else:
                logger.warning(f"'close' column not found in VIX data at {vix_path}")

        except FileNotFoundError:
            logger.warning(
                f"VIX data file not found at {vix_path}. Skipping VIX feature."
            )
        except Exception as e:
            logger.error(f"Error loading VIX data: {e}")

    def calculate_features(self):
        """Calculates all required technical indicators and adds them to the DataFrame."""
        if not _ta_available:
            raise RuntimeError("TA-Lib not available")

        close = self.data[self._close_column].values.astype(np.float64)
        high = self.data[self._high_column].values.astype(np.float64)
        low = self.data[self._low_column].values.astype(np.float64)
        volume = self.data[self._volume_column].values.astype(np.float64)
        index = self.data.index
        # Price change - Using ROCR (Rate of Change Ratio) and MOM (Momentum) from TA-Lib
        # ROCR: (Price(t)/Price(t-n)) * 100
        self.data["ROCR3"] = pd.Series(talib.ROCR(close, timeperiod=3), index=index)
        self.data["ROCR12"] = pd.Series(talib.ROCR(close, timeperiod=12), index=index)
        # MOM: Price(t) - Price(t-n)
        self.data["MOM1"] = pd.Series(talib.MOM(close, timeperiod=1), index=index)
        self.data["MOM3"] = pd.Series(talib.MOM(close, timeperiod=3), index=index)

        # Stock trend discovery - Using ADX and MFI from TA-Lib
        # ADX: Average Directional Movement Index
        self.data["ADX14"] = pd.Series(
            talib.ADX(high, low, close, timeperiod=14), index=index
        )
        self.data["ADX20"] = pd.Series(
            talib.ADX(high, low, close, timeperiod=20), index=index
        )
        # MFI: Money Flow Index
        self.data["MFI14"] = pd.Series(
            talib.MFI(high, low, close, volume, timeperiod=14), index=index
        )

        # Buy&Sell signals - Using WILLR, RSI, CCI, MACD from TA-Lib
        # WILLR: Williams' %R. TA-Lib uses 14 as default, consistent with paper's 14/10 note
        self.data["WILLR"] = pd.Series(
            talib.WILLR(high, low, close, timeperiod=14), index=index
        )
        # RSI: Relative Strength Index
        self.data["RSI6"] = pd.Series(talib.RSI(close, timeperiod=6), index=index)
        self.data["RSI12"] = pd.Series(talib.RSI(close, timeperiod=12), index=index)
        self.data["RSI14"] = pd.Series(talib.RSI(close, timeperiod=14), index=index)
        # CCI: Commodity Channel Index
        self.data["CCI12"] = pd.Series(
            talib.CCI(high, low, close, timeperiod=12), index=index
        )
        self.data["CCI20"] = pd.Series(
            talib.CCI(high, low, close, timeperiod=20), index=index
        )
        # MACD: Moving Average Convergence/Divergence. Default fast=12, slow=26, signal=9.
        macd_out, macdsignal_out, macdhist_out = talib.MACD(
            close, fastperiod=12, slowperiod=26, signalperiod=9
        )
        self.data["outMACD"] = pd.Series(macd_out, index=index)
        self.data["outMACDSignal"] = pd.Series(macdsignal_out, index=index)
        self.data["outMACDHist"] = pd.Series(macdhist_out, index=index)

        # Volatility signal - Using ATR from TA-Lib
        self.data["ATR14"] = pd.Series(
            talib.ATR(high, low, close, timeperiod=14), index=index
        )

        # Volume weights - Using OBV from TA-Lib
        self.data["OBV"] = pd.Series(talib.OBV(close, volume), index=index)

        # Noise elimination and data smoothing - Using TRIX, SMA, EMA from TA-Lib
        # TRIX: Triple Exponential Moving Average
        self.data["TRIX"] = pd.Series(
            talib.TRIX(close, timeperiod=15), index=index
        )  # Default period 15
        # SMA: Simple Moving Average
        self.data["SMA3"] = pd.Series(talib.SMA(close, timeperiod=3), index=index)
        # EMA: Exponential Moving Average
        self.data["EMA6"] = pd.Series(talib.EMA(close, timeperiod=6), index=index)
        self.data["EMA12"] = pd.Series(talib.EMA(close, timeperiod=12), index=index)

        # Bollinger Bands - Using BBANDS from TA-Lib
        # Default timeperiod=20, nbdevup=2, nbdevdn=2, matype=0 (SMA)
        upper, middle, lower = talib.BBANDS(
            close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0
        )
        self.data["BBANDSUPPER"] = pd.Series(upper, index=index)
        self.data["BBANDSMIDDLE"] = pd.Series(middle, index=index)
        self.data["BBANDSLOWER"] = pd.Series(lower, index=index)

        # Time Series Forecast (Linear Regression)
        self.data["TSF10"] = self._calculate_tsf(period=10)
        self.data["TSF20"] = self._calculate_tsf(period=20)

        # Donchian Channel
        upper_period = 20
        lower_period = 20
        self.data["DONCHIAN_UPPER"] = (
            self.data[self._high_column].rolling(window=upper_period).max()
        )
        self.data["DONCHIAN_LOWER"] = (
            self.data[self._low_column].rolling(window=lower_period).min()
        )
        self.data["DONCHIAN_MIDDLE"] = (
            self.data["DONCHIAN_UPPER"] + self.data["DONCHIAN_LOWER"]
        ) / 2

        # Drop rows with NaN values created by indicator calculations
        self.data.dropna(inplace=True)

        # Add VIX data
        # self._add_vix_data()

        # Candlestick Patterns
        # self._calculate_candlestick_patterns()

        return self.data
