"""Independent saved-output accounting plus end-to-end temporal controls."""
from dataclasses import replace
import json
import numpy as np
import pandas as pd
from . import config as c
from .data import load,select
from .engine import make_schedule,run_account,metrics
from .allocation import tail_loss

def verify(temporal=True):
    inputs=load();saved=pd.read_csv(c.ROOT/'output/metrics.csv',index_col=0);checks=[]
    signals=pd.read_csv(c.ROOT/'output/signals.csv',parse_dates=['signal_date','execution_date','last_price_date'])
    assert (signals.execution_date>signals.signal_date).all()
    diagnostics=pd.read_csv(c.ROOT/'output/optimizer_diagnostics.csv',parse_dates=['signal_date','execution_date','training_end','rate_date'])
    assert (diagnostics.training_end<=diagnostics.signal_date).all() and (diagnostics.rate_date<diagnostics.signal_date).all()
    assert diagnostics.cvar95_monthly.max()<=c.CVaR_LIMIT+2e-6
    for signal,g in signals.groupby('signal_date'):
        names,R,audit=select(inputs,signal)
        assert list(g.loc[g.reason.eq('eligible'),'ticker'])==names
        assert len(g)==61 and abs(g.base_target.sum()-1)<1e-9 and g.base_target.max()<=c.CAP+2e-6
        actual=inputs.monthly.loc[:signal,names].tail(c.TREND)
        gate=actual.iloc[-1]>actual.mean()
        q=g.set_index('ticker').loc[names]
        np.testing.assert_array_equal(q.trend_pass,gate)
        np.testing.assert_allclose(q.trend_target,q.base_target*gate,atol=1e-10)
        assert (q.last_price_date<=signal).all()
    checks+=['source hashes, unique positive prices and FX','historical liquidity rebuilt from past daily observations',
             '61-price history and equivalent-wrapper selection','training, yield and signal timestamps',
             'optimizer ETF cap, funding and empirical CVaR','ten-month signal independently reconstructed']
    max_error=0.;accounts={}
    for label in c.LABELS:
        account=pd.read_csv(c.ROOT/f'output/{label}_account.csv',parse_dates=['date','rate_date']).set_index('date')
        accounts[label]=account
        weights=pd.read_csv(c.ROOT/f'output/{label}_weights.csv',index_col=0,parse_dates=True)
        trades=pd.read_csv(c.ROOT/f'output/{label}_trades.csv',parse_dates=['date','signal_date'])
        np.testing.assert_allclose(weights.sum(axis=1),1.,atol=1e-10)
        assert weights.min().min()>=-1e-10 and (account.rate_date<account.index.to_series()).all()
        before=account.nav.shift(1,fill_value=1.)
        reconstructed=before+account.market_pnl+account.cash_interest-account.management_cost-account.trading_cost
        error=float(abs(reconstructed-account.nav).max());max_error=max(max_error,error)
        assert error<1e-10
        np.testing.assert_allclose((1+account['return']).cumprod(),account.nav,atol=1e-10)
        np.testing.assert_allclose(account.risky_value+account.cash,account.nav,atol=1e-10)
        if len(trades):
            assert (trades.signal_date<trades.date).all()
            np.testing.assert_allclose(trades.cost,c.COST*abs(trades.notional),atol=1e-12)
            fees=trades.groupby('date').cost.sum().reindex(account.index,fill_value=0.)
            np.testing.assert_allclose(fees,account.trading_cost,atol=1e-10)
            # Dollar holdings reconstruct from recorded trade units and expense accrual.
            units=np.zeros(len(inputs.meta));prior_date=account.index[0];mapname={t:i for i,t in enumerate(inputs.meta.index)}
            grouped={d:g for d,g in trades.groupby('date')}
            management=0. if label in ['SPY','VT'] else c.MANAGEMENT
            for date,row in account.iterrows():
                factor=1-management*(date-prior_date).days/365
                units*=factor
                if date in grouped:
                    for t in grouped[date].itertuples():
                        assert pd.notna(inputs.observed.at[date,t.ticker])
                        units[mapname[t.ticker]]+=t.units_change
                values=units*np.nan_to_num(inputs.valued.loc[date].to_numpy())
                np.testing.assert_allclose(values.sum(),row.risky_value,atol=1e-9)
                np.testing.assert_allclose(values/row.nav,weights.loc[date,inputs.meta.index],atol=1e-8)
                prior_date=date
        for key,value in metrics(account).items():
            assert np.isclose(saved.loc[label,key],value,rtol=1e-9,atol=1e-10),(label,key)
        if label in ['SPY','VT','initial_hold']:assert trades.date.nunique()==1
        if label in ['core','trend']:
            events=pd.read_csv(c.ROOT/f'output/{label}_events.csv',parse_dates=['date','signal_date'])
            assert events.max_etf_weight.max()<=c.CAP+2e-6
            for e in events.itertuples():
                target=signals[signals.signal_date.eq(e.signal_date)].set_index('ticker')['base_target' if label=='core' else 'trend_target']
                actual=weights.loc[e.date,inputs.meta.index]
                assert abs(actual-target).max()<=c.BAND+3e-6
                assert actual[target.eq(0)].max()<1e-8
    checks+=['fully funded nonnegative holdings and cash','daily NAV / P&L / interest / fee reconciliation',
             'independent units rebuilt from trade tickets and fund expense accrual','actual execution quotes, never stale fills',
             'cost charged on both buy and sell notionals','buy-and-hold trades once','realized decision-date caps, bands and forced exits',
             'saved metrics independently recomputed']
    if temporal:
        schedule,_,_=make_schedule(inputs)
        for label in ['core','trend']:
            reproduced=run_account(inputs,schedule,label,full=False)['account']
            np.testing.assert_allclose(reproduced.nav,accounts[label].nav,rtol=1e-9,atol=1e-10)
        cut=pd.Timestamp('2023-06-30')
        # Deliberately poison only future price, monthly, liquidity and yield values.
        observed=inputs.observed.copy();observed.loc[observed.index>cut]*=1.2
        valued=inputs.valued.copy();valued.loc[valued.index>cut]*=1.2
        monthly=inputs.monthly.copy();monthly.loc[monthly.index>cut]*=1.2
        liquidity=inputs.liquidity.copy();liquidity.loc[liquidity.date>cut,'dollar_volume_usd']*=.001
        yields=inputs.yields.copy();yields.loc[yields.index>cut]+=.03
        changed=replace(inputs,observed=observed,valued=valued,monthly=monthly,liquidity=liquidity,yields=yields)
        # Construct schedules only as far as the comparison endpoint. Full inputs
        # still contain poisoned future values; selection must exclude them.
        short,_,_=make_schedule(inputs,until=cut)
        altered,_,_=make_schedule(changed,until=cut)
        truncated=replace(inputs,observed=inputs.observed.loc[:cut],valued=inputs.valued.loc[:cut],age=inputs.age.loc[:cut],
                          monthly=inputs.monthly.loc[:cut],monthly_date=inputs.monthly_date.loc[:cut],
                          liquidity=inputs.liquidity[inputs.liquidity.date<=cut],yields=inputs.yields.loc[:cut])
        prefix,_,_=make_schedule(truncated,until=cut)
        assert list(short)==list(altered)==list(prefix)
        for label in ['core','trend']:
            original=accounts[label].loc[:cut,'nav']
            for source,events in [(changed,altered),(truncated,prefix)]:
                got=run_account(source,events,label,end=cut,full=False)['account'].nav
                np.testing.assert_allclose(got,original,rtol=1e-9,atol=1e-10)
        checks+=['main accounts reproduced from raw inputs','future data perturbation leaves earlier execution and wealth unchanged',
                 'truncated-input prefix reproduces earlier wealth']
    return {'passed':True,'check_count':len(checks),'checks':checks,'max_daily_accounting_error':max_error,
            'temporal_checks_run':temporal,'limitation':'Does not certify vendor accuracy, historical holdings constraints, prospective performance or broker fills.'}
