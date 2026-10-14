"""Check publishing invariants for crawler access, page identity, and episode HTML."""
from pathlib import Path
from html.parser import HTMLParser
import json
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.canonicals=[]; self.h1=0; self.schema=False; self.data=''; self.schemas=[]; self.ids=set(); self.fragments=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.add(a['id'])
        if tag=='a' and a.get('href','').startswith('#'):self.fragments.append(a['href'][1:])
        if tag=='h1':self.h1+=1
        if tag=='link' and a.get('rel')=='canonical':self.canonicals.append(a['href'])
        if tag=='script' and a.get('type')=='application/ld+json':self.schema=True;self.data=''
    def handle_data(self,data):
        if self.schema:self.data+=data
    def handle_endtag(self,tag):
        if tag=='script' and self.schema:self.schemas.append(json.loads(self.data));self.schema=False

def main():
    sitemap=ET.parse(ROOT/'sitemap.xml')
    for loc in sitemap.findall('.//{*}loc'):
        route=loc.text.removeprefix('https://mainstdreamers.com')
        p=ROOT/(route.strip('/')+'/index.html' if route!='/' else 'index.html')
        source=p.read_text(); page=Page();page.feed(source)
        assert page.canonicals==[loc.text],p
        assert page.h1==1,p
        assert page.schemas,p
        assert all(not f or f in page.ids for f in page.fragments),(p,page.fragments-page.ids if isinstance(page.fragments,set) else page.fragments)
        if route in ('/','/podcast/'):
            assert '<time datetime=' in source and 'id="episode-schema"' in source,p
    assert 'Sitemap: https://mainstdreamers.com/sitemap.xml' in (ROOT/'robots.txt').read_text()
    assert 'Disallow: /' not in (ROOT/'robots.txt').read_text()
    assert 'noindex' in (ROOT/'404.html').read_text()
    print('SEO publishing checks passed: sitemap routes, canonical URLs, H1s, JSON-LD, fragments, crawlable episodes, robots, and 404')
if __name__=='__main__':main()
