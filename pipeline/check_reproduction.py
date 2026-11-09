"""Reproduce from source plus raw snapshots in a clean, local temporary folder."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def main():
    # Unique directory per run: no recursive deletion or stale-output reuse.
    import tempfile
    parent=ROOT/'tmp';parent.mkdir(exist_ok=True)
    clean=Path(tempfile.mkdtemp(prefix='clean-reproduction-',dir=parent))
    for folder in ['pipeline','data','tests','resources']:(clean/folder).mkdir()
    for file in ['run.py','requirements.txt']:
        shutil.copyfile(ROOT/file,clean/file)
    for folder in ['pipeline','tests']:
        for source in (ROOT/folder).glob('*.py'):shutil.copyfile(source,clean/folder/source.name)
    for source in (ROOT/'resources').glob('*.md'):shutil.copyfile(source,clean/'resources'/source.name)
    provenance=json.loads((ROOT/'data/provenance.json').read_text())
    for record in provenance['records']:
        shutil.copyfile(ROOT/'data'/record['file'],clean/'data'/record['file'])
    shutil.copyfile(ROOT/'data/provenance.json',clean/'data/provenance.json')
    result=subprocess.run([sys.executable,'run.py'],cwd=clean,capture_output=True,text=True)
    (ROOT/'output/clean_reproduction_log.txt').write_text(result.stdout+'\nSTDERR\n'+result.stderr)
    if result.returncode:raise RuntimeError('Clean run failed; see output/clean_reproduction_log.txt')
    comparisons=[]
    for original in sorted((ROOT/'output').glob('*.csv')):
        repeated=clean/'output'/original.name
        assert repeated.exists(),original.name
        a=pd.read_csv(original);b=pd.read_csv(repeated)
        pd.testing.assert_frame_equal(a,b,check_exact=False,rtol=1e-8,atol=1e-10)
        comparisons.append({'file':original.name,'numerically_equal':True,
            'byte_identical':hashlib.sha256(original.read_bytes()).digest()==hashlib.sha256(repeated.read_bytes()).digest()})
    for file in ['monthly_prices_usd.csv','monthly_observation_dates.csv']:
        assert (ROOT/'data'/file).read_bytes()==(clean/'data'/file).read_bytes()
    assert json.loads((clean/'output/verification.json').read_text())['passed']
    assert json.loads((ROOT/'output/bootstrap.json').read_text())==json.loads((clean/'output/bootstrap.json').read_text())
    record={'passed':True,'method':'Only source files and raw inputs copied. No precomputed outputs or derived monthly panels copied.',
            'source_folder':str(clean.relative_to(ROOT)),'csv_outputs':comparisons,'derived_input_panels_equal':True,
            'conditional_bootstrap_equal':True,'full_temporal_verification_passed':True,
            'note':'The existing installed Python environment supplies dependencies; no sibling assignment is read by the reproduced run.'}
    (ROOT/'output/clean_reproduction.json').write_text(json.dumps(record,indent=2))
    print('Clean reproduction passed:',len(comparisons),'CSV files and two prepared input panels.')

if __name__=='__main__':main()
