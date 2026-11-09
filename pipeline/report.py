"""Academic English report: one content model produces PDF, HTML and Markdown."""
from pathlib import Path
import base64,html,json,os
import numpy as np
import pandas as pd
from . import config as c
os.environ.setdefault('MPLCONFIGDIR',str(c.ROOT/'.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.mathtext import math_to_image
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak,KeepTogether
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

PRIMARY='#1f6b56'
COLORS={'initial_hold':'#9c7b47','core':'#356fa0','trend':PRIMARY,'SPY':'#a95048','VT':'#77818c'}

def figures(accounts):
    plt.rcParams.update({'font.family':'DejaVu Serif','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(9,4.5))
    for label,account in accounts.items():ax.plot(account.index,100*account.nav,label=c.LABELS[label],color=COLORS[label],lw=1.5)
    ax.set(ylabel='USD wealth (initial capital = 100)',title='From target weights to a historical trading account')
    ax.legend(fontsize=8,ncol=2);ax.grid(alpha=.15);fig.tight_layout();fig.savefig(c.ROOT/'figures/01-wealth.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,3.7))
    for label in ['core','trend','SPY','VT']:
        a=accounts[label];peak=np.maximum.accumulate(np.r_[1.,a.nav])[1:]
        ax.plot(a.index,100*(a.nav/peak-1),label=c.LABELS[label],color=COLORS[label],lw=1.3)
    ax.set(ylabel='Drawdown (%)',title='Drawdown from prior wealth peaks');ax.legend(fontsize=8,ncol=2);ax.grid(alpha=.15)
    fig.tight_layout();fig.savefig(c.ROOT/'figures/02-drawdown.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,2.6))
    for label in ['core','trend']:ax.plot(accounts[label].index,100*accounts[label].risky_weight,color=COLORS[label],label=c.LABELS[label],lw=1.3)
    ax.set(ylim=(0,105),ylabel='ETF exposure (%)',title='Cash stays inside the growth fund');ax.legend(fontsize=8);ax.grid(alpha=.15)
    fig.tight_layout();fig.savefig(c.ROOT/'figures/03-exposure.png',dpi=180);plt.close(fig)
    returns=pd.DataFrame({k:v['return'] for k,v in accounts.items()})
    annual=(1+returns).resample('YE').prod()-1
    fig,ax=plt.subplots(figsize=(9,3.4));x=np.arange(len(annual));width=.22
    for j,label in enumerate(['core','trend','SPY']):ax.bar(x+(j-1)*width,100*annual[label],width,label=c.LABELS[label],color=COLORS[label])
    ax.axhline(0,color='#444',lw=.6);ax.set_xticks(x,[str(d.year)+('*' if d.year in [2019,2026] else '') for d in annual.index])
    ax.set(ylabel='Net return (%)',title='Calendar-year returns (* partial year)');ax.legend(fontsize=8,ncol=3);ax.grid(axis='y',alpha=.15)
    fig.tight_layout();fig.savefig(c.ROOT/'figures/04-annual-returns.png',dpi=180);plt.close(fig)
    annual.index=annual.index.year;annual.index.name='year';annual.to_csv(c.ROOT/'output/annual_returns.csv')

def build():
    metrics=pd.read_csv(c.ROOT/'output/metrics.csv',index_col=0)
    segments=pd.read_csv(c.ROOT/'output/subperiod_metrics.csv')
    sensitivity=pd.read_csv(c.ROOT/'output/sensitivity.csv')
    signals=pd.read_csv(c.ROOT/'output/signals.csv',parse_dates=['signal_date','execution_date'])
    diag=pd.read_csv(c.ROOT/'output/optimizer_diagnostics.csv')
    settings=json.loads((c.ROOT/'output/settings.json').read_text())
    bootstrap=json.loads((c.ROOT/'output/bootstrap.json').read_text())
    verified=json.loads((c.ROOT/'output/verification.json').read_text())
    exposure_diag=pd.read_csv(c.ROOT/'output/exposure_diagnostic.csv').iloc[0]
    meta=pd.read_csv(c.ROOT/'data/universe.csv')
    accounts={k:pd.read_csv(c.ROOT/f'output/{k}_account.csv',index_col=0,parse_dates=True) for k in c.LABELS}
    figures(accounts)
    fonts=Path('C:/Windows/Fonts')
    if (fonts/'pala.ttf').exists():
        for name,file in [('Academic','pala.ttf'),('AcademicBold','palab.ttf'),('AcademicItalic','palai.ttf')]:
            pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
        pdfmetrics.registerFontFamily('Academic',normal='Academic',bold='AcademicBold',italic='AcademicItalic',boldItalic='AcademicBold')
        normal,bold='Academic','AcademicBold'
    else:normal,bold='Times-Roman','Times-Bold'
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Academic',fontName=normal,fontSize=10,leading=14,spaceAfter=8))
    styles.add(ParagraphStyle(name='SmallAcademic',fontName=normal,fontSize=8,leading=10.5,spaceAfter=5))
    styles.add(ParagraphStyle(name='TableAcademic',fontName=normal,fontSize=7.4,leading=9.5))
    for name in ['Title','Heading1','Heading2']:
        styles[name].fontName=bold;styles[name].textColor=colors.HexColor(PRIMARY)
    styles['Title'].fontSize=24;styles['Title'].leading=29;styles['Title'].alignment=0
    styles['Heading1'].fontSize=16;styles['Heading1'].leading=20
    styles['Heading2'].fontSize=12;styles['Heading2'].leading=15
    story=[];web=[];md=[]
    esc=html.escape
    def heading(t,level=1):
        story.append(Paragraph(esc(t),styles['Heading1' if level==1 else 'Heading2']))
        web.append(f'<h{level+1}>{esc(t)}</h{level+1}>');md.append('#'*(level+1)+' '+t+'\n')
    def p(t,small=False):
        story.append(Paragraph(esc(t),styles['SmallAcademic' if small else 'Academic']))
        web.append(f'<p>{esc(t)}</p>');md.append(t+'\n')
    def table(headers,rows,widths):
        values=[[Paragraph(esc(str(v)),styles['TableAcademic']) for v in row] for row in [headers]+rows]
        tab=Table(values,colWidths=widths,repeatRows=1,hAlign='LEFT')
        tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9f0eb')),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor(PRIMARY)),
            ('LINEBELOW',(0,1),(-1,-1),.2,colors.HexColor('#d5ded8')),('LEFTPADDING',(0,0),(-1,-1),4),
            ('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        story.extend([tab,Spacer(1,10)])
        web.append('<div class="scroll"><table><thead><tr>'+''.join(f'<th>{esc(str(x))}</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{esc(str(x))}</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>')
        md.extend(['| '+' | '.join(map(str,headers))+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows]+[''])
    def picture(name,caption,height):
        path=c.ROOT/'figures'/name
        story.append(Image(str(path),width=488,height=height))
        story.append(Paragraph(esc(caption),styles['SmallAcademic']))
        encoded=base64.b64encode(path.read_bytes()).decode()
        web.append(f'<figure><img src="data:image/png;base64,{encoded}" alt="{esc(caption)}"><figcaption>{esc(caption)}</figcaption></figure>')
        md.append(f'![{caption}](../figures/{name})\n')
    def equation(name,formula):
        path=c.ROOT/'figures'/name
        math_to_image(formula,str(path),dpi=190,format='png',color=PRIMARY)
        from PIL import Image as PILImage
        width,height=PILImage.open(path).size
        scale=min(488/width,.38)
        story.extend([Image(str(path),width=width*scale,height=height*scale),Spacer(1,9)])
        web.append(f'<p class="equation"><img src="data:image/png;base64,{base64.b64encode(path.read_bytes()).decode()}" alt="{esc(formula)}"></p>')
        md.append(formula+'\n')
    def page():story.append(PageBreak());web.append('</section><section>')
    pct=lambda v:f'{v:.2%}'
    core=metrics.loc['core'];trend=metrics.loc['trend'];spy=metrics.loc['SPY']
    start,end=settings['account_start'],settings['account_end']
    title='From ETF Allocation to Automated Trading'
    story.append(Paragraph(title,styles['Title']))
    web.append('<header><p class="eyebrow">Northwestern University · Financial Engineering</p><h1>'+title+'</h1>')
    md.append('# '+title+'\n')
    p('Leandro Loli | MSDS 451, Section 001 | Fall 2026 | November 8, 2026',small=True)
    p('Programming Assignment 3',small=True);web.append('</header><section>')
    heading('1. From choosing the fund to running it')
    p('Earlier assignments defined the jobs of the portfolio, chose ETFs for the growth block, and studied how to divide the money among them. This assignment takes the next step: turning those choices into rules for buying, selling and rebalancing. I then test whether a trend rule helps the fund after costs.')
    p('The question moves from what to hold and how much to invest to how to maintain the portfolio over time. The safety and inflation blocks keep their original jobs. This study trades only the growth fund.')
    heading('The question',2)
    p('Can a monthly trend rule reduce the fund\'s losses without giving up too much growth? The optimizer decides how much each ETF should receive. The trend rule decides whether that amount stays in the ETF or moves to cash.')
    heading('How the rule works',2)
    table(['Step','Decision'],[
        ['Choose eligible ETFs','Use the earlier catalogue. Require five years of returns and enough trading volume; remove equivalent wrappers.'],
        ['Set the weights','Update the Checkpoint B allocation using only earlier data. Use no short positions or borrowing.'],
        ['Check the trend','Compare each ETF\'s month-end USD price with its ten-month average. Keep its target above the average; move it to cash otherwise.'],
        ['Trade later','Use the next available common closing date. Trade when weights leave their bands; charge purchases and sales.']],[100,388])
    p(f'All 61 catalogue ETFs remain candidates. Between {int(diag.eligible.min())} and {int(diag.eligible.max())} qualify at each of the {settings["signal_count"]} monthly decisions. A young fund must build enough history before it can enter.')
    p('Each ETF can receive at most 20% at a decision. The fund also has a model-based monthly loss limit. I keep three-percentage-point trading bands: small weight changes can wait, while an ETF rejected by the trend rule must be sold. Appendix A gives the exact rules.')
    p('The ten-month rule follows Faber [2]. A sustained decline may continue after a sell signal. A quick recovery can also leave the fund in cash while prices rise. That trade-off is what I test.')
    page()
    heading('2. What happened to return and risk?')
    p(f'The test covers {start} to {end}, in USD. I compare the fund with bands, the same fund with trend, and three buy-and-hold controls. The initial-fund control buys the first allocation once. SPY provides the required S&P 500 benchmark; VT adds a global-equity reference.')
    table(['Account','CAGR','Volatility','Sharpe','Max DD'],[
        [c.LABELS[k],pct(r.cagr),pct(r.volatility),f'{r.sharpe:.3f}',pct(r.max_drawdown)] for k,r in metrics.iterrows()],[176,77,82,65,88])
    p('CAGR is compound annual growth. Volatility measures return variation. Sharpe measures return above the cash proxy relative to its variation. Maximum drawdown is the largest loss from a previous wealth peak.')
    picture('01-wealth.png','Figure 1. Net historical wealth, starting from 100. All accounts use the same main dates.',244)
    p(f'With trend, CAGR is {pct(trend.cagr)}, versus {pct(core.cagr)} for the fund with bands. Sharpe is {trend.sharpe:.3f}, versus {core.sharpe:.3f}. The filter changes both growth and risk; it does not simply add return to the original fund.')
    p(f'SPY has CAGR {pct(spy.cagr)} and Sharpe {spy.sharpe:.3f}. The fund therefore needs to be judged against a simple alternative, even when its own risk measures improve.')
    p('I assume a cost of 0.10% of every amount bought or sold. The three fund accounts also pay a 0.25% annual management expense. SPY and VT pay no extra fund-management fee. Cash earns a proxy based on three-month Treasury yields. These are modeling assumptions; Appendix A explains the accounting.')
    page()
    heading('3. What does the lower drawdown mean?')
    picture('02-drawdown.png','Figure 2. Loss from each account\'s previous wealth peak.',200)
    picture('03-exposure.png','Figure 3. ETF exposure as a share of fund wealth. The remainder stays in growth-fund cash.',146)
    p(f'The largest fall is {pct(trend.max_drawdown)} with trend and {pct(core.max_drawdown)} without it. In this history, leaving some allocations in cash reduced the depth of the loss.')
    p(f'The trend fund holds {pct(trend.mean_risky_weight)} in ETFs on average. That matters: part of the lower risk comes from being less invested. The cash belongs to the growth fund and does not replace the separate safety reserve.')
    p(f'The filter also trades more. Its annual turnover is {trend.annual_turnover:.2f} times fund wealth, compared with {core.annual_turnover:.2f} for the fund with bands. Each purchase and sale has a cost.')
    p('For the investor, the choice is between more time in the market and a rule that may soften a prolonged decline. The filter can also exit late, miss a recovery or trade repeatedly around the moving average. Monthly decisions leave the fund exposed to losses between signals.')
    page()
    heading('4. Is the improvement reliable enough to adopt?')
    p('I split the ongoing accounts into an earlier and a later period. Holdings carry across the boundary; the fund does not restart or pay a second entry cost.')
    table(['Account','Period','CAGR','Sharpe','Max DD'],[
        [c.LABELS[r.strategy],r.segment,pct(r.cagr),f'{r.sharpe:.3f}',pct(r.max_drawdown)]
        for r in segments[segments.strategy.isin(['core','trend','SPY'])&segments.segment.isin(['earlier','later'])].itertuples()],[160,76,85,75,92])
    p('Earlier means July 2019-December 2022; later means January 2023-September 2026. Previous work already examined overlapping dates. This split shows how the result changes over time; it is not a new, untouched test.')
    p('I also change trading costs, the trend window, the bands and the execution delay. I keep the ten-month rule as the main result, even if another setting looks better. Appendix B reports every alternative.')
    lo,hi=bootstrap['percentile_95_interval']
    p(f'A block-resampling check asks how much the Sharpe difference varies when groups of observed months are drawn again. Its 95% interval is [{lo:+.3f}, {hi:+.3f}]. It includes zero, so this check does not establish a stable Sharpe advantage. The detailed assumptions are in Appendix B.')
    heading('Conclusion: automate the process; keep trend experimental',2)
    p('Automated execution worked: the program turned the policy into delayed trades and accounts that reconcile. The added management rules did not show a clear investment advantage in this sample.')
    initial=metrics.loc['initial_hold']
    p(f'Rebalancing had CAGR {pct(core.cagr)} and Sharpe {core.sharpe:.3f}. Holding the initial allocation had {pct(initial.cagr)} and {initial.sharpe:.3f}. The extra allocation decisions did not improve growth or Sharpe.')
    p(f'Trend delivered protection instead: maximum drawdown changed from {pct(core.max_drawdown)} to {pct(trend.max_drawdown)}, while CAGR fell from {pct(core.cagr)} to {pct(trend.cagr)}. It softened the worst fall by holding more cash and trading more. That protection had a growth cost; the Sharpe check above does not establish a stable advantage.')
    p('My decision for the project is to keep the automated execution and accounting, retain buy-and-hold as the reference, and leave trend out of the default fund policy. The growth block is meant to compound. Adding a cash-exit rule requires deciding how much growth to sacrifice for a smaller drawdown and testing that choice further. This exercise has not justified that change.')
    p('This conclusion applies to the tested period and assumptions. The catalogue and data are retrospective, and historical company/sector limits remain unverified. It does not establish that buy-and-hold will always win.')
    page()
    heading('Appendix A. Data and allocation')
    p('The inputs are the real observations saved in Module 6. Prices end October 23, 2026; the study stops at September 30, the last complete month. The normal run is offline.')
    table(['Input','Use'],[
        ['daily_prices.csv','Adjusted local prices, including the vendor\'s split and distribution adjustments'],
        ['fx.csv','Convert BRL, GBP and EUR prices to USD before calculating returns'],
        ['daily_liquidity.csv','Rebuild eligibility from the prior six calendar months of trading volume'],
        ['risk_free.csv','DGS3MO Treasury yield for the cash proxy and excess-return metrics'],
        ['universe.csv','Fixed 61-ETF catalogue and equivalent-wrapper groups'],
        ['Source/provenance JSON','Retrieval metadata, original source URLs and copy hashes']],[150,338])
    p('Eligibility requires 61 consecutive monthly USD prices, giving 60 returns. Median daily dollar volume must reach USD 1 million, with at least 100 valid observations in the prior six months. Wrapper preference follows the fixed order from Checkpoint B. It is applied among eligible funds, not by ranking future returns.')
    p('FX uses the same date or an earlier observation, no more than five calendar days old. Monthly prices use each ETF\'s last observation within seven days of month-end. Fourteen early PIBB11 volume records lack dollar volume; the raw records stay intact and the filter excludes them. Dividends are not added again to adjusted prices.')
    heading('How the optimizer sets weights',2)
    p('The optimizer uses the prior 60 monthly returns. Ledoit-Wolf shrinkage stabilizes the covariance matrix [5]. Individual means move toward a common estimate, as in Checkpoint B. Here mu_0 is the minimum-variance portfolio\'s sample mean and lambda is a data-driven shrinkage weight. This reduces the influence of noisy estimates without making them reliable forecasts.')
    equation('eq-mean.png',r'$\hat{\mu}=12[(1-\lambda)\bar{r}+\lambda\mu_0\mathbf{1}]$')
    p('It seeks the highest estimated excess return per unit of volatility after forecast costs. The equation below states that objective. Annual management cost is m, one-way trading cost is c, and w_prev is the previous structural target.')
    equation('eq-objective.png',r'$\max_w\;\frac{\hat{\mu}^{T}w-r_f-m-12c\|w-w_{\mathrm{prev}}\|_1}{\sqrt{w^T\hat{\Sigma}w}}$')
    p('Targets sum to one, prohibit shorts, cap each ETF at 20%, and limit empirical 95% monthly CVaR to 15%, including forecast costs. CVaR estimates average loss in the worst 5% of the training returns; it is not a guaranteed loss ceiling. CLARABEL solves the transformed conic problem. If estimated net excess opportunities are nonpositive, a recorded minimum-risk fallback applies.')
    p('Both accounts use the same structural targets and previous-target cost reference. Actual costs use each account\'s actual trades. Company, sector, country and economic-currency limits from the full Checkpoint B mandate are not imposed using future composition snapshots. Shorts and leverage are disabled in this operational extension.')
    page()
    heading('Appendix A. Execution and measurement')
    p('The trend filter compares the current adjusted USD month-end price with its ten-month average, including the current month. A positive test retains the structural target; otherwise the target is zero. The structural targets of other ETFs stay unchanged.')
    equation('eq-trend.png',r'$w_{i,t}^{\mathrm{trend}}=w_{i,t}^{\mathrm{base}}\,\mathbf{1}\left[P_{i,t}>\frac{1}{10}\sum_{j=0}^{9}P_{i,t-j}\right]$')
    p('Execution waits for the first later SPY-calendar date with actual quotes for potential holdings and controls. Each actual purchase or sale is checked again. A delay beyond ten calendar days fails. Valuation alone may carry an earlier observed USD price for up to seven days. Different market closes and carried valuations can affect daily risk estimates.')
    p('When weights leave their three-percentage-point bands or fail the risk check, a linear program minimizes turnover within the bands and ETF cap. Cash returns to its desired target when a trade occurs. A zero target forces full exit. Weights can drift between decisions, so decision-date limits are not continuous guarantees.')
    p('Costs reduce the capital available for the new holdings. The account solves the following identity, where H is the value held before the trade. Purchases and sales both count.')
    equation('eq-cost.png',r'$V_{\mathrm{after}}+c\sum_i|w_iV_{\mathrm{after}}-H_{i,\mathrm{before}}|=V_{\mathrm{before}}$')
    p('Initial capital is one USD accounting unit. Fractional adjusted-price units and reinvested distributions are assumed. Fund management expense accrues ACT/365 proportionally against holdings and cash, without borrowing. Embedded ETF expenses are not deducted again. Cash uses the DGS3MO yield known strictly before each interval starts, times elapsed days / 365. No taxes, FX spreads, capacity or market impact are modeled. The final account is marked to market without a forced sale.')
    table(['Metric','Calculation'],[
        ['CAGR','Compounded net wealth, annualized by elapsed calendar years'],
        ['Volatility','Sample daily-return standard deviation times sqrt(252)'],
        ['Sharpe','Mean daily excess return / its sample standard deviation, times sqrt(252); all accounts use the same cash proxy'],
        ['Maximum drawdown','Largest loss from a running wealth peak, including pre-cost initial capital'],
        ['Annual turnover','Absolute buys plus sells / pre-trade NAV, summed and annualized by elapsed years'],
        ['Cost totals','Sum of dollar costs in original-capital units, not annual rates or shares of final NAV']],[125,363])
    p('The first row includes purchase costs with zero elapsed market return. Segment CAGR begins at the preceding observation. Buy-and-hold accounts trade once; the initial-fund control allows its weights to drift. SPY and VT pay initial trading costs but no additional fund-management expense.')
    page()
    heading('Appendix B. Sensitivity and exposure checks')
    def spec(r):
        if r.kind=='cost':return f'Cost {r.value*10000:g} bp / side'
        if r.kind=='trend_months':return f'Trend {r.value:g} months'
        if r.kind=='band':return 'Exact targets; no bands'
        return 'Second common execution day'
    table(['Alternative','Account','CAGR','Sharpe','Max DD'],[
        [spec(r),'Core' if r.strategy=='core' else 'Trend',pct(r.cagr),f'{r.sharpe:.3f}',pct(r.max_drawdown)] for r in sensitivity.itertuples()],[175,63,85,73,92])
    p('Cost alternatives rerun the allocation objective and charge actual costs. They do not subtract fees from identical holdings. The delayed accounts start one common trading date later. The main rule remains ten months, ten basis points and three-percentage-point bands.')
    heading('What the resampling check tells us',2)
    p(f'The stationary block bootstrap draws {bootstrap["paths"]:,} paired paths from {bootstrap["months"]} observed monthly core, trend and cash returns, using mean blocks of six months and seed {bootstrap["seed"]}. The monthly-annualized Sharpe difference is {bootstrap["monthly_sharpe_difference"]:+.3f}; its percentile 95% interval is [{lo:+.3f}, {hi:+.3f}]. Monthly and daily Sharpe conventions differ.')
    p('The interval spans zero. This check does not establish a stable positive difference. It is conditional on the observed returns, does not rerun portfolio selection, and gives neither a null-hypothesis p-value nor a full correction for earlier research choices.')
    heading('How much comes from holding cash?',2)
    p(f'A separate diagnostic mixes core-account returns with cash at the trend fund\'s full-sample mean ETF exposure. It gives CAGR {pct(exposure_diag.cagr)}, Sharpe {exposure_diag.sharpe:.3f} and drawdown {pct(exposure_diag.max_drawdown)}. That weight is known only after observing the sample. The mix is an ex-post exposure check, not an investable or volatility-matched benchmark, and cannot isolate timing skill.')
    page()
    heading('Appendix C. Trades, checks and reproduction')
    tickets=pd.read_csv(c.ROOT/'output/trend_trades.csv',parse_dates=['date','signal_date'])
    candidates=tickets[(tickets.date>='2020-03-01')&(tickets.date<'2020-05-01')]
    event_date=candidates.date.min() if len(candidates) else tickets.date.unique()[1]
    example=tickets[tickets.date.eq(event_date)].copy();signal=example.signal_date.iloc[0]
    p(f'This excerpt shows the largest absolute trades from {pd.Timestamp(event_date).date()}, following the {signal.date()} signal. Values are fractions of original capital; a negative amount is a sale. The complete ticket file retains every trade.')
    example=example.assign(size=example.notional.abs()).nlargest(8,'size')
    table(['ETF','Side','USD notional','Cost','Adjusted USD price'],[
        [r.ticker,r.side,f'{r.notional:+.6f}',f'{r.cost:.6f}',f'{r.adjusted_usd_price:.4f}'] for r in example.itertuples()],[62,50,123,93,160])
    picture('04-annual-returns.png','Figure 4. Net calendar-year returns; 2019 and 2026 are partial years.',175)
    p(f'The saved record reports {verified["check_count"]} passed checks. An independent calculation rebuilds positions from trade units and management accrual, then reconciles wealth with prices, cash interest and costs. Maximum daily accounting error is {verified["max_daily_accounting_error"]:.2e} initial-capital units. Changing future data or truncating the history must leave earlier wealth unchanged. Artificial software-test fixtures do not enter the research inputs.')
    p('With Python 3.13, install requirements.txt and run python run.py. Use python run.py --check for accounting and temporal checks; python -m unittest discover -s tests -v for mechanism tests; and python -m pipeline.qa_artifacts for document checks. The README gives setup instructions and file locations. A clean-folder reproduction is recorded in output/clean_reproduction.json.')
    p('The input hashes preserve copy integrity, not vendor certification. The sample includes 2020 and 2022; it does not test the 2001 or 2008 crises. No live orders or Canvas submission have been made.')
    page()
    heading('References')
    refs=[
        '[1] Northwestern University. Module 7: Programming Assignment 3. Revised October 24, 2025. Local snapshot: resources/assignment.md. https://canvas.northwestern.edu/courses/260285/assignments/1818439',
        '[2] Faber, Meb. 2017. A Quantitative Approach to Tactical Asset Allocation, Episode 86, December 13. https://mebfaber.com/2017/12/13/episode-86-quantitative-approach-tactical-asset-allocation/ (checked November 8, 2026). Source for the ten-month rule. This study executes after the signal rather than at the same close.',
        '[3] Clenow, Andreas F. 2019. Trading Evolved: Anyone Can Build Killer Trading Strategies in Python. Independently Published. ISBN 978-1091983786. https://www.followingthetrend.com/trading-evolved/ (author overview checked November 8, 2026). Assignment guide; no exact chapter replication is claimed.',
        '[4] Boyd, Stephen, et al. 2017. Multi-Period Trading via Convex Optimization. Foundations and Trends in Optimization 3(1): 1-76. https://web.stanford.edu/~boyd/papers/cvx_portfolio.html (checked November 8, 2026). Reference for linking allocation, risk and trading costs.',
        '[5] Ledoit, Olivier, and Michael Wolf. 2004. A Well-Conditioned Estimator for Large-Dimensional Covariance Matrices. Journal of Multivariate Analysis 88(2): 365-411. Implemented with sklearn.covariance.LedoitWolf.',
        '[6] Board of Governors of the Federal Reserve System. Three-Month Treasury Constant-Maturity Yield [DGS3MO]. FRED. https://fred.stlouisfed.org/series/DGS3MO (definition checked November 8, 2026). An annualized yield, not a traded total-return series.',
        '[7] Local MSDS 451 Modules 3-6: Programming Assignments 1-2 and Checkpoints A-B. References for fund purpose, catalogue, estimator, constraints, inputs and report style.',
        '[8] Yahoo Finance snapshots preserved in Module 6. Source URLs, retrieval dates and hashes: data/sources.json, data/liquidity_sources.json and data/provenance.json.'
    ]
    for ref in refs:p(ref,small=True)
    heading('Relation to the Module 7 discussion',2)
    p('The discussion used a simpler minimum-variance optimizer, diagonal covariance shrinkage and exact monthly targets. This assignment restores the Checkpoint B mean/covariance estimator and net-Sharpe objective, adds CVaR, bands and fund expenses, and lags cash yields from the interval start. The hypothesis stays the same; the results need not match. Earlier deliverables and the discussion remain unchanged.')
    selected=signals.groupby('ticker').agg(max_target=('base_target','max'),eligible_months=('reason',lambda x:int(x.eq('eligible').sum())))
    for part in range(2):
        page();heading(f'Appendix D. Candidate coverage ({part+1}/2)')
        p('First eligible is the first month passing the history, liquidity and wrapper rules. Maximum target is the largest structural weight. Candidates that never qualify remain visible.',small=True)
        rows=[]
        for r in meta.iloc[part*31:(part+1)*31].itertuples():
            g=signals[(signals.ticker.eq(r.ticker))&signals.reason.eq('eligible')]
            first='Never' if not len(g) else str(g.signal_date.min().date())
            stats=selected.loc[r.ticker]
            rows.append([r.ticker,r.quote_currency,first,str(int(stats.eligible_months)),pct(stats.max_target)])
        table(['ETF','Quote','First eligible signal','Eligible months','Max target'],rows,[100,65,135,100,88])
    def footer(canvas,doc):
        canvas.setStrokeColor(colors.HexColor(PRIMARY));canvas.line(54,43,558,43)
        canvas.setFont(normal,7.3);canvas.drawString(54,29,'MSDS 451 | Programming Assignment 3 | Historical research')
        canvas.drawRightString(558,29,str(doc.page))
    path=c.ROOT/'report/msds451-pa3.pdf'
    SimpleDocTemplate(str(path),pagesize=(612,792),leftMargin=54,rightMargin=54,topMargin=40,bottomMargin=54,
                      title=title,author='Leandro Loli').build(story,onFirstPage=footer,onLaterPages=footer)
    css='''body{margin:0;color:#1c2420;background:#f3f6f4;font:17px/1.65 "Palatino Linotype",Palatino,Georgia,serif}main{max-width:960px;margin:36px auto}header,section{background:white;padding:30px 38px;margin-bottom:22px;border-radius:6px}header{border-top:3px solid #1f6b56}h1,h2,h3{color:#1f6b56;line-height:1.25}h1{font-size:2.4rem}h2{font-size:1.5rem}.eyebrow,figcaption{font:12px/1.5 "Segoe UI",sans-serif;color:#5c6b63}.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font:13px/1.5 "Segoe UI",sans-serif}th,td{padding:8px;text-align:left;border-bottom:1px solid #d5ded8}th{background:#e9f0eb}figure{margin:24px 0}figure img{width:100%;height:auto}.equation{text-align:center}.equation img{max-width:100%;max-height:72px}p{overflow-wrap:anywhere}@media(max-width:640px){main{margin:0}header,section{padding:22px 16px}}@media print{body{background:white}main{margin:0}header,section{break-inside:avoid;padding:0}figure{break-inside:avoid}}'''
    markup='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+css+'</style></head><body><main>'+''.join(web)+'</section></main></body></html>'
    (c.ROOT/'report/msds451-pa3.html').write_text(markup,encoding='utf-8')
    (c.ROOT/'report/report.md').write_text('\n'.join(md),encoding='utf-8')

if __name__=='__main__':build()
