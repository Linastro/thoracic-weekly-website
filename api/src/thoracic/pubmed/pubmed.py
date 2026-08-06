from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from .dates import edat_clause
from .diseases import DISEASES
from .journal_terms import load_journal_terms, chunk_journal_terms
from .client import gather_esearch_all, gather_efetch_all
from .parser import parse_pubmed_xml_batches
@dataclass
class SearchDayResult:
 target_date: date
 records: list[dict]
 pmids_by_disease: dict[str,set[str]]
 supplemental_pmids: set[str]
 metadata: dict
async def search_day(*,target_date,api_key=None,journal_index=None,journal_chunk_size=18):
 chunks=chunk_journal_terms(load_journal_terms(),journal_chunk_size)
 p=await gather_esearch_all(chunks,DISEASES,edat_clause(target_date),api_key)
 supp=set()
 allp=set().union(*p.values()) if p else set()
 records=parse_pubmed_xml_batches(await gather_efetch_all(allp,api_key)) if allp else []
 for r in records:r['disease_hint']=next((d for d,v in p.items() if r['pmid'] in v),None)
 return SearchDayResult(target_date,records,p,supp,{'edat':edat_clause(target_date)})
if __name__=='__main__':
 import asyncio,os
 from .dates import previous_us_eastern_day
 t=previous_us_eastern_day(); r=asyncio.run(search_day(target_date=t,api_key=os.environ.get('PUBMED_API_KEY'))); print(f'Found {len(r.records)} records')
