"""Render the final PDF, check layout bounds and validate report consistency."""
from pathlib import Path
import hashlib,json,re
import pandas as pd
import pymupdf
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]

def main():
    path=ROOT/'report/msds451-pa3.pdf';doc=pymupdf.open(path)
    out=ROOT/'tmp/pdfs';out.mkdir(parents=True,exist_ok=True)
    pages=[];thumbs=[]
    for i,page in enumerate(doc):
        text=page.get_text()
        assert len(text)>120,(i+1,'nearly empty page')
        footer=page.get_text(clip=pymupdf.Rect(535,750,570,775)).strip()
        assert footer==str(i+1),(i+1,footer)
        for word in page.get_text('words'):
            x0,y0,x1,y1,*_=word
            assert 47<=x0 and x1<=565 and 17<=y0 and y1<=776,(i+1,word)
        rendered=out/f'page-{i+1:02d}.png'
        page.get_pixmap(matrix=pymupdf.Matrix(1.3,1.3)).save(rendered)
        im=Image.open(rendered).convert('RGB');im.thumbnail((367,475))
        tile=Image.new('RGB',(377,500),'white');tile.paste(im,(5,5));ImageDraw.Draw(tile).text((10,480),f'Page {i+1}',fill='black');thumbs.append(tile)
        pages.append({'page':i+1,'characters':len(text),'text_inside_bounds':True})
    cols=3;rows=(len(thumbs)+cols-1)//cols
    sheet=Image.new('RGB',(cols*377,rows*500),'#dddddd')
    for i,tile in enumerate(thumbs):sheet.paste(tile,((i%cols)*377,(i//cols)*500))
    sheet.save(out/'contact.png')
    text='\n'.join(p.get_text() for p in doc)
    for required in ['From ETF Allocation to Automated Trading','ten-month','DGS3MO','Checkpoint B','References','Appendix A']:
        assert required in text,required
    stats=pd.read_csv(ROOT/'output/metrics.csv',index_col=0)
    for label in ['core','trend','SPY']:
        for term in [f'{stats.loc[label,"cagr"]:.2%}',f'{stats.loc[label,"sharpe"]:.3f}',f'{stats.loc[label,"max_drawdown"]:.2%}']:
            assert term in text,term
    html=(ROOT/'report/msds451-pa3.html').read_text(encoding='utf-8')
    assert '<html lang="en">' in html and html.count('data:image/png;base64,')>=8
    assert not re.search(r'<(?:img|script)[^>]+(?:src|href)=["\']https?://',html)
    assert not any(t in text for t in ['{{','TODO','INSERT RESULTS'])
    result={'passed':True,'pdf_pages':len(doc),'pages':pages,'self_contained_html':True,'metrics_present':True,
            'pdf_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'visual_review':'Rendered pages require separate visual inspection; automated checks alone do not establish visual quality.'}
    (ROOT/'output/artifact_qa.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
