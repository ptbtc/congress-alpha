#!/usr/bin/env python3
"""
Price Fetcher — Downloads stock prices for all trades and benchmarks.
Uses yfinance to get historical price data for:
- Trade date (T+0)
- Disclosure date
- T+30, T+60, T+90 after disclosure
- SPY benchmark on all dates

Handles delisted tickers, missing data, and weekends/holidays gracefully.
"""

import json
import sys
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA_DIR = Path("/home/pete/.openclaw/workspace-opus/research/congress-alpha/data")

# Lag periods (business days after disclosure)
LAG_DAYS = [0, 30, 60, 90]

def nearest_trading_day(date_str, prices_df, direction="forward"):
    """Find nearest trading day in price data."""
    target = pd.Timestamp(date_str)
    # Match timezone awareness of the index
    if prices_df.index.tz is not None:
        target = target.tz_localize(prices_df.index.tz)
    elif target.tz is not None:
        target = target.tz_localize(None)

    if target in prices_df.index:
        return target

    if direction == "forward":
        future = prices_df.index[prices_df.index >= target]
        return future[0] if len(future) > 0 else None
    else:
        past = prices_df.index[prices_df.index <= target]
        return past[-1] if len(past) > 0 else None


def fetch_prices_for_ticker(ticker, start_date, end_date, max_retries=3):
    """Fetch price history for a ticker with retry logic."""
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(ticker)
            # Add buffer around dates
            start = (pd.Timestamp(start_date) - timedelta(days=10)).strftime("%Y-%m-%d")
            end = (pd.Timestamp(end_date) + timedelta(days=10)).strftime("%Y-%m-%d")
            hist = stock.history(start=start, end=end, auto_adjust=True)
            if len(hist) > 0:
                return hist
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  ERROR fetching {ticker}: {e}")
                return None


def get_price_on_date(prices_df, date_str):
    """Get closing price on or near a specific date."""
    if prices_df is None or len(prices_df) == 0:
        return None
    nearest = nearest_trading_day(date_str, prices_df, direction="forward")
    if nearest is None:
        nearest = nearest_trading_day(date_str, prices_df, direction="backward")
    if nearest is not None:
        return float(prices_df.loc[nearest, "Close"])
    return None


