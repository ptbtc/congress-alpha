#!/usr/bin/env python3
"""
Congressional Trade Analysis Engine
=====================================
Reads enriched trade data and produces:
- lag_analysis.csv — returns by lag period
- trader_stats.csv — per-trader performance metrics
- sector_stats.csv — per-sector metrics
- monthly_returns.csv — monthly time series
- summary_stats.json — headline numbers for dashboard

Statistical methods:
- Excess returns vs SPY benchmark
- Sharpe / Sortino ratios (annualized)
- Max drawdown, win rate, CAGR
- Two-sided t-tests for significance of excess returns
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DATA_DIR = Path("/home/pete/.openclaw/workspace-opus/research/congress-alpha/data")
TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.04  # ~4% as of 2024-2025


def load_data():
    """Load enriched trade data."""
    df = pd.read_csv(DATA_DIR / "trades_enriched.csv")
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["disclosure_date"] = pd.to_datetime(df["disclosure_date"])
    # Calculate disclosure lag in days
    df["disclosure_lag_days"] = (df["disclosure_date"] - df["trade_date"]).dt.days
    return df


def lag_analysis(df):
    """Analyze returns at different lag periods."""
    results = []

    # For "insider" returns (from trade date)
    for lag in [0, 30, 60, 90]:
        col_ret = f"return_lag_{lag}d"
        col_excess = f"excess_return_lag_{lag}d"

        if col_ret not in df.columns:
            continue

        valid = df[df[col_ret].notna()]
        if len(valid) == 0:
            continue

        returns = valid[col_ret].values
        excess = valid[col_excess].dropna().values if col_excess in valid.columns else np.array([])

        # T-test: is mean excess return significantly different from 0?
        if len(excess) > 1:
            t_stat, p_value = stats.ttest_1samp(excess, 0)
        else:
            t_stat, p_value = 0, 1

        results.append({
            "perspective": "insider (from trade date)",
            "lag_days": lag,
            "label": f"T+{lag}d from disclosure" if lag > 0 else "At disclosure",
            "n_trades": len(valid),
            "mean_return_pct": round(returns.mean(), 2),
            "median_return_pct": round(np.median(returns), 2),
            "std_return_pct": round(returns.std(), 2),
            "mean_excess_return_pct": round(excess.mean(), 2) if len(excess) > 0 else None,
            "median_excess_return_pct": round(np.median(excess), 2) if len(excess) > 0 else None,
            "win_rate_pct": round((returns > 0).mean() * 100, 1),
            "excess_win_rate_pct": round((excess > 0).mean() * 100, 1) if len(excess) > 0 else None,
            "t_statistic": round(t_stat, 3),
            "p_value": round(p_value, 4),
            "significant_5pct": p_value < 0.05 if p_value else False,
        })

    # For "copycat" returns (from disclosure date — what a retail investor gets)
    for lag in [0, 30, 60, 90]:
        col_ret = f"copy_return_lag_{lag}d"
        col_excess = f"copy_excess_lag_{lag}d"

        if col_ret not in df.columns:
            continue

        valid = df[df[col_ret].notna()]
        if len(valid) == 0:
            continue

        returns = valid[col_ret].values
        excess = valid[col_excess].dropna().values if col_excess in valid.columns else np.array([])

        if len(excess) > 1:
            t_stat, p_value = stats.ttest_1samp(excess, 0)
        else:
            t_stat, p_value = 0, 1

        results.append({
            "perspective": "copycat (from disclosure)",
            "lag_days": lag,
            "label": f"T+{lag}d after copying" if lag > 0 else "At copy (disclosure day)",
            "n_trades": len(valid),
            "mean_return_pct": round(returns.mean(), 2),
            "median_return_pct": round(np.median(returns), 2),
            "std_return_pct": round(returns.std(), 2),
            "mean_excess_return_pct": round(excess.mean(), 2) if len(excess) > 0 else None,
            "median_excess_return_pct": round(np.median(excess), 2) if len(excess) > 0 else None,
            "win_rate_pct": round((returns > 0).mean() * 100, 1),
            "excess_win_rate_pct": round((excess > 0).mean() * 100, 1) if len(excess) > 0 else None,
            "t_statistic": round(t_stat, 3),
            "p_value": round(p_value, 4),
            "significant_5pct": p_value < 0.05 if p_value else False,
        })

    # Split by trade type (Purchase vs Sale)
    for trade_type in ["Purchase", "Sale"]:
        subset = df[df["trade_type"] == trade_type]
        for lag in [30, 60, 90]:
            col = f"excess_return_lag_{lag}d"
            if col not in subset.columns:
                continue
            valid = subset[col].dropna()
            if len(valid) < 2:
                continue
            t_stat, p_value = stats.ttest_1samp(valid, 0)
            results.append({
                "perspective": f"{trade_type.lower()} only (insider)",
                "lag_days": lag,
                "label": f"{trade_type}s: T+{lag}d excess",
                "n_trades": len(valid),
                "mean_return_pct": round(subset[f"return_lag_{lag}d"].dropna().mean(), 2),
                "median_return_pct": round(subset[f"return_lag_{lag}d"].dropna().median(), 2),
                "std_return_pct": round(valid.std(), 2),
                "mean_excess_return_pct": round(valid.mean(), 2),
                "median_excess_return_pct": round(valid.median(), 2),
                "win_rate_pct": round((valid > 0).mean() * 100, 1),
                "excess_win_rate_pct": round((valid > 0).mean() * 100, 1),
                "t_statistic": round(t_stat, 3),
                "p_value": round(p_value, 4),
                "significant_5pct": p_value < 0.05,
            })

    lag_df = pd.DataFrame(results)
    lag_df.to_csv(DATA_DIR / "lag_analysis.csv", index=False)
    print(f"Lag analysis: {len(results)} rows saved")
    return lag_df


def trader_stats(df):
    """Calculate per-trader performance metrics."""
    results = []

    for trader, group in df.groupby("trader"):
        if len(group) < 1:
            continue

        # Use 90-day excess return as primary metric
        excess_90 = group["excess_return_lag_90d"].dropna()
        returns_90 = group["return_lag_90d"].dropna()

        row = {
            "trader": trader,
            "party": group["party"].iloc[0],
            "chamber": group["chamber"].iloc[0],
            "n_trades": len(group),
            "n_purchases": (group["trade_type"] == "Purchase").sum(),
            "n_sales": (group["trade_type"] == "Sale").sum(),
            "total_est_value": int(group["amount_est"].sum()),
            "avg_disclosure_lag_days": round(group["disclosure_lag_days"].mean(), 1),
            "top_sector": group["sector"].mode().iloc[0] if len(group["sector"].mode()) > 0 else "Mixed",
        }

        if len(returns_90) > 0:
            row["mean_return_90d_pct"] = round(returns_90.mean(), 2)
            row["mean_excess_90d_pct"] = round(excess_90.mean(), 2) if len(excess_90) > 0 else None
            row["win_rate_90d_pct"] = round((returns_90 > 0).mean() * 100, 1)

            # Sharpe-like ratio (using 90d returns, annualized roughly)
            if returns_90.std() > 0:
                periods_per_year = 365 / 90  # ~4 periods
                excess_mean = excess_90.mean() if len(excess_90) > 0 else returns_90.mean()
                row["sharpe_ratio"] = round(
                    (excess_mean / returns_90.std()) * math.sqrt(periods_per_year), 2
                )
            else:
                row["sharpe_ratio"] = None

            # Sortino (downside deviation only)
            downside = returns_90[returns_90 < 0]
            if len(downside) > 0 and downside.std() > 0:
                periods_per_year = 365 / 90
                row["sortino_ratio"] = round(
                    (returns_90.mean() / downside.std()) * math.sqrt(periods_per_year), 2
                )
            else:
                row["sortino_ratio"] = None

            row["best_trade_pct"] = round(returns_90.max(), 2)
            row["worst_trade_pct"] = round(returns_90.min(), 2)
        else:
            for k in ["mean_return_90d_pct", "mean_excess_90d_pct", "win_rate_90d_pct",
                       "sharpe_ratio", "sortino_ratio", "best_trade_pct", "worst_trade_pct"]:
                row[k] = None

        results.append(row)

    # Sort by excess return descending
    results_df = pd.DataFrame(results).sort_values("mean_excess_90d_pct", ascending=False, na_position="last")
    results_df.to_csv(DATA_DIR / "trader_stats.csv", index=False)
    print(f"Trader stats: {len(results)} traders")
    return results_df


def sector_stats(df):
    """Calculate per-sector metrics."""
    results = []

    for sector, group in df.groupby("sector"):
        excess_90 = group["excess_return_lag_90d"].dropna()
        returns_90 = group["return_lag_90d"].dropna()

        if len(returns_90) == 0:
            continue

        # T-test
        if len(excess_90) > 1:
            t_stat, p_value = stats.ttest_1samp(excess_90, 0)
        else:
            t_stat, p_value = 0, 1

        row = {
            "sector": sector,
            "n_trades": len(group),
            "n_traders": group["trader"].nunique(),
            "pct_purchases": round((group["trade_type"] == "Purchase").mean() * 100, 1),
            "mean_return_90d_pct": round(returns_90.mean(), 2),
            "median_return_90d_pct": round(returns_90.median(), 2),
            "mean_excess_90d_pct": round(excess_90.mean(), 2) if len(excess_90) > 0 else None,
            "win_rate_90d_pct": round((returns_90 > 0).mean() * 100, 1),
            "t_statistic": round(t_stat, 3),
            "p_value": round(p_value, 4),
            "significant_5pct": p_value < 0.05,
            "total_est_value": int(group["amount_est"].sum()),
        }
        results.append(row)

    results_df = pd.DataFrame(results).sort_values("mean_excess_90d_pct", ascending=False, na_position="last")
    results_df.to_csv(DATA_DIR / "sector_stats.csv", index=False)
    print(f"Sector stats: {len(results)} sectors")
    return results_df


def monthly_returns(df):
    """Create monthly time series of congressional trade returns for charting."""
    # Group trades by month of trade date
    df["trade_month"] = df["trade_date"].dt.to_period("M")

    monthly = []
    for month, group in df.groupby("trade_month"):
        returns_30 = group["return_lag_30d"].dropna()
        returns_60 = group["return_lag_60d"].dropna()
        returns_90 = group["return_lag_90d"].dropna()
        excess_30 = group["excess_return_lag_30d"].dropna()
        excess_60 = group["excess_return_lag_60d"].dropna()
        excess_90 = group["excess_return_lag_90d"].dropna()
        copy_30 = group["copy_return_lag_30d"].dropna()
        copy_60 = group["copy_return_lag_60d"].dropna()
        copy_90 = group["copy_return_lag_90d"].dropna()

        row = {
            "month": str(month),
            "n_trades": len(group),
            "n_purchases": (group["trade_type"] == "Purchase").sum(),
            "n_sales": (group["trade_type"] == "Sale").sum(),
            "total_est_value": int(group["amount_est"].sum()),
            # Insider returns
            "mean_return_30d": round(returns_30.mean(), 2) if len(returns_30) > 0 else None,
            "mean_return_60d": round(returns_60.mean(), 2) if len(returns_60) > 0 else None,
            "mean_return_90d": round(returns_90.mean(), 2) if len(returns_90) > 0 else None,
            "mean_excess_30d": round(excess_30.mean(), 2) if len(excess_30) > 0 else None,
            "mean_excess_60d": round(excess_60.mean(), 2) if len(excess_60) > 0 else None,
            "mean_excess_90d": round(excess_90.mean(), 2) if len(excess_90) > 0 else None,
            # Copycat returns
            "mean_copy_return_30d": round(copy_30.mean(), 2) if len(copy_30) > 0 else None,
            "mean_copy_return_60d": round(copy_60.mean(), 2) if len(copy_60) > 0 else None,
            "mean_copy_return_90d": round(copy_90.mean(), 2) if len(copy_90) > 0 else None,
            # Party breakdown
            "pct_democrat": round((group["party"] == "D").mean() * 100, 1),
            "pct_republican": round((group["party"] == "R").mean() * 100, 1),
        }
        monthly.append(row)

    monthly_df = pd.DataFrame(monthly).sort_values("month")
    monthly_df.to_csv(DATA_DIR / "monthly_returns.csv", index=False)
    print(f"Monthly returns: {len(monthly)} months")
    return monthly_df


def summary_statistics(df, lag_df, trader_df, sector_df):
    """Generate headline summary numbers for the dashboard."""
    excess_90 = df["excess_return_lag_90d"].dropna()
    returns_90 = df["return_lag_90d"].dropna()

    # Purchases only (most interesting signal)
    purchases = df[df["trade_type"] == "Purchase"]
    purch_excess_90 = purchases["excess_return_lag_90d"].dropna()
    purch_returns_90 = purchases["return_lag_90d"].dropna()

    # Cumulative return simulation (equal-weight each trade)
    if len(returns_90) > 0:
        # Simple: average return per trade, compounded
        avg_ret = returns_90.mean() / 100
        n_periods = len(returns_90)
        years = (df["trade_date"].max() - df["trade_date"].min()).days / 365.25
        cumulative = (1 + avg_ret) ** n_periods - 1

        if years > 0:
            cagr = ((1 + cumulative) ** (1 / years) - 1) * 100
        else:
            cagr = 0
    else:
        cumulative = 0
        cagr = 0

    # Max drawdown approximation (sequential worst-case)
    if len(returns_90) > 0:
        sorted_rets = returns_90.sort_values()
        worst_streak = sorted_rets.head(5).sum()
        max_drawdown = min(worst_streak, 0)
    else:
        max_drawdown = 0

    # T-test on all excess returns
    if len(excess_90) > 1:
        t_stat, p_value = stats.ttest_1samp(excess_90, 0)
    else:
        t_stat, p_value = 0, 1

    # Party comparison
    dem_excess = df[df["party"] == "D"]["excess_return_lag_90d"].dropna()
    rep_excess = df[df["party"] == "R"]["excess_return_lag_90d"].dropna()
    if len(dem_excess) > 1 and len(rep_excess) > 1:
        party_t, party_p = stats.ttest_ind(dem_excess, rep_excess)
    else:
        party_t, party_p = 0, 1

    summary = {
        "methodology": {
            "dataset": "Curated sample of ~80 high-profile congressional trades (2020-2025)",
            "source": "SEC EDGAR PTR filings, news coverage, Capitol Trades references",
            "note": "NOT the full universe. S3 data sources (house/senate-stock-watcher) returned 403.",
            "benchmark": "SPY (S&P 500 ETF)",
            "risk_free_rate": RISK_FREE_RATE,
            "generated": pd.Timestamp.now().isoformat(),
        },
        "headline_numbers": {
            "total_trades": len(df),
            "total_traders": df["trader"].nunique(),
            "date_range": f"{df['trade_date'].min().strftime('%Y-%m-%d')} to {df['trade_date'].max().strftime('%Y-%m-%d')}",
            "total_est_value": f"${df['amount_est'].sum():,.0f}",
        },
        "all_trades_90d": {
            "mean_return_pct": round(returns_90.mean(), 2) if len(returns_90) > 0 else None,
            "mean_excess_return_pct": round(excess_90.mean(), 2) if len(excess_90) > 0 else None,
            "median_excess_return_pct": round(excess_90.median(), 2) if len(excess_90) > 0 else None,
            "win_rate_pct": round((returns_90 > 0).mean() * 100, 1) if len(returns_90) > 0 else None,
            "excess_win_rate_pct": round((excess_90 > 0).mean() * 100, 1) if len(excess_90) > 0 else None,
            "t_statistic": round(float(t_stat), 3),
            "p_value": round(float(p_value), 4),
            "significant": bool(p_value < 0.05),
        },
        "purchases_90d": {
            "n_trades": len(purchases),
            "mean_excess_return_pct": round(purch_excess_90.mean(), 2) if len(purch_excess_90) > 0 else None,
            "win_rate_pct": round((purch_returns_90 > 0).mean() * 100, 1) if len(purch_returns_90) > 0 else None,
        },
        "portfolio_simulation": {
            "cumulative_return_pct": round(cumulative * 100, 1),
            "cagr_pct": round(cagr, 1),
            "max_drawdown_pct": round(max_drawdown, 1),
            "sharpe_ratio": round(
                (returns_90.mean() / returns_90.std()) * math.sqrt(4), 2
            ) if len(returns_90) > 0 and returns_90.std() > 0 else None,
        },
        "party_comparison": {
            "democrat_mean_excess_90d": round(dem_excess.mean(), 2) if len(dem_excess) > 0 else None,
            "republican_mean_excess_90d": round(rep_excess.mean(), 2) if len(rep_excess) > 0 else None,
            "democrat_n_trades": len(dem_excess),
            "republican_n_trades": len(rep_excess),
            "t_statistic": round(float(party_t), 3),
            "p_value": round(float(party_p), 4),
            "significant_difference": bool(party_p < 0.05),
        },
        "top_traders": [],
        "disclosure_lag": {
            "mean_days": round(df["disclosure_lag_days"].mean(), 1),
            "median_days": round(df["disclosure_lag_days"].median(), 1),
            "max_days": int(df["disclosure_lag_days"].max()),
            "min_days": int(df["disclosure_lag_days"].min()),
        },
    }

    # Add top 5 traders by excess return
    if trader_df is not None:
        top = trader_df.head(5)
        for _, row in top.iterrows():
            summary["top_traders"].append({
                "trader": row["trader"],
                "party": row["party"],
                "n_trades": int(row["n_trades"]),
                "mean_excess_90d": row.get("mean_excess_90d_pct"),
                "win_rate": row.get("win_rate_90d_pct"),
            })

    with open(DATA_DIR / "summary_stats.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nSummary saved. Headline: {summary['all_trades_90d']['mean_excess_return_pct']}% mean excess return (p={summary['all_trades_90d']['p_value']})")
    return summary


def main():
    print("=" * 60)
    print("CONGRESSIONAL TRADE ANALYSIS")
    print("=" * 60)

    df = load_data()
    print(f"\nLoaded {len(df)} enriched trades")
    print(f"Traders: {df['trader'].nunique()}")
    print(f"Date range: {df['trade_date'].min()} to {df['trade_date'].max()}")
    print(f"Avg disclosure lag: {df['disclosure_lag_days'].mean():.1f} days")

    print("\n--- Lag Analysis ---")
    lag_df = lag_analysis(df)

    print("\n--- Trader Stats ---")
    trader_df = trader_stats(df)

    print("\n--- Sector Stats ---")
    sector_df = sector_stats(df)

    print("\n--- Monthly Returns ---")
    monthly_df = monthly_returns(df)

    print("\n--- Summary Statistics ---")
    summary = summary_statistics(df, lag_df, trader_df, sector_df)

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"\nOutput files in {DATA_DIR}:")
    for f in sorted(DATA_DIR.glob("*")):
        size = f.stat().st_size
        print(f"  {f.name} ({size:,} bytes)")


if __name__ == "__main__":
    main()
