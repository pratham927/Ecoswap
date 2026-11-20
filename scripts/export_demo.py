"""Export a self-contained, offline HTML explorer using computed engine outputs."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ecoswap import EcoSwap
ROOT=Path(__file__).resolve().parents[1]

def main():
    m=EcoSwap();cases=[]
    for r in m.recipes:
        opts=m.options(r,r['target'])
        for o in opts:
            changed=r if o['fraction']==0 else m.apply(r,r['target'],o['target'],o['fraction'])
            o['adapted_ingredients']=changed['ingredients']
        cases.append({'recipe':r,'options':opts,'footprint':m.footprint(r)})
    payload={'cases':cases,'ingredients':m.ingredients,'results':json.loads((ROOT/'results/summary.json').read_text())}
    template=(ROOT/'scripts/demo_template.html').read_text(encoding='utf-8')
    for key,value in {'__INGREDIENT_COUNT__':len(m.ingredients),**{f'__W_{k.upper()}__':f'{v:g}' for k,v in m.evidence_weights.items()}}.items():
        template=template.replace(key,str(value))
    html=template.replace('__PAYLOAD__',json.dumps(payload,ensure_ascii=False).replace('</','<\\/'))
    (ROOT/'EcoSwap_demo.html').write_text(html,encoding='utf-8')
    print('Exported EcoSwap_demo.html')

if __name__=='__main__':main()
