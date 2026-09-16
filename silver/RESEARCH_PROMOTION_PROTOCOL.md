# Silver Research-to-Publication Promotion Protocol

## Purpose
Prevent data-snooping after final OOS results have been inspected while allowing continued model research.

## Locked facts
- The existing weekly final 260-week OOS has already been evaluated and cannot be reused as a pristine promotion holdout for newly invented model families.
- Cyclical research generation v1 has been evaluated and rejected for publication.
- Historical FRED CSV data are current-vintage and do not by themselves prove what data were known on each historical forecast date.

## Research track
New feature sets, rolling windows, nonlinear/regime specifications, industrial factors and benchmark variants remain RESEARCH_ONLY. Historical diagnostics can rank research ideas, but cannot by themselves promote a model into the published price after the holdout has been reviewed.

## Promotion requirements
1. Predictor data are point-in-time, release-lag aware and revision-aware; use ALFRED/realtime vintages where revisions matter or a sufficiently long committed forward archive.
2. Model family, feature set, transformations, training window, hyperparameter grid and benchmark set are frozen before a promotion holdout is opened.
3. Promotion holdout is untouched by model selection.
4. Weekly hard gates remain unchanged: MSE skill >=2%, relative MAPE improvement >=1%, one-sided HAC DM p<=0.05, >=4/5 positive 52-week regimes, direction >=52.5%, R2>=0.60, MAPE<=12%.
5. Persistence is mandatory; additional benchmarks include random-walk-with-drift and a simple predeclared silver-specific benchmark.
6. No market-relative clipping or cosmetic override.
7. Silver Institute/Metals Focus physical supply-demand and USGS elasticity effects require separate point-in-time price validation. Until that exists, effective physical price weight remains zero.
8. Monthly industrial series such as INDPRO require explicit original release-date lags before historical predictive use.

## Forward evidence
Daily committed institutional snapshots beginning 2026-09-16 form an auditable forward point-in-time archive for future shadow validation.

## Current publication rule
Until a candidate passes the complete promotion protocol, production stays REFERENCE_ONLY whenever the strict gate fails.
