from __future__ import annotations
import json
from pathlib import Path

def load_journal_terms(path: str | None = None) -> list[str]:
    p=Path(path) if path else Path(__file__).resolve().parents[5]/'journal_metrics.json'
    data=json.loads(p.read_text(encoding='utf-8'))
    out=[]
    for item in data.values() if isinstance(data,dict) else data:
        if isinstance(item,dict): out.extend(item.get('pubmed_journal_terms',[]))
    return list(dict.fromkeys(out))
def chunk_journal_terms(terms:list[str], size:int=18)->list[list[str]]:
    if size<=0: raise ValueError('size must be positive')
    return [terms[i:i+size] for i in range(0,len(terms),size)]
