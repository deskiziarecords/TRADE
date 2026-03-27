#!/usr/bin/env python3
"""
Historical Forex Data Downloader for IPDA System
Downloads OHLCV data from OANDA and stores in efficient format
"""

import os
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Optional, List, Tuple

import aiohttp
from dotenv import load_dotenv

load_dotenv('/home/rjimenez/ipda-system/config/.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)


class HistoricalDataDownloader:
    """Download historical forex data from OANDA"""
    
    def __init__(self, instrument: str = "EUR_USD"):
        self.instrument = instrument
        self.api_key = os.getenv('OANDA_API_KEY')
        self.account_id = os.getenv('OANDA_ACCOUNT_ID')
        self.base_url = "https://api-fxtrade.oanda.com/v3"
        
        # Storage paths
        self.data_dir = Path("/home/rjimenez/ipda-system/data")
        self.raw_dir = self.data_dir / "raw" / instrument.replace("/", "_")
        self.processed_dir = self.data_dir / "processed" / instrument.replace("/", "_")
        
        # Create directories
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
    async def download_candles(
        self, 
        from_date: datetime, 
        to_date: datetime, 
        granularity: str = "H1"
    ) -> pd.DataFrame:
        """
        Download candles from OANDA
        
        Granularity options:
        M1, M5, M15, M30, H1, H4, D1, W1, M1 (monthly)
        """
        all_candles = []
        current_start = from_date
        
        # OANDA limits to 5000 candles per request
        while current_start < to_date:
            params = {
                'granularity': granularity,
                'from': current_start.isoformat() + 'Z',
                'to': to_date.isoformat() + 'Z',
                'price': 'MBA'  # Mid, Bid, Ask
            }
            
            headers = {'Authorization': f'Bearer {self.api_key}'}
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/instruments/{self.instrument}/candles"
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to download: {response.status}")
                        break
                    
                    data = await response.json()
                    candles = data.get('candles', [])
                    
                    if not candles:
                        break
                    
                    for c in candles:
                        if c.get('complete', False):
                            all_candles.append({
                                'timestamp': pd.to_datetime(c['time']),
                                'open': float(c['mid']['o']),
                                'high': float(c['mid']['h']),
                                'low': float(c['mid']['l']),
                                'close': float(c['mid']['c']),
                                'volume': c.get('volume', 0)
                            })
                    
                    # Update current_start to last candle time
                    last_ts = pd.to_datetime(candles[-1]['time'])
                    current_start = last_ts + timedelta(milliseconds=1)
                    
                    logger.info(f"Downloaded {len(candles)} candles. Progress: {current_start}")
            
            # Rate limiting
            await asyncio.sleep(1)
        
        df = pd.DataFrame(all_candles)
        df.set_index('timestamp', inplace=True)
        
        # Save raw data
        raw_file = self.raw_dir / f"{self.instrument}_{granularity}_{from_date.date()}_{to_date.date()}.parquet"
        df.to_parquet(raw_file)
        logger.info(f"Saved {len(df)} candles to {raw_file}")
        
        return df
    
    def download_sync(self, from_date: datetime, to_date: datetime, granularity: str = "H1") -> pd.DataFrame:
        """Synchronous wrapper"""
        return asyncio.run(self.download_candles(from_date, to_date, granularity))
    
    def add_ipda_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add IPDA-specific indicators for your system"""
        df = df.copy()
        
        # IPDA Ranges
        df['H20'] = df['high'].rolling(20).max()
        df['L20'] = df['low'].rolling(20).min()
        df['H40'] = df['high'].rolling(40).max()
        df['L40'] = df['low'].rolling(40).min()
        df['H60'] = df['high'].rolling(60).max()
        df['L60'] = df['low'].rolling(60).min()
        
        # Equilibrium
        df['equilibrium'] = (df['H60'] + df['L60']) / 2
        
        # ATR
        tr = pd.DataFrame({
            'hl': df['high'] - df['low'],
            'hc': abs(df['high'] - df['close'].shift()),
            'lc': abs(df['low'] - df['close'].shift())
        }).max(axis=1)
        df['atr'] = tr.rolling(14).mean()
        
        # Price position within range (0-1)
        df['price_position'] = (df['close'] - df['L60']) / (df['H60'] - df['L60'])
        
        # Phase detection
        df['phase'] = 'MANIPULATION'  # default
        df.loc[df['price_position'] > 0.8, 'phase'] = 'DISTRIBUTION'
        df.loc[df['price_position'] < 0.2, 'phase'] = 'ACCUMULATION'
        
        return df
    
    def prepare_for_ipda(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare dataframe for IPDA system consumption"""
        df = self.add_ipda_indicators(df)
        
        # Drop rows with NaN (first 60 candles)
        df = df.dropna()
        
        # Save processed data
        processed_file = self.processed_dir / f"{self.instrument}_ipda_ready.parquet"
        df.to_parquet(processed_file)
        logger.info(f"Saved IPDA-ready data to {processed_file}")
        
        return df


class DataValidator:
    """Validate downloaded data for quality"""
    
    @staticmethod
    def check_gaps(df: pd.DataFrame, expected_frequency: str = 'H') -> List[Tuple]:
        """Check for missing candles"""
        freq_map = {'M': '1min', 'H': '1h', 'D': '1d', 'W': '1w'}
        expected = freq_map.get(expected_frequency, '1h')
        
        full_index = pd.date_range(start=df.index.min(), end=df.index.max(), freq=expected)
        missing = full_index.difference(df.index)
        
        if len(missing) > 0:
            logger.warning(f"Found {len(missing)} missing candles")
            return list(missing[:10])  # Return first 10
        
        logger.info("No gaps detected")
        return []
    
    @staticmethod
    def check_anomalies(df: pd.DataFrame) -> dict:
        """Check for price anomalies"""
        anomalies = {
            'zero_volume': len(df[df['volume'] == 0]),
            'negative_spread': len(df[df['low'] > df['high']]),  # shouldn't happen
            'outliers': len(df[abs(df['close'] - df['close'].mean()) > 5 * df['close'].std()])
        }
        
        for key, count in anomalies.items():
            if count > 0:
                logger.warning(f"{key}: {count} anomalies detected")
        
        return anomalies


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def main():
    """Example usage"""
    
    # Initialize downloader
    downloader = HistoricalDataDownloader(instrument="EUR_USD")
    
    # Download last 3 months of hourly data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    logger.info(f"Downloading {start_date.date()} to {end_date.date()}")
    
    # Download
    df = downloader.download_sync(start_date, end_date, granularity="H1")
    
    if len(df) > 0:
        # Validate
        validator = DataValidator()
        validator.check_gaps(df, 'H')
        validator.check_anomalies(df)
        
        # Add IPDA indicators
        ipda_df = downloader.prepare_for_ipda(df)
        
        # Display summary
        print("\n" + "="*60)
        print("DOWNLOAD SUMMARY")
        print("="*60)
        print(f"Instrument: EUR/USD")
        print(f"Period: {start_date.date()} to {end_date.date()}")
        print(f"Candles: {len(ipda_df)}")
        print(f"Date range: {ipda_df.index.min()} to {ipda_df.index.max()}")
        print(f"Current price: {ipda_df['close'].iloc[-1]:.5f}")
        print(f"Current phase: {ipda_df['phase'].iloc[-1]}")
        print(f"60-day range: {ipda_df['L60'].iloc[-1]:.5f} - {ipda_df['H60'].iloc[-1]:.5f}")
        print(f"Equilibrium: {ipda_df['equilibrium'].iloc[-1]:.5f}")
        
        # Show recent data
        print("\nRecent data:")
        print(ipda_df[['close', 'phase', 'price_position', 'atr']].tail(10))
        
        # Save summary
        summary = {
            'instrument': 'EUR_USD',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'candles': len(ipda_df),
            'last_price': ipda_df['close'].iloc[-1],
            'last_phase': ipda_df['phase'].iloc[-1],
            'h60': ipda_df['H60'].iloc[-1],
            'l60': ipda_df['L60'].iloc[-1],
            'equilibrium': ipda_df['equilibrium'].iloc[-1]
        }
        
        import json
        with open(downloader.data_dir / "metadata/latest_summary.json", 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        print("\n✅ Data ready for IPDA backtesting!")
        print(f"Files saved in: {downloader.data_dir}")


if __name__ == "__main__":
    main()
