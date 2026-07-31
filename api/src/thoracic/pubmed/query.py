from __future__ import annotations
import urllib.parse
ESEARCH_URL='https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'; EFETCH_URL='https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
def build_esearch_params(*,disease_query,journal_query,epdat,api_key):
 p={'db':'pubmed','term':f'(({disease_query}) AND ({journal_query}) AND {epdat})','retmode':'json','retmax':'500','sort':'pub date'}
 if api_key:p['api_key']=api_key
 return p
def build_efetch_url(*,pmids,api_key):
 p={'db':'pubmed','id':','.join(pmids),'retmode':'xml'}
 if api_key:p['api_key']=api_key
 return f'{EFETCH_URL}?{urllib.parse.urlencode(p)}'
def build_journal_query_chunk(journal_terms): return ' OR '.join(f'"{t}"[jour]' for t in journal_terms)
