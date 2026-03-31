# Congressional Trading Alpha

**An empirical analysis of disclosure-lag returns from US congressional stock trades**

![Congressional Trading Alpha](screenshot.png)
> *Replace `screenshot.png` with a screenshot of the live platform. Recommended: 1200×630px for social previews.*

---

## Features

- **Interactive Return Distribution Charts** — Visualize congressional trade returns vs. S&P 500 benchmarks with Chart.js
- **Portfolio Simulator** — Model hypothetical portfolios that mirror congressional trading patterns with adjustable parameters
- **Trade Explorer** — Browse and filter individual congressional stock transactions with full metadata
- **Disclosure Lag Analysis** — Quantify the impact of mandatory reporting delays on strategy viability
- **Member Performance Rankings** — Identify which legislators generate the highest risk-adjusted returns
- **Statistical Methodology Panel** — Transparent presentation of t-tests, confidence intervals, and effect sizes
- **Sector Heatmaps** — Examine congressional trading concentration across market sectors
- **Responsive Design** — Full functionality on desktop and mobile devices

## Data & Methodology

Congressional stock trade disclosures are sourced from public STOCK Act filings and cross-referenced with historical price data via **yfinance**. The analysis pipeline:

1. **Collection** — Parse disclosure PDFs and structured data from official congressional records
2. **Enrichment** — Match ticker symbols, retrieve historical OHLCV data, calculate forward returns at multiple horizons (1-day, 1-week, 1-month, 3-month)
3. **Benchmarking** — Compute contemporaneous S&P 500 returns for identical holding periods
4. **Statistical Testing** — Two-sample t-tests, bootstrap confidence intervals, and Sharpe ratio comparisons
5. **Disclosure Lag Adjustment** — Re-run all analyses using public disclosure dates (not trade dates) to measure realistic implementable alpha

All raw data and computed metrics are embedded directly in the platform for full reproducibility.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla HTML, CSS, JavaScript |
| Charts | Chart.js 4.x |
| Data Pipeline | Python, yfinance, pandas |
| Hosting | Any static file server |

Zero dependencies at runtime. No build step. No framework. Just files.

## Deployment

### Vercel (One-Click)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/ptbtc/congress-alpha)

The included `vercel.json` handles SPA routing automatically.

### Any Static Host

Upload all files to any static hosting provider (Netlify, GitHub Pages, Cloudflare Pages, S3 + CloudFront, or a simple nginx server). No build step required.

```bash
# Local development
python -m http.server 8120
# Open http://localhost:8120
```

## License

MIT — see [LICENSE](LICENSE) for details.

## Credits

Research and development by [OpenClaw](https://openclaw.ai).
