# Silver Equilibrium Price

Independent, automatically refreshed silver equilibrium-price model and GitHub Pages dashboard.

## Model layers

1. Market benchmark: COMEX Silver Futures (`SI=F`) with a public XAG fallback.
2. Weekly ARX fair value: lagged silver + gold + USD + US 10Y + VIX + copper.
3. Physical equilibrium overlay: latest verified Silver Institute / Metals Focus supply-demand data using published silver price elasticities.
4. Governance: no critical-value imputation; expanding walk-forward validation plus an explicit persistence/naive benchmark.

## Daily automation

GitHub Actions recalibrates the weekly model and refreshes `docs/silver/data/latest.json` every day. A second workflow deploys the latest `/docs` artifact to GitHub Pages after a successful data refresh, with a daily scheduled deployment fallback.

## Publication status

The model may publish a numerical `P*` while remaining `PROVISIONAL`. It becomes `VALID` only when all required governance gates pass. In particular, the weekly layer must beat the predeclared naive persistence benchmark outside sample.

## Site

One-time repository setting required: enable **GitHub Pages** and select **GitHub Actions** as the publishing source. After that, deployments are automated by `.github/workflows/deploy-pages.yml`.

Expected dashboard URL:

`https://kalmaghrabi2-hub.github.io/Silver-Equilibrium-Price/`

Full Arabic methodology: [`silver/METHODOLOGY_AR.md`](silver/METHODOLOGY_AR.md)
