# Silver Institutional Data Upgrade

Purpose: improve genuine out-of-sample skill without weakening publication gates or tuning on the final OOS window.

## Point-in-time data policy

1. Every predictor must be available before the forecast week starts.
2. Final 260-week OOS is never used for factor, hyperparameter, or blend selection.
3. Revised macro/fundamental data may not be backfilled as if the revision had been historically known.
4. Daily snapshots are retained from activation onward to build an auditable point-in-time archive.
5. A candidate factor can affect the published price only after independent strict validation passes all gates.

## Priority institutional sources

| Factor | Series/source | Frequency | Role |
|---|---|---:|---|
| 10Y real yield | Federal Reserve/FRED `DFII10` | Daily | precious-metals monetary channel |
| Broad USD | Federal Reserve/FRED `DTWEXBGS` | Daily | currency valuation channel |
| VIX | CBOE via FRED `VIXCLS` | Daily | risk regime |
| 10Y breakeven inflation | FRED `T10YIE` | Daily | inflation expectations |
| Gold price | market cross-factor | Weekly | precious-metals common factor |
| Copper price | market cross-factor | Weekly | industrial-cycle factor |
| Supply/demand by sector | Silver Institute / Metals Focus | Annual | structural balance |
| Mine production/reserves | USGS / Silver Institute | Annual | structural supply |
| ETP/inventory/liquidity data | Silver Institute / exchange sources | weekly/monthly | investment/liquidity channel |

## Research protocol

Candidate feature sets are selected only on training + validation, then frozen for one evaluation on the untouched final 260 weeks. Persistence remains the primary benchmark. Gold and copper cross-factors are lagged so the forecast uses only information known before the target week. No price clipping or cosmetic convergence toward spot is allowed.

The current published model remains `REFERENCE_ONLY` until the strict governance contract passes.
