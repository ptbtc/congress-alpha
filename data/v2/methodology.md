# Congressional Trading Copycat Returns — Methodology

## Data Source

**Capitol Trades** (capitoltrades.com), operated by 2iQ Research. Capitol Trades aggregates publicly disclosed stock transactions from U.S. congressional members as filed under the STOCK Act (Stop Trading on Congressional Knowledge Act of 2012).

- House members file Periodic Transaction Reports (PTRs) with the Clerk of the House
- Senators file with the Secretary of the Senate
- The STOCK Act requires disclosure within 45 days of the transaction

Capitol Trades parses these filings and enriches them with issuer metadata (ticker, sector, market cap) and publication timestamps.

## Scope

- **Asset type filter:** Stock only (excludes ETFs, bonds, mutual funds, options, private equity, crypto)
- **Disclosure date range:** March 2024 – September 2025
- **Trade date range:** April 2023 – September 2025
- **Trades analyzed:** 3,962 unique (politician, ticker, date, direction) combinations with at least one horizon of forward price data
- **Politicians covered:** 71 unique members of Congress
- **Tickers covered:** 793 unique stocks

## Price Source

**Yahoo Finance** via the `yfinance` Python library. All prices are adjusted closing prices (`auto_adjust=True`), which accounts for splits and dividends.

When a target date falls on a weekend or market holiday, the next available trading day's close is used (up to 7 calendar days forward).

## Benchmark Construction

- **Broad market benchmark:** SPY (SPDR S&P 500 ETF Trust)
- **Sector benchmarks:** Sector-specific ETFs mapped from Capitol Trades sector classifications:
  - Information Technology → XLK
  - Health Care → XLV
  - Financials → XLF
  - Energy → XLE
  - Consumer Discretionary → XLY
  - Consumer Staples → XLP
  - Industrials → XLI
  - Materials → XLB
  - Utilities → XLU
  - Real Estate → XLRE
  - Communication Services → XLC

## Return Definitions

### Insider Return (not the focus)
The return between the actual trade date and the disclosure date. This represents the informational advantage period that is NOT available to copycat investors.

```
insider_return = (price_disclosure - price_trade) / price_trade
```

### Copycat Return (primary metric)
The return a hypothetical investor would earn by buying on the disclosure date (when the filing becomes public) and holding for a fixed horizon.

```
copycat_return_{H}d = (price_{disclosure + H days} - price_disclosure) / price_disclosure
```

Horizons measured: 30, 60, 90, and 180 calendar days after disclosure.

### Excess Return
The difference between the stock's copycat return and the benchmark return over the identical holding period.

```
excess_return_{H}d = copycat_return_{H}d - spy_return_{H}d
```

For sector-relative benchmarking:

```
sector_excess_{H}d = copycat_return_{H}d - sector_etf_return_{H}d
```

### Win Rate
The percentage of trades where the excess return exceeds zero (i.e., the stock outperformed the benchmark over the holding period).

## Statistical Testing

One-sample t-tests are used to assess whether mean excess returns are statistically significantly different from zero. Significance levels reported: *** (p < 0.01), ** (p < 0.05), * (p < 0.10).

## Treatment of Sell Trades

For sell trades, excess returns are calculated identically to buy trades — measuring the stock's forward return from disclosure date. A negative excess return on a sell signal would validate the information content (the sold stock underperformed). However, in this analysis we report raw excess returns without sign-flipping sells.

## Known Limitations

1. **Survivorship bias in tickers:** 43 tickers were excluded due to delisting, acquisition, or ticker changes during the analysis period (e.g., SQ→XYZ, DFS→COF, PXD→XOM). This may slightly bias results if delistings correlate with poor performance.

2. **Value estimation:** Capitol Trades reports trade values in ranges (e.g., $1K–$15K, $15K–$50K). We use the midpoint of the reported range, which introduces noise. We do not value-weight the analysis — each trade counts equally.

3. **Transaction costs not modeled:** Real copycat returns would be reduced by bid-ask spreads and commissions, though these are minimal for liquid large-cap stocks.

4. **Disclosure delay:** The "disclosure date" used here is the Capitol Trades publication date, which may lag the actual filing date by hours to days as 2iQ processes filings. A real copycat investor might detect filings even sooner via direct SEC EDGAR monitoring.

5. **No portfolio construction:** This analysis treats each trade independently. A practical copycat strategy would need position sizing, diversification, and portfolio construction rules.

6. **Sample period:** The analysis covers approximately 18 months of disclosures (Mar 2024 – Sep 2025). Results may not generalize to other market regimes.

## Output Files

| File | Description |
|------|-------------|
| `trades_v2.csv` | Complete trade-level dataset with prices and multi-horizon returns |
| `copycat_analysis.csv` | Aggregated returns by group (all, buy, sell, party, chamber) × horizon |
| `sector_benchmark.csv` | Sector-relative excess returns vs sector-specific ETFs |
| `trader_leaderboard.csv` | Per-politician statistics across all horizons |
| `summary_v2.json` | Machine-readable headline numbers for downstream consumption |

## Date Generated

2026-04-01 (data as of market close 2026-03-31)