def process_trades():
    """Main pipeline: load trades, fetch prices, calculate returns."""
    # Load raw trades
    with open(DATA_DIR / "raw_trades.json") as f:
        trades = json.load(f)

    # Collect all unique tickers + SPY
    tickers = list(set(t["ticker"] for t in trades)) + ["SPY"]

    # Determine date range needed
    all_dates = [t["trade_date"] for t in trades] + [t["disclosure_date"] for t in trades]
    min_date = min(all_dates)
    max_date = max(all_dates)
    # Extend end date by 120 days for lag calculations
    end_date = (pd.Timestamp(max_date) + timedelta(days=120)).strftime("%Y-%m-%d")

    print(f"Fetching prices for {len(tickers)} tickers ({min_date} to {end_date})")

    # Fetch all price data (batch by ticker to be efficient)
    price_cache = {}
    failed_tickers = []

    for i, ticker in enumerate(tickers):
        print(f"  [{i+1}/{len(tickers)}] {ticker}...", end=" ", flush=True)
        prices = fetch_prices_for_ticker(ticker, min_date, end_date)
        if prices is not None and len(prices) > 0:
            price_cache[ticker] = prices
            print(f"OK ({len(prices)} days)")
        else:
            failed_tickers.append(ticker)
            print("FAILED")
        # Rate limiting
        time.sleep(0.3)

    print(f"\nPrice data: {len(price_cache)}/{len(tickers)} tickers successful")
    if failed_tickers:
        print(f"Failed tickers: {failed_tickers}")

    # Get SPY prices for benchmark
    spy_prices = price_cache.get("SPY")
    if spy_prices is None:
        print("CRITICAL: Could not fetch SPY data. Aborting.")
        sys.exit(1)

    # Enrich each trade with price data
    enriched = []
    skipped = 0

    for trade in trades:
        ticker = trade["ticker"]
        if ticker not in price_cache:
            skipped += 1
            continue

        prices = price_cache[ticker]
        trade_date = trade["trade_date"]
        disclosure_date = trade["disclosure_date"]

        # Get prices at key dates
        price_trade = get_price_on_date(prices, trade_date)
        price_disclosure = get_price_on_date(prices, disclosure_date)

        spy_trade = get_price_on_date(spy_prices, trade_date)
        spy_disclosure = get_price_on_date(spy_prices, disclosure_date)

        if price_trade is None or spy_trade is None:
            skipped += 1
            continue

        row = {
            "trader": trade["trader"],
            "party": trade["party"],
            "chamber": trade["chamber"],
            "ticker": ticker,
            "company": trade["company"],
            "trade_type": trade["trade_type"],
            "trade_date": trade_date,
            "disclosure_date": disclosure_date,
            "amount_range": trade["amount_range"],
            "amount_est": trade["amount_est"],
            "sector": trade["sector"],
            "committee": trade.get("committee", "Unknown"),
            "source": trade.get("source", ""),
            "price_trade_date": round(price_trade, 2),
            "price_disclosure_date": round(price_disclosure, 2) if price_disclosure else None,
            "spy_trade_date": round(spy_trade, 2),
            "spy_disclosure_date": round(spy_disclosure, 2) if spy_disclosure else None,
        }

        # Calculate return from trade date to disclosure date
        if price_disclosure and price_trade:
            row["return_to_disclosure"] = round((price_disclosure / price_trade - 1) * 100, 2)
            if spy_disclosure and spy_trade:
                spy_ret = (spy_disclosure / spy_trade - 1) * 100
                row["excess_return_to_disclosure"] = round(row["return_to_disclosure"] - spy_ret, 2)
            else:
                row["excess_return_to_disclosure"] = None
        else:
            row["return_to_disclosure"] = None
            row["excess_return_to_disclosure"] = None

        # Calculate returns at each lag period after disclosure
        for lag in LAG_DAYS:
            lag_date = (pd.Timestamp(disclosure_date) + timedelta(days=lag)).strftime("%Y-%m-%d")
            price_lag = get_price_on_date(prices, lag_date)
            spy_lag = get_price_on_date(spy_prices, lag_date)

            if price_lag and price_trade:
                stock_ret = (price_lag / price_trade - 1) * 100
                row[f"return_lag_{lag}d"] = round(stock_ret, 2)
                if spy_lag and spy_trade:
                    spy_ret = (spy_lag / spy_trade - 1) * 100
                    row[f"excess_return_lag_{lag}d"] = round(stock_ret - spy_ret, 2)
                else:
                    row[f"excess_return_lag_{lag}d"] = None
            else:
                row[f"return_lag_{lag}d"] = None
                row[f"excess_return_lag_{lag}d"] = None

            # Also calculate return from DISCLOSURE date (i.e., if you copy on disclosure)
            if price_lag and price_disclosure:
                copy_ret = (price_lag / price_disclosure - 1) * 100
                row[f"copy_return_lag_{lag}d"] = round(copy_ret, 2)
                if spy_lag and spy_disclosure:
                    spy_copy_ret = (spy_lag / spy_disclosure - 1) * 100
                    row[f"copy_excess_lag_{lag}d"] = round(copy_ret - spy_copy_ret, 2)
                else:
                    row[f"copy_excess_lag_{lag}d"] = None
            else:
                row[f"copy_return_lag_{lag}d"] = None
                row[f"copy_excess_lag_{lag}d"] = None

        enriched.append(row)

    # Save enriched trades
    df = pd.DataFrame(enriched)
    output_path = DATA_DIR / "trades_enriched.csv"
    df.to_csv(output_path, index=False)

    print(f"\nEnriched {len(enriched)} trades (skipped {skipped} due to missing data)")
    print(f"Saved to {output_path}")

    # Also save failed tickers list
    with open(DATA_DIR / "failed_tickers.json", "w") as f:
        json.dump(failed_tickers, f)

    return df


if __name__ == "__main__":
    df = process_trades()
    print(f"\nDataset shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
