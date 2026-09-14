#!/usr/bin/env python3
"""Apply strict publication governance to silver outputs."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; LATEST=ROOT/'docs/silver/data/latest.json'; CAL=ROOT/'docs/silver/data/weekly_calibration.json'
def main():
 d=json.loads(LATEST.read_text(encoding='utf-8')); c=json.loads(CAL.read_text(encoding='utf-8')); m=c.get('metrics') or {}; live=c.get('live') or {}; model=d.get('model')
 if not model:return
 passed=c.get('strict_publication_gate')=='PASS'; candidate=float(live.get('fair_value_usd_oz') or model['weekly_fair_value_usd_oz']); anchor=float(live.get('anchor_usd_oz') or candidate); active=candidate if passed else anchor; market=float(d['market']['usd_oz'])
 physical=model.get('physical_overlay') or {}; overlay_valid=physical.get('applied_to_pstar') is True and physical.get('physical_price_validation_gate')=='PASS'; mult=float(physical.get('effective_multiplier',1.0)) if overlay_valid else 1.0; applied=active*mult
 model['weekly_fair_value_usd_oz']=round(active,2); model['fundamental_p_star_usd_oz']=round(applied,2); model['market_vs_pstar_pct']=round((market/applied-1)*100,2); model['publication_source']='STRICT_VALIDATED_MODEL' if passed else 'REFERENCE_PRICE_PERSISTENCE'; model['equilibrium_claim']='VALIDATED_MARKET_REFERENCE' if passed else 'WITHHELD_NOT_VALIDATED'
 fit=m.get('accuracy_pct') if passed else m.get('naive_accuracy_pct'); model['accuracy']={'oos_fit_score_100_minus_mape_pct':fit,'mape_pct':m.get('mape_pct') if passed else m.get('naive_mape_pct'),'candidate_fit_score_pct':m.get('accuracy_pct'),'naive_fit_score_pct':m.get('naive_accuracy_pct'),'definition':'100 - MAPE on effective published reference; descriptive fit score, not probability or proof of equilibrium.'}; d['model_status']='VALID' if passed else 'REFERENCE_ONLY'; model['status']=d['model_status']; LATEST.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'strict_gate':c.get('strict_publication_gate'),'publication_source':model['publication_source'],'reference_usd_oz':round(applied,2),'fit_score_pct':fit},ensure_ascii=False))
if __name__=='__main__':main()
