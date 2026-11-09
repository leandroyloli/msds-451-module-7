"""Explicit one-time import; ordinary reproduction never reads sibling folders."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'msds-451-module-6'
FILES=['universe.csv','daily_prices.csv','fx.csv','daily_liquidity.csv','liquidity_monthly.csv','risk_free.csv','sources.json','liquidity_sources.json']

def main():
    for name in ['data','output','figures','report','resources','tmp/pdfs','pipeline']:
        (ROOT/name).mkdir(parents=True,exist_ok=True)
    manifest=json.loads((SOURCE/'data/sources.json').read_text(encoding='utf-8'))
    records=[]
    for name in FILES:
        source=SOURCE/'data'/name
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        if name in manifest.get('hashes',{}):
            assert digest==manifest['hashes'][name],name
        dest=ROOT/'data'/name
        if dest.exists():
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==digest,'Refuse to overwrite different frozen inputs'
        else: shutil.copyfile(source,dest)
        records.append({'file':name,'sha256':digest,'bytes':source.stat().st_size,'source':str(source),
                        'matched_prior_manifest':name in manifest.get('hashes',{})})
    provenance={'source':'Module 6 frozen Yahoo Finance/FRED snapshots; real observations, no simulated study inputs',
                'price_cutoff':'2026-10-23','analysis_end':'2026-09-30','new_market_download':False,
                'records':records,'note':'Hashes prove copy integrity, not point-in-time vendor accuracy. Liquidity is recomputed from daily observations in the new study.'}
    (ROOT/'data/provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    official=ROOT.parent/'msds-451/Modules/Module 7 _ Volatility and Market Regimes/assignments/Module 7_ Programming Assignment 3/instructions.md'
    shutil.copyfile(official,ROOT/'resources/assignment.md')
    print('Frozen',len(records),'input files.')

if __name__=='__main__':main()
