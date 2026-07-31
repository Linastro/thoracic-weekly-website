from __future__ import annotations
import asyncio, os, httpx
from .query import ESEARCH_URL, EFETCH_URL, build_esearch_params, build_efetch_url, build_journal_query_chunk
_semaphore=asyncio.Semaphore(3)
async def _request(client, method, url, **kwargs):
    delay=.1 if kwargs.pop('api_key',None) else .34
    for i in range(4):
        await asyncio.sleep(delay)
        try:
            async with _semaphore:
                r=await client.request(method,url,**kwargs)
            if r.status_code==429 or r.status_code>=500:
                if i<3: await asyncio.sleep(2**i); continue
            r.raise_for_status(); return r
        except (httpx.TransportError,httpx.HTTPStatusError):
            if i==3: raise
            await asyncio.sleep(2**i)
async def esearch_ids(client, *, disease_query, journal_query, epdat, api_key):
 r=await _request(client,'GET',ESEARCH_URL,params=build_esearch_params(disease_query=disease_query,journal_query=journal_query,epdat=epdat,api_key=api_key),api_key=api_key)
 return r.json().get('esearchresult',{}).get('idlist',[])
async def efetch_xml(client, *, pmids, api_key, batch_size=200):
 out=[]
 for i in range(0,len(pmids),batch_size):
  b=pmids[i:i+batch_size]
  if len(b)>200:
   data={'db':'pubmed','id':','.join(b),'retmode':'xml'}
   if api_key:data['api_key']=api_key
   r=await _request(client,'POST',EFETCH_URL,data=data,api_key=api_key)
  else:r=await _request(client,'GET',build_efetch_url(pmids=b,api_key=api_key),api_key=api_key)
  out.append(r.text)
 return out
async def gather_esearch_all(journal_chunks,diseases,epdat,api_key,max_concurrency=3):
 async with httpx.AsyncClient(timeout=httpx.Timeout(60,connect=10)) as c:
  tasks=[(d,chunk) for d in diseases for chunk in journal_chunks]
  vals=await asyncio.gather(*(esearch_ids(c,disease_query=d['query'],journal_query=build_journal_query_chunk(ch),epdat=epdat,api_key=api_key) for d,ch in tasks))
 out={d['slug']:set() for d in diseases}
 for (d,_),v in zip(tasks,vals):out[d['slug']].update(v)
 return out
async def gather_efetch_all(pmids_set,api_key,batch_size=200):
 p=list(pmids_set)
 async with httpx.AsyncClient(timeout=httpx.Timeout(60,connect=10)) as c:return await efetch_xml(c,pmids=p,api_key=api_key,batch_size=batch_size)

def get_api_key(): return os.environ.get('PUBMED_API_KEY')
