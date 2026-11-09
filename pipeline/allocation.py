"""Checkpoint B estimator and net-Sharpe objective, long-only operational scope.

No present-day holdings data are used to impose historical company/sector limits.
"""
import numpy as np
import pandas as pd
import cvxpy as cp
from sklearn.covariance import LedoitWolf
from . import config as c

def tail_loss(R,w,cost=0.):
    loss=np.sort(-np.asarray(R)@np.asarray(w)+cost)[::-1]
    mass=len(loss)*(1-c.CVaR_LEVEL);n=int(np.floor(mass+1e-9));fraction=mass-n
    return float((loss[:n].sum()+(fraction*loss[n] if fraction>1e-9 else 0))/mass)

def estimates(R):
    R=np.asarray(R);T,N=R.shape
    fit=LedoitWolf().fit(R);cov=fit.covariance_;inv=np.linalg.inv(cov)
    one=np.ones(N);gmv=inv@one/(one@inv@one);means=R.mean(axis=0);center=float(gmv@means)
    delta=means-center;shrink=float((N+2)/(N+2+T*max(delta@inv@delta,0)))
    mu=((1-shrink)*means+shrink*center)*12;annual=cov*12
    eig,vec=np.linalg.eigh(annual);root=(vec*np.sqrt(np.maximum(eig,1e-12)))@vec.T
    return mu,annual,root,{'mean_shrinkage':shrink,'covariance_shrinkage':float(fit.shrinkage_)}

def solve(problem):
    problem.solve(solver='CLARABEL',tol_gap_abs=1e-9,tol_gap_rel=1e-9,tol_feas=1e-9,max_iter=250)
    if problem.status not in ['optimal','optimal_inaccurate']:raise ValueError('Optimization failed: '+problem.status)

def allocate(R,rf,previous,rate=c.COST):
    names=list(R.columns);R=np.asarray(R);n=len(names)
    mu,cov,root,diag=estimates(R)
    # Shared structural target stream: previous target, not either account's holdings.
    old=previous.reindex(names,fill_value=0.).to_numpy()
    removed=float(previous.drop(index=names,errors='ignore').abs().sum())
    y=cp.Variable(n,nonneg=True);scale=cp.Variable(nonneg=True)
    eta=cp.Variable();z=cp.Variable(len(R),nonneg=True)
    trade=cp.norm1(y-cp.multiply(old,scale))+removed*scale
    monthly_cost=c.MANAGEMENT/12*scale+rate*trade
    cons=[cp.sum(y)==scale,y<=c.CAP*scale,cp.norm(root@y)<=1,
          z>=-R@y+monthly_cost-eta,eta+cp.sum(z)/((1-c.CVaR_LEVEL)*len(R))<=c.CVaR_LIMIT*scale]
    problem=cp.Problem(cp.Maximize(mu@y-(rf+c.MANAGEMENT)*scale-12*rate*trade),cons)
    solve(problem)
    method='maximum_net_sharpe'
    if scale.value is None or scale.value<1e-7 or problem.value<1e-8:
        w=cp.Variable(n,nonneg=True);eta=cp.Variable();z=cp.Variable(len(R),nonneg=True)
        cost=c.MANAGEMENT/12+rate*(cp.norm1(w-old)+removed)
        prob=cp.Problem(cp.Minimize(cp.quad_form(w,cp.psd_wrap(cov))),
             [cp.sum(w)==1,w<=c.CAP,z>=-R@w+cost-eta,eta+cp.sum(z)/((1-c.CVaR_LEVEL)*len(R))<=c.CVaR_LIMIT])
        solve(prob);answer=np.asarray(w.value);method='negative_expected_excess_minimum_risk'
    else: answer=np.asarray(y.value)/float(scale.value)
    answer=np.maximum(answer,0.);answer[answer<1e-8]=0.;answer/=answer.sum()
    turnover=float(abs(answer-old).sum()+removed)
    cvar=tail_loss(R,answer,c.MANAGEMENT/12+rate*turnover)
    assert answer.max()<=c.CAP+2e-6 and abs(answer.sum()-1)<1e-10 and cvar<=c.CVaR_LIMIT+2e-6
    diag.update(method=method,forecast_turnover=turnover,cvar95_monthly=cvar,
                expected_return=float(mu@answer),expected_volatility=float(np.sqrt(answer@cov@answer)),
                expected_net_sharpe=float((mu@answer-rf-c.MANAGEMENT-12*rate*turnover)/np.sqrt(answer@cov@answer)))
    return pd.Series(answer,index=names),diag

def band_target(current,target,R,band=c.BAND,rate=c.COST):
    """Minimum turnover inside target bands; zero targets require full exit."""
    names=target.index;old=current.reindex(names,fill_value=0.).to_numpy();goal=target.to_numpy()
    active=np.flatnonzero(goal>1e-12)
    if len(active)==0:return target.copy()
    low=np.maximum(goal-band,0.);high=np.minimum(goal+band,c.CAP);high[goal==0]=0.
    cash_goal=1-goal.sum();cash_old=1-old.sum()
    # No trading if already inside every band and hard cap.
    if ((old>=low-1e-10)&(old<=high+1e-10)).all() and abs(cash_old-cash_goal)<=band+1e-10 and tail_loss(R,old,c.MANAGEMENT/12)<=c.CVaR_LIMIT:
        return current.reindex(names,fill_value=0.).copy()
    w=cp.Variable(len(active));full=cp.hstack([w[list(active).index(i)] if i in active else 0. for i in range(len(goal))])
    cash=1-cp.sum(w)
    eta=cp.Variable();z=cp.Variable(len(R),nonneg=True)
    trade=cp.norm1(full-old)
    cost=c.MANAGEMENT/12+rate*trade
    constraints=[w>=low[active],w<=high[active],cash==max(0.,cash_goal),
                 z>=-np.asarray(R)@full+cost-eta,eta+cp.sum(z)/((1-c.CVaR_LEVEL)*len(R))<=c.CVaR_LIMIT]
    # This is a linear program. A dedicated LP solver avoids poor numerical
    # conditioning from adding an unnecessary near-zero quadratic tie-breaker.
    problem=cp.Problem(cp.Minimize(trade),constraints)
    problem.solve(solver='HIGHS')
    if problem.status!='optimal':raise ValueError('Band LP failed: '+problem.status)
    answer=np.zeros(len(goal));answer[active]=np.maximum(np.asarray(w.value),0.)
    if answer.sum()>1 and answer.sum()<1+1e-7:answer/=answer.sum()
    assert answer.sum()<=1+1e-7 and answer.max()<=c.CAP+2e-6 and answer.min()>=0
    assert np.max(np.abs(answer-goal))<=band+2e-6
    assert tail_loss(R,answer,c.MANAGEMENT/12+rate*abs(answer-old).sum())<=c.CVaR_LIMIT+2e-6
    return pd.Series(answer,index=names)
