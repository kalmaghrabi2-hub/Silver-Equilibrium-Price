#!/usr/bin/env python3
"""Independent strict validation layer. Fails closed."""
from __future__ import annotations
import importlib.util,json,math,statistics
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; CAL_PATH=ROOT/'docs/silver/data/weekly_calibration.json'; MOD_PATH=ROOT/'silver/src/calibrate_silver_weekly_arx.py'
FINAL=260; WINDOWS=5; MIN_SKILL=2.0; MIN_REL_MAPE=1.0; MAX_DM_P=.05; MIN_POS_WINDOWS=4; MIN_DIR=52.5
def load_module():
 spec=importlib.util.spec_from_file_location('calibrator',MOD_PATH); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
def q(vals,p):
 v=sorted(vals); x=(len(v)-1)*p; lo=int(math.floor(x)); hi=int(math.ceil(x)); return v[lo] if lo==hi else v[lo]+(v[hi]-v[lo])*(x-lo)
def metrics(pred,actual,naive):
 mse=statistics.fmean((a-p)**2 for a,p in zip(actual,pred)); nmse=statistics.fmean((a-n)**2 for a,n in zip(actual,naive)); mape=100*statistics.fmean(abs((a-p)/a) for a,p in zip(actual,pred)); nmape=100*statistics.fmean(abs((a-n)/a) for a,n in zip(actual,naive)); hits=n=0
 for a,p,z in zip(actual,pred,naive):
  if a-z!=0:n+=1;hits+=int(((a-z)>0)==((p-z)>0))
 return {'mape_pct':mape,'naive_mape_pct':nmape,'skill_mse_pct':100*(1-mse/nmse) if nmse else 0.0,'relative_mape_improvement_pct':100*(nmape-mape)/nmape if nmape else 0.0,'direction_accuracy_pct':100*hits/n if n else 0.0}
def dm(pred,actual,naive,lag=4):
 d=[(a-n)**2-(a-p)**2 for a,p,n in zip(actual,pred,naive)]; n=len(d); md=statistics.fmean(d); c=[x-md for x in d]; lrv=sum(x*x for x in c)/n; ml=min(lag,n-1)
 for k in range(1,ml+1):lrv+=2*(1-k/(ml+1))*sum(c[t]*c[t-k] for t in range(k,n))/n
 if lrv<=0:return 0.0,1.0
 stat=md/math.sqrt(lrv/n); return stat,.5*math.erfc(stat/math.sqrt(2))
def main():
 c=json.loads(CAL_PATH.read_text(encoding='utf-8')); cal=load_module(); target,_=cal.chart(cal.TARGET); factors={s:cal.chart(s)[0] for s in cal.MACRO}; common=sorted(set(target).intersection(*[set(factors[s]) for s in cal.MACRO])); raw=[(w,target[w],[factors[s][w] for s in cal.MACRO]) for w in common]; rows=[]
 for i in range(1,len(raw)):
  pw,prev,pm=raw[i-1]; w,cur,_=raw[i]
  if w-pw==1:rows.append((w,cur,[math.log(prev)]+pm))
 start=len(rows)-FINAL; lam=float(c['ridge_lambda']); weight=float(c['blend_weight_vs_persistence']); pred=[]; actual=[]; naive=[]; dates=[]
 for i in range(start,len(rows)):
  anc=math.exp(rows[i][2][0]); rawp=cal.predict_one(rows[:i],rows[i],lam); pred.append(cal.blended(rawp,anc,weight)); actual.append(rows[i][1]); naive.append(anc); dates.append(datetime.fromtimestamp(rows[i][0]*604800,tz=timezone.utc).date().isoformat())
 m=metrics(pred,actual,naive); stat,p=dm(pred,actual,naive); size=len(actual)//WINDOWS; ws=[]; pos=0
 for j in range(WINDOWS):
  lo=j*size; hi=(j+1)*size if j<WINDOWS-1 else len(actual); mm=metrics(pred[lo:hi],actual[lo:hi],naive[lo:hi]); ok=mm['skill_mse_pct']>0 and mm['mape_pct']<mm['naive_mape_pct']; pos+=int(ok); ws.append({'start':dates[lo],'end':dates[hi-1],'skill_mse_pct':round(mm['skill_mse_pct'],3),'positive':ok})
 checks={'nonzero_model_weight':weight>0,'min_mse_skill':m['skill_mse_pct']>=MIN_SKILL,'min_relative_mape_improvement':m['relative_mape_improvement_pct']>=MIN_REL_MAPE,'dm_significance':p<=MAX_DM_P,'regime_stability':pos>=MIN_POS_WINDOWS,'directional_information':m['direction_accuracy_pct']>=MIN_DIR}; passed=all(checks.values()); me=[math.log(a/pr) for a,pr in zip(actual,pred)]; ne=[math.log(a/nv) for a,nv in zip(actual,naive)]; center=float(c['live']['fair_value_usd_oz']); anchor=float(c['live']['anchor_usd_oz'])
 c['strict_validation']={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'failed_checks':[k for k,v in checks.items() if not v],'thresholds':{'min_mse_skill_pct':MIN_SKILL,'min_relative_mape_improvement_pct':MIN_REL_MAPE,'max_dm_p_value':MAX_DM_P,'min_positive_52w_windows':MIN_POS_WINDOWS,'min_direction_accuracy_pct':MIN_DIR},'diagnostics':{'mse_skill_pct':round(m['skill_mse_pct'],3),'relative_mape_improvement_pct':round(m['relative_mape_improvement_pct'],3),'direction_accuracy_pct':round(m['direction_accuracy_pct'],2),'dm_stat':round(stat,4),'dm_one_sided_p_value':round(p,6),'positive_52w_windows':pos,'windows':ws}}
 c['strict_publication_gate']='PASS' if passed else 'FAIL'; c['publication_status']='VALIDATED' if passed else 'REFERENCE_ONLY'; c['uncertainty']={'method':'empirical final-OOS log errors','candidate_80':[round(center*math.exp(q(me,.10)),4),round(center*math.exp(q(me,.90)),4)],'candidate_95':[round(center*math.exp(q(me,.025)),4),round(center*math.exp(q(me,.975)),4)],'persistence_80':[round(anchor*math.exp(q(ne,.10)),4),round(anchor*math.exp(q(ne,.90)),4)],'persistence_95':[round(anchor*math.exp(q(ne,.025)),4),round(anchor*math.exp(q(ne,.975)),4)]}; c['rules']['fit_score_definition']='100 - final OOS MAPE; descriptive fit score only, NOT probability and NOT equilibrium accuracy'; c['rules']['equilibrium_claim_rule']='Near-term forecast cannot by itself validate structural equilibrium; every structural/physical overlay needs separate OOS validation.'
 CAL_PATH.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'strict_publication_gate':c['strict_publication_gate'],'failed':c['strict_validation']['failed_checks'],'dm_p':round(p,6),'positive_windows':pos},ensure_ascii=False))
if __name__=='__main__':main()
