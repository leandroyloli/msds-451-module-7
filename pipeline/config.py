from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIRST_SIGNAL='2019-06-30'
END='2026-09-30'
TRAIN=60
TREND=10
CAP=.20
BAND=.03
CVaR_LIMIT=.15
CVaR_LEVEL=.95
COST=.001
MANAGEMENT=.0025
MIN_DOLLAR_VOLUME=1_000_000
MIN_VOLUME_OBS=100
FAMILIES=[['VOO','IVV','SPY','CSPX','VUAA','VUSA','IVVB11'],['VTI','ITOT'],['VT','WRLD11'],
          ['QQQ','CNDX','NASD11'],['VWRD','VWRA','VWRA11'],['BOVA11','BOVV11','BBOV11']]
LABELS={'initial_hold':'Initial fund, buy-and-hold','core':'Fund with bands','trend':'Fund + trend',
        'SPY':'SPY buy-and-hold','VT':'VT buy-and-hold'}

def settings():
    settings={k:v for k,v in globals().items() if k.isupper() and isinstance(v,(str,int,float,list,dict))}
    settings.update(CVAR_LEVEL=CVaR_LEVEL,CVAR_LIMIT=CVaR_LIMIT)
    return settings
