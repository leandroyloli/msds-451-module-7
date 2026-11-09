"""Run the complete offline Programming Assignment 3 study."""
from pathlib import Path
import argparse,json,platform,time
import numpy as np
import pandas as pd
from pipeline import config as c
from pipeline.data import load
from pipeline.engine import make_schedule,run_account,metrics

def save_result(result,label):
    for kind,frame in result.items():
        frame.to_csv(c.ROOT/f'output/{label}_{kind}.csv',index=(kind not in ['trades','events']))

def analyses():
    start=time.perf_counter();inputs=load()
    schedule,audit,diagnostics=make_schedule(inputs)
    inputs.monthly.to_csv(c.ROOT/'data/monthly_prices_usd.csv')
    inputs.monthly_date.to_csv(c.ROOT/'data/monthly_observation_dates.csv')
    audit.to_csv(c.ROOT/'output/signals.csv',index=False)
    diagnostics.to_csv(c.ROOT/'output/optimizer_diagnostics.csv',index=False)
    results={}
    for label in c.LABELS:
        results[label]=run_account(inputs,schedule,label)
        save_result(results[label],label)
    statistics=pd.DataFrame({k:metrics(v['account']) for k,v in results.items()}).T
    statistics.index.name='strategy';statistics.to_csv(c.ROOT/'output/metrics.csv')
    segments=[]
    for label,result in results.items():
        account=result['account']
        for name,left,right in [('earlier','2019-07-01','2022-12-31'),('later','2023-01-01','2026-09-30'),
                                ('COVID_2020','2020-01-01','2020-12-31'),('rates_2022','2022-01-01','2022-12-31')]:
            segment=account.loc[left:right]
            at=account.index.get_loc(segment.index[0]);origin=account.index[max(0,at-1)]
            segments.append({'strategy':label,'segment':name,'origin':origin,**metrics(segment,origin)})
    pd.DataFrame(segments).to_csv(c.ROOT/'output/subperiod_metrics.csv',index=False)
    sensitivities=[]
    # Each hypothesis stays fixed; no winning specification is promoted.
    for cost in [0.,c.COST,.0025]:
        s=schedule if cost==c.COST else make_schedule(inputs,allocation_cost=cost)[0]
        for label in ['core','trend']:
            result=results[label] if cost==c.COST else run_account(inputs,s,label,rate=cost,full=False)
            sensitivities.append({'kind':'cost','value':cost,'strategy':label,**metrics(result['account'])})
    for months in [6,12]:
        s=make_schedule(inputs,trend_months=months)[0]
        result=run_account(inputs,s,'trend',full=False)
        sensitivities.append({'kind':'trend_months','value':months,'strategy':'trend',**metrics(result['account'])})
    for label in ['core','trend']:
        result=run_account(inputs,schedule,label,band=0.,full=False)
        sensitivities.append({'kind':'band','value':0.,'strategy':label,**metrics(result['account'])})
    delayed=make_schedule(inputs,delay=2)[0]
    for label in ['core','trend']:
        result=run_account(inputs,delayed,label,full=False)
        sensitivities.append({'kind':'common_execution_day','value':2,'strategy':label,**metrics(result['account'])})
    pd.DataFrame(sensitivities).to_csv(c.ROOT/'output/sensitivity.csv',index=False)
    # Ex-post fixed exposure is descriptive only; never call it an investable policy.
    exposure=results['trend']['account'].risky_weight.mean()
    base=results['core']['account'];cash=base.cash_return
    diagnostic=base.copy();diagnostic['return']=exposure*base['return']+(1-exposure)*cash
    pd.DataFrame([{'strategy':'ex_post_static_exposure','exposure':exposure,**metrics(diagnostic)}]).to_csv(c.ROOT/'output/exposure_diagnostic.csv',index=False)
    # Paired moving-block bootstrap of already observed returns, not new price data.
    block_bootstrap(results)
    settings=c.settings();settings.update(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,
        account_start=str(min(schedule).date()),account_end=str(results['core']['account'].index[-1].date()),
        signal_count=len(schedule),execution_seconds=time.perf_counter()-start,
        scope='Long-only operational extension of Checkpoint B, not exact replication of current-look-through/short mandate',
        target_turnover_reference='previous structural target, shared by core and trend; actual cost charged on actual trades',
        locked_for_run=True,prospective_holdout=False)
    (c.ROOT/'output/settings.json').write_text(json.dumps(settings,indent=2))
    return inputs,schedule,results

def block_bootstrap(results):
    returns=pd.DataFrame({k:v['account']['return'] for k,v in results.items()})
    cash=results['core']['account'].cash_return
    monthly=(1+returns).resample('ME').prod()-1
    cash_month=(1+cash).resample('ME').prod()-1
    rng=np.random.default_rng(4510708);N=len(monthly);B=2000;L=6
    ids=np.empty((B,N),int);ids[:,0]=rng.integers(N,size=B)
    for i in range(1,N):ids[:,i]=np.where(rng.random(B)<1/L,rng.integers(N,size=B),(ids[:,i-1]+1)%N)
    def sharpe(values):
        x=values[ids]-cash_month.to_numpy()[ids]
        return x.mean(axis=1)/x.std(axis=1,ddof=1)*np.sqrt(12)
    difference=sharpe(monthly.trend.to_numpy())-sharpe(monthly.core.to_numpy())
    observed=(monthly.trend-cash_month).mean()/(monthly.trend-cash_month).std(ddof=1)*np.sqrt(12)-\
             (monthly.core-cash_month).mean()/(monthly.core-cash_month).std(ddof=1)*np.sqrt(12)
    result={'paths':B,'mean_block_months':L,'seed':4510708,'months':N,
            'monthly_sharpe_difference':float(observed),'percentile_95_interval':np.quantile(difference,[.025,.975]).tolist(),
            'fraction_difference_positive':float(np.mean(difference>0)),
            'interpretation':'Conditional descriptive bootstrap of realized paired returns, not a null p-value, parameter re-selection test or prospective evidence.'}
    (c.ROOT/'output/bootstrap.json').write_text(json.dumps(result,indent=2))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--report-only',action='store_true')
    args=parser.parse_args()
    for name in ['output','figures','report','tmp/pdfs']:(c.ROOT/name).mkdir(parents=True,exist_ok=True)
    if not args.check and not args.report_only:analyses()
    from pipeline.verify import verify
    result=verify(temporal=not args.report_only)
    (c.ROOT/'output/verification.json').write_text(json.dumps(result,indent=2))
    if not args.check:
        from pipeline.report import build
        build()
    summary=pd.read_csv(c.ROOT/'output/metrics.csv',index_col=0).to_string()
    summary='\n'.join(line.rstrip() for line in summary.splitlines())
    (c.ROOT/'output/run_summary.txt').write_text(summary+'\n\n'+json.dumps(result,indent=2))
    print(summary);print(json.dumps(result,indent=2))

if __name__=='__main__':main()
