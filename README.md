# Silver Equilibrium Price

Independent, automatically refreshed silver equilibrium-price model and GitHub Pages dashboard.

## Model layers

1. Market benchmark: COMEX Silver Futures (`SI=F`) with a public XAG fallback.
2. Weekly ARX fair value: lagged silver + gold + USD + US 10Y + VIX + copper.
3. Physical equilibrium overlay: latest verified Silver Institute / Metals Focus supply-demand data using published silver price elasticities.
4. Governance: no critical-value imputation; explicit walk-forward gate and source/freshness status.

## Daily automation

GitHub Actions recalibrates the weekly model and refreshes `docs/silver/data/latest.json` every day.

## Site

After GitHub Pages is enabled for the repository using the `main` branch `/docs` folder, the dashboard is available at:

`https://kalmaghrabi2-hub.github.io/Silver-Equilibrium-Price/`

Full Arabic methodology: [`silver/METHODOLOGY_AR.md`](silver/METHODOLOGY_AR.md)
