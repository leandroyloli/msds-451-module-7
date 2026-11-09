"""Real input snapshots; no automatic source refresh and no price backfill."""
from dataclasses import dataclass,replace
import hashlib,json
import numpy as np
import pandas as pd
from . import config as c

@dataclass
class Inputs:
    meta:pd.DataFrame
    observed:pd.DataFrame
    valued:pd.DataFrame
    age:pd.DataFrame
    monthly:pd.DataFrame
    monthly_date:pd.DataFrame
    liquidity:pd.DataFrame
    yields:pd.Series

def load(root=c.ROOT):
    root=__import__('pathlib').Path(root)
    manifest=json.loads((root/'data/provenance.json').read_text())
    for record in manifest['records']:
        assert hashlib.sha256((root/'data'/record['file']).read_bytes()).hexdigest()==record['sha256']
    raw=pd.read_csv(root/'data/daily_prices.csv',parse_dates=['date'])
    fx=pd.read_csv(root/'data/fx.csv',parse_dates=['date'])
    meta=pd.read_csv(root/'data/universe.csv').set_index('ticker')
    assert len(meta)==61 and meta.index.is_unique
    assert not raw.duplicated(['date','ticker']).any() and (raw.adjusted_close>0).all()
    assert not fx.duplicated(['date','symbol']).any() and (fx.close>0).all()
    assert raw.date.max()<=pd.Timestamp('2026-10-23')
    columns={}
    for ticker in meta.index:
        g=raw[raw.ticker.eq(ticker)].sort_values('date')
        assert len(g)>0 and g.quote_currency.nunique()==1
        currency=g.quote_currency.iloc[0]; values=g.adjusted_close.to_numpy()
        if currency!='USD':
            symbol={'BRL':'BRL=X','GBP':'GBPUSD=X','EUR':'EURUSD=X'}[currency]
            rates=fx[fx.symbol.eq(symbol)][['date','close']].sort_values('date')
            matched=pd.merge_asof(g[['date']],rates,on='date',direction='backward',tolerance=pd.Timedelta(days=5))
            values=values/matched.close.to_numpy() if currency=='BRL' else values*matched.close.to_numpy()
        columns[ticker]=pd.Series(values,index=g.date)
    all_observed=pd.DataFrame(columns).sort_index().loc[:c.END]
    monthly={};dates={}
    for ticker in meta.index:
        s=all_observed[ticker].dropna()
        actual=s.index.to_series().resample('ME').last()
        sample=s.resample('ME').last()
        keep=(sample.index.to_series()-actual).dt.days<=7
        monthly[ticker]=sample.where(keep)
        dates[ticker]=actual.where(keep)
    monthly=pd.DataFrame(monthly).reindex(pd.date_range(all_observed.index.min(),c.END,freq='ME'))
    monthly_date=pd.DataFrame(dates).reindex(monthly.index)
    # US reference calendar. A foreign quote may be carried only for valuation.
    calendar=all_observed.index[all_observed.SPY.notna()]
    observed=all_observed.reindex(calendar)
    valued={};ages={}
    for ticker in meta.index:
        s=all_observed[ticker].dropna()
        pair=pd.merge_asof(pd.DataFrame({'date':calendar}),pd.DataFrame({'date':s.index,'price':s.to_numpy(),'quote_date':s.index}),
                           on='date',direction='backward',tolerance=pd.Timedelta(days=7))
        valued[ticker]=pd.Series(pair.price.to_numpy(),index=calendar)
        ages[ticker]=pd.Series((pair.date-pair.quote_date).dt.days.to_numpy(),index=calendar)
    liquid=pd.read_csv(root/'data/daily_liquidity.csv',parse_dates=['date'])
    assert not liquid.duplicated(['date','ticker']).any()
    # Fourteen early PIBB11 rows have no FX-derived dollar volume. Preserve
    # the raw file; exclude unknown volume from eligibility, never call it zero.
    liquid=liquid.dropna(subset=['dollar_volume_usd'])
    assert (liquid.dollar_volume_usd>=0).all()
    rates=pd.read_csv(root/'data/risk_free.csv')
    yields=pd.Series(pd.to_numeric(rates.iloc[:,1],errors='coerce').to_numpy(),index=pd.to_datetime(rates.iloc[:,0])).dropna().sort_index()/100
    return Inputs(meta,observed,pd.DataFrame(valued),pd.DataFrame(ages),monthly,monthly_date,liquid,yields)

def lagged_yield(inputs,date):
    known=inputs.yields.loc[inputs.yields.index<pd.Timestamp(date)]
    assert len(known) and (pd.Timestamp(date)-known.index[-1]).days<10
    return float(known.iloc[-1]),known.index[-1]

def select(inputs,signal):
    signal=pd.Timestamp(signal)
    history=inputs.monthly.loc[:signal].tail(c.TRAIN+1)
    assert len(history)==c.TRAIN+1
    complete=history.columns[history.notna().all()]
    daily=inputs.liquidity
    known=daily[(daily.date>signal-pd.DateOffset(months=6))&(daily.date<=signal)]
    liquidity=known.groupby('ticker').dollar_volume_usd.agg(['median','count'])
    eligible=[t for t in inputs.meta.index if t in complete and t in liquidity.index and
              liquidity.loc[t,'median']>=c.MIN_DOLLAR_VOLUME and liquidity.loc[t,'count']>=c.MIN_VOLUME_OBS]
    selected=eligible.copy()
    for family in c.FAMILIES:
        choices=[t for t in family if t in selected]
        for ticker in choices[1:]:selected.remove(ticker)
    if len(selected)<5:raise ValueError('Too few eligible ETFs for the 20% cap; no silent relaxation')
    audit=[]
    for ticker in inputs.meta.index:
        reason='history' if ticker not in complete else 'liquidity' if ticker not in eligible else 'equivalent' if ticker not in selected else 'eligible'
        audit.append({'signal_date':signal,'ticker':ticker,'reason':reason,
                      'volume_observations':int(liquidity.loc[ticker,'count']) if ticker in liquidity.index else 0,
                      'median_dollar_volume':float(liquidity.loc[ticker,'median']) if ticker in liquidity.index else 0.})
    returns=history[selected].pct_change(fill_method=None).iloc[1:]
    return selected,returns,pd.DataFrame(audit)
