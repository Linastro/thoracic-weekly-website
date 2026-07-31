from __future__ import annotations
import xml.etree.ElementTree as ET

_MONTHS = {'Jan':'01','Feb':'02','Mar':'03','Apr':'04','May':'05','Jun':'06',
           'Jul':'07','Aug':'08','Sep':'09','Oct':'10','Nov':'11','Dec':'12'}


def _txt(e):
    return ''.join(e.itertext()).strip() if e is not None else None


def _ymd_iso(year, month, day):
    """把 (year, month, day) 转 ISO `YYYY-MM-DD`;任一字段缺失返回 None。"""
    if not year:
        return None
    m = _MONTHS.get(month, month) if month else None
    d = day.zfill(2) if day else None
    parts = [year]
    if m:
        parts.append(m.zfill(2))
    if d:
        parts.append(d)
    return '-'.join(parts) if len(parts) >= 2 else None


def _article_date_iso(article):
    """优先取 `<ArticleDate DateType="Electronic">`,否则 PubDate,返回 ISO。"""
    for ad in article.findall('.//ArticleDate'):
        if ad.attrib.get('DateType') == 'Electronic':
            iso = _ymd_iso(_txt(ad.find('Year')), _txt(ad.find('Month')), _txt(ad.find('Day')))
            if iso:
                return iso
    iso = _ymd_iso(_txt(article.find('.//PubDate/Year')),
                   _txt(article.find('.//PubDate/Month')),
                   _txt(article.find('.//PubDate/Day')))
    return iso


def parse_pubmed_xml(xml_str):
    root = ET.fromstring(xml_str)
    out = []
    for a in root.findall('.//PubmedArticle'):
        pmid = _txt(a.find('.//PMID'))
        title = _txt(a.find('.//ArticleTitle')) or ''

        absx = [_txt(x) or '' for x in a.findall('.//Abstract/AbstractText')]
        abstract = ' '.join(x for x in absx if x) or None

        authors = []
        aff = []
        for au in a.findall('.//AuthorList/Author'):
            name = ' '.join(filter(None, [_txt(au.find('ForeName')), _txt(au.find('LastName'))])) \
                or _txt(au.find('CollectiveName'))
            if name:
                authors.append(name)
            infos = au.findall('./AffiliationInfo/Affiliation')
            aff.append(_txt(infos[0]) if infos else None)

        journal = (_txt(a.find('.//Journal/Title'))
                   or _txt(a.find('.//MedlineJournalInfo/MedlineTA'))
                   or _txt(a.find('.//Journal/ISOAbbreviation')))
        jabr = _txt(a.find('.//Journal/ISOAbbreviation'))

        doi = None
        for x in a.findall('.//ArticleId'):
            if x.attrib.get('IdType') == 'doi':
                doi = _txt(x)

        types = [_txt(x) for x in a.findall('.//PublicationType') if _txt(x)]

        pubdate = ' '.join(filter(None, [_txt(a.find('.//PubDate/Year')),
                                          _txt(a.find('.//PubDate/Month')),
                                          _txt(a.find('.//PubDate/Day'))]))

        # epdat:优先 PubMed 入库日(`PubStatus=pubmed`),否则 ArticleDate Electronic,再否则 PubDate
        ep = None
        for h in a.findall('.//PubmedData/History/PubMedPubDate'):
            if h.attrib.get('PubStatus') == 'pubmed':
                ep = _ymd_iso(_txt(h.find('Year')), _txt(h.find('Month')), _txt(h.find('Day')))
                break
        if not ep:
            ep = _article_date_iso(a)

        out.append({
            'pmid': pmid,
            'title': title,
            'abstract': abstract,
            'authors': authors,
            'affiliations': aff,
            'journal': journal,
            'journal_abbr': jabr,
            'doi': doi,
            'publication_types': types,
            'pubdate': pubdate,
            'epdat': ep,
        })
    return out


def parse_pubmed_xml_batches(xml_batches):
    out = []
    for x in xml_batches:
        out.extend(parse_pubmed_xml(x))
    return out
