# Economic Committee → Engineering Committee Implementation Standard

## Scope
Keep three horizons separate: short-term Market Reference, medium-term Cyclical Fair Value, and long-term Structural/Physical Equilibrium. A one-week forecast is not evidence of structural equilibrium.

## Non-negotiable rules
- `100 - MAPE` is an **OOS Fit Score**, not probability or equilibrium accuracy.
- Final OOS data cannot be used for model/hyperparameter selection.
- No look-ahead and no imputation of critical fundamentals.
- Any failed/unvalidated layer has zero price weight.
- No market-relative price clipping or cosmetic guardrail.
- If the strict gate fails: `model_status=REFERENCE_ONLY`, `equilibrium_claim=WITHHELD_NOT_VALIDATED`.

## Weekly hard gate
All must pass: non-zero model weight; MSE skill >=2%; relative MAPE improvement >=1%; one-sided Diebold-Mariano p<=0.05; positive skill in >=4/5 contiguous 52-week regimes; direction accuracy >=52.5%; R²>=0.60; MAPE<=12%; untouched final OOS >=260 weeks.

## Silver physical gate
The Silver Institute/Metals Focus supply-demand deficit and USGS elasticities remain diagnostic until a point-in-time historical price-level validation demonstrates incremental OOS skill. Until then the effective physical multiplier must remain 1.0 and `applied_to_pstar=false`.

## Required production sequence
Compile → calibrate → independent strict validation → update latest inputs → apply publication gate → assert publication contract → commit outputs → deploy Pages after successful update.

## Engineering principle
Large market/equilibrium gaps are allowed. Unsupported certainty is not.
