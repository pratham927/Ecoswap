"""Optional refresh of public source files; shipped snapshots work offline.

Downloaded data is checked against the shipped SHA-256 manifest. A changed
upstream file is written as .changed and requires manual review, not silent use.
"""
import concurrent.futures
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw'
SOURCES={
 'agribalyse_api.json':'https://data.ademe.fr/data-fair/api/v1/datasets/agribalyse-31-synthese/lines?size=10000',
 'agribalyse_api_meta.json':'https://data.ademe.fr/data-fair/api/v1/datasets/agribalyse-31-synthese',
 'nodes.csv':'https://raw.githubusercontent.com/lamypark/FlavorGraph/master/input/nodes_191120.csv',
 'edges.csv':'https://raw.githubusercontent.com/lamypark/FlavorGraph/master/input/edges_191120.csv',
 'train_subs.pkl':'https://dl.fbaipublicfiles.com/gismo/train_comments_subs.pkl',
 'val_subs.pkl':'https://dl.fbaipublicfiles.com/gismo/val_comments_subs.pkl',
 'test_subs.pkl':'https://dl.fbaipublicfiles.com/gismo/test_comments_subs.pkl',
 'recipe_information.csv':'https://raw.githubusercontent.com/RaoulKalisvaart/green-recommender-systems/main/data/recipe-emissions/recipe_information.csv',
 'FlavorGraph_LICENSE.txt':'https://raw.githubusercontent.com/lamypark/FlavorGraph/master/LICENSE',
 'GISMo_LICENSE.md':'https://raw.githubusercontent.com/facebookresearch/gismo/main/LICENSE.md',
}

def main():
    RAW.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'data/manifest.json').read_text())['raw_sha256']
    def fetch(item):
        name,url=item
        existing=RAW/name
        if existing.exists() and hashlib.sha256(existing.read_bytes()).hexdigest()==manifest.get(name):return name,'already verified'
        try:
            with urllib.request.urlopen(url,timeout=60) as response:payload=response.read()
            digest=hashlib.sha256(payload).hexdigest()
            if digest!=manifest.get(name):
                (RAW/(name+'.changed')).write_bytes(payload)
                return name,'UPSTREAM CHANGED: review .changed before rebuilding'
            existing.write_bytes(payload)
            return name,'downloaded and verified'
        except Exception as exc:return name,f'FAILED: {exc}'
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for name,status in pool.map(fetch,SOURCES.items()):print(f'{name}: {status}')

if __name__=='__main__':main()
