"""Delayed, common-quote execution with a self-financing dollar ledger."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from . import config as c
from .data import select,lagged_yield
from .allocation import allocate,band_target,tail_loss

@dataclass
class Event:
    signal:pd.Timestamp
    execution:pd.Timestamp
    base:pd.Series
    trend:pd.Series
    returns:pd.DataFrame

def make_schedule(inputs,trend_months=c.TREND,allocation_cost=c.COST,delay=1,until=None):
    last=min(pd.Timestamp(until or c.END),pd.Timestamp(c.END))
    monthly=inputs.monthly
    signals=monthly.index[(monthly.index>=pd.Timestamp(c.FIRST_SIGNAL))&(monthly.index<last)]
    previous=pd.Series(dtype=float);initial=None;schedule={};audits=[];diagnostics=[]
    for signal in signals:
        names,R,audit=select(inputs,signal)
        rf,rate_date=lagged_yield(inputs,signal)
        weight,diag=allocate(R,rf,previous,allocation_cost)
        history=monthly.loc[:signal,names]
        trend_average=history.tail(trend_months).mean()
        gate=history.iloc[-1]>trend_average
        base=weight.reindex(monthly.columns,fill_value=0.)
        trend=(weight*gate).reindex(monthly.columns,fill_value=0.)
        if initial is None:initial=base.copy()
        used=set(base.index[base>1e-12])|set(previous.index[previous>1e-12])|set(initial.index[initial>1e-12])|{'SPY','VT'}
        # This is an execution availability check, never a return-based choice.
        possible=inputs.observed.loc[(inputs.observed.index>signal)&(inputs.observed.index<=last),sorted(used)].dropna()
        if len(possible)<delay:continue  # signal remains unexecuted if data stop first
        execution=possible.index[delay-1]
        if (execution-signal).days>10:raise ValueError(f'No fresh common execution within ten days: {signal}')
        assert execution>signal and execution not in schedule
        full_R=R.reindex(columns=monthly.columns,fill_value=0.)
        schedule[execution]=Event(signal,execution,base,trend,full_R)
        audit['execution_date']=execution
        audit['base_target']=audit.ticker.map(base)
        audit['trend_target']=audit.ticker.map(trend)
        audit['trend_price']=audit.ticker.map(history.iloc[-1])
        audit['trend_average']=audit.ticker.map(trend_average)
        audit['trend_pass']=audit.ticker.map(gate).fillna(False).astype(bool)
        audit['last_price_date']=audit.ticker.map(inputs.monthly_date.loc[signal])
        audits.append(audit)
        diagnostics.append({'signal_date':signal,'execution_date':execution,'eligible':len(names),'trend_months':trend_months,
                            'training_start':R.index[0],'training_end':R.index[-1], 'rate_date':rate_date,
                            'target_cash':1-trend.sum(),**diag})
        previous=base
    if not schedule:raise ValueError('No executable signals')
    return schedule,pd.concat(audits,ignore_index=True),pd.DataFrame(diagnostics)

def transaction(values,cash,target,cost):
    """Exact dollar conservation after proportional two-sided trading costs."""
    values=np.asarray(values,float);target=np.asarray(target,float)
    assert target.min()>=-1e-10 and target.sum()<=1+1e-7
    nav=values.sum()+cash;lo=0.;hi=nav
    for _ in range(60):
        mid=(lo+hi)/2
        if mid+cost*np.abs(target*mid-values).sum()>nav:hi=mid
        else:lo=mid
    after=(lo+hi)/2;new=target*after;delta=new-values;fee=cost*abs(delta).sum()
    remaining=cash-delta.sum()-fee
    assert remaining>=-1e-9 and abs(after+fee-nav)<1e-10
    return new,max(remaining,0.),delta,fee

def run_account(inputs,schedule,label,rate=c.COST,band=c.BAND,management=None,end=None,full=True):
    if management is None:management=0. if label in ['SPY','VT'] else c.MANAGEMENT
    names=list(inputs.meta.index);start=min(schedule);end=pd.Timestamp(end or c.END)
    dates=inputs.observed.index[(inputs.observed.index>=start)&(inputs.observed.index<=end)]
    units=np.zeros(len(names));cash=1.;prior_nav=1.;prior_date=start;prior_values=np.zeros(len(names))
    initial=schedule[start].base.copy()
    rows=[];trades=[];weights=[];events=[]
    for date in dates:
        px=inputs.valued.loc[date].to_numpy();observed=inputs.observed.loc[date].to_numpy()
        held=units>1e-12
        assert np.isfinite(px[held]).all() and (inputs.age.loc[date].to_numpy()[held]<=7).all(),(date,label,'stale valuation')
        values=np.where(held,units*np.nan_to_num(px),0.)
        market_pnl=float(values.sum()-prior_values.sum())
        annual,rate_date=lagged_yield(inputs,prior_date)
        days=(date-prior_date).days;cash_return=annual*days/365;interest=cash*cash_return;cash+=interest
        gross=float(values.sum()+cash)
        # Fund expense accrual is proportional, as in a NAV-based expense.
        charge=gross*management*days/365
        factor=1-charge/gross;units*=factor;values*=factor;cash*=factor
        before=float(values.sum()+cash);fee=turnover=0.;triggered=False
        signal=pd.NaT;target_cash=np.nan
        if date in schedule:
            event=schedule[date];signal=event.signal
            current=pd.Series(values/before,index=names)
            if label in ['SPY','VT']:
                desired=pd.Series(0.,index=names);desired[label]=1.;chosen=desired
                triggered=date==start
            elif label=='initial_hold':
                desired=initial;chosen=initial;triggered=date==start
            else:
                desired=event.base if label=='core' else event.trend
                try:chosen=band_target(current,desired,event.returns,band,rate)
                except Exception as error:raise RuntimeError(f'{label} at {date}: {error}') from error
                triggered=float(abs(chosen-current).sum())>1e-9
            target_cash=1-desired.sum()
            if triggered:
                target=chosen.to_numpy();affected=(target>1e-12)|(values>1e-12)
                assert np.isfinite(observed[affected]).all(),(date,label,'no actual execution quote')
                old_cash=cash
                new,cash,delta,fee=transaction(values,cash,target,rate)
                turnover=float(abs(delta).sum()/before)
                units=np.divide(new,px,out=np.zeros(len(names)),where=(new>0)&np.isfinite(px));values=new
                if full:
                    for j in np.flatnonzero(abs(delta)>1e-10):
                        trades.append({'date':date,'signal_date':signal,'strategy':label,'ticker':names[j],
                                       'side':'BUY' if delta[j]>0 else 'SELL','notional':float(delta[j]),
                                       'cost':float(rate*abs(delta[j])),'adjusted_usd_price':float(px[j]),
                                       'units_change':float(delta[j]/px[j])})
                assert abs(old_cash-cash-delta.sum()-fee)<1e-10
            if label in ['core','trend']:
                assert max(values/(before-fee))<=c.CAP+2e-6,(date,'cap')
                assert np.max(np.abs(values/(before-fee)-desired.to_numpy()))<=band+3e-6
                assert ((values/(before-fee))[desired.to_numpy()==0]<1e-8).all()
            events.append({'date':date,'signal_date':signal,'strategy':label,'traded':triggered,
                           'turnover':turnover,'cost':fee,'target_cash':target_cash,
                           'realized_cash':cash/(before-fee),'max_etf_weight':float(max(values/(before-fee)))})
        nav=float(values.sum()+cash)
        assert abs(nav-(prior_nav+market_pnl+interest-charge-fee))<1e-10
        assert cash>=-1e-10 and units.min()>=-1e-12 and nav>0
        rows.append({'date':date,'strategy':label,'nav':nav,'return':nav/prior_nav-1,'cash':cash,
                     'risky_value':float(values.sum()),'risky_weight':float(values.sum()/nav),'cash_return':cash_return,
                     'market_pnl':market_pnl,'cash_interest':interest,'management_cost':charge,'trading_cost':fee,
                     'turnover':turnover,'signal_date':signal,'rate_date':rate_date,'day_gap':days})
        if full:
            weights.append({'date':date,**dict(zip(names,values/nav)),'CASH':cash/nav})
        prior_date=date;prior_nav=nav;prior_values=values.copy()
    return {'account':pd.DataFrame(rows).set_index('date'),'trades':pd.DataFrame(trades),
            'weights':pd.DataFrame(weights).set_index('date') if full else pd.DataFrame(),
            'events':pd.DataFrame(events)}

def metrics(account,origin=None):
    r=account['return'];rf=account.cash_return;excess=r-rf
    wealth=np.r_[1.,np.cumprod(1+r)];years=(account.index[-1]-pd.Timestamp(origin or account.index[0])).days/365.25
    return {'total_return':float(wealth[-1]-1),'cagr':float(wealth[-1]**(1/years)-1),
            'volatility':float(r.std(ddof=1)*np.sqrt(252)),
            'sharpe':float(excess.mean()/excess.std(ddof=1)*np.sqrt(252)),
            'max_drawdown':float((wealth/np.maximum.accumulate(wealth)-1).min()),
            'worst_day':float(r.min()),'annual_turnover':float(account.turnover.sum()/years),
            'mean_risky_weight':float(account.risky_weight.mean()),
            'trading_cost_initial_nav':float(account.trading_cost.sum()),
            'management_cost_initial_nav':float(account.management_cost.sum()),'observations':len(account)}
