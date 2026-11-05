"""Capture public official guides, retaining complete visible text and original bytes."""
from __future__ import annotations

import asyncio
from html.parser import HTMLParser
import io
from pathlib import Path
import re
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from . import journalcontext as jc
from .packagefreeze import _sha256
from .readiness import atomic_json


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "template"}: self.skip+=1
        if not self.skip and tag in {"p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "br"}: self.parts.append("\n")
    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "template"}: self.skip=max(0,self.skip-1)
        if not self.skip and tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}: self.parts.append("\n")
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def normalize(text): return re.sub(r"\s+", " ", str(text)).strip()


def extract(raw: bytes, suffix: str):
    reader=None
    if raw.startswith(b"%PDF") or suffix==".pdf":
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
        try:
            document=PdfReader(io.BytesIO(raw))
            text="\n\n".join(f"[Page {i+1}]\n"+(p.extract_text() or "") for i,p in enumerate(document.pages))
        except PyPdfError as exc: raise ValueError("Official PDF could not be read; obtain a genuine readable/downloaded source") from exc
        if len(normalize(text))<80: raise ValueError("PDF has no usable text; render/OCR and register the actual complete source, do not treat extraction success as readable instructions")
        return ".pdf",text,None
    encoding=re.search(br'charset=["\x27]?([A-Za-z0-9_-]+)',raw[:5000])
    try: decoded=raw.decode(encoding.group(1).decode() if encoding else "utf-8-sig")
    except (UnicodeDecodeError,LookupError):
        try:
            from charset_normalizer import from_bytes
            best=from_bytes(raw).best()
            if best is None: raise ValueError("Guide character encoding unresolved; register a real readable export")
            decoded=str(best)
        except ImportError as exc: raise ValueError("Non-UTF8 guide needs charset-normalizer or a genuine UTF8 browser export") from exc
    if suffix in {".html", ".htm"} or re.search(r"<html\b|<!doctype\s+html",decoded[:2000],re.I):
        parser=VisibleText();parser.feed(decoded)
        text="\n".join(x.strip() for x in "".join(parser.parts).splitlines() if x.strip())
        try:
            import trafilatura
            reader=trafilatura.extract(decoded,include_tables=True,include_links=True,favor_recall=True)
        except ImportError: pass  # Complete visible text remains usable with stdlib only.
        suffix=".html"
    else: text=decoded;suffix=".txt"
    if len(normalize(text))<80 or (len(normalize(text))<1200 and re.search(
            r"just a moment|verify you are human|access denied|enable javascript|checking your browser|captcha",text,re.I)):
        raise ValueError("Empty/challenge/script-only guide page; use the browser fallback or register its genuine official download")
    return suffix,text,reader


def download(url):
    request=Request(url,headers={"User-Agent":"MedpaperGuide/1.0 (+public author-instructions retrieval)","Accept":"text/html,application/pdf,text/plain;q=0.9"})
    with urlopen(request,timeout=35) as response:
        return response.read(),response.geturl(),response.headers.get_content_type()


async def browser_download(url):
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    except ImportError as exc:
        raise ValueError("Crawl4AI is optional and unavailable. Use the available Codex browser, save the official page/download, then journal.py register; no cloud account or fabricated snapshot is required") from exc
    async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as crawler:
        result=await crawler.arun(url=url,config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS,page_timeout=35000))
        if not result.success or (result.status_code and result.status_code>=400):
            raise ValueError("Browser could not obtain public instructions: "+str(result.error_message))
        return result.html.encode("utf-8"),getattr(result,"redirected_url",None) or url,"text/html"


def capture(project, url, *, file=None, mode="auto", why="", retrieved_at=None):
    context=jc.current(project);jc.allowed_url(project,url)
    if file is not None:
        if len(why.strip())<20: raise ValueError("Describe the actual official/browser/user source; registration is not a claim of an HTTP fetch")
        if not retrieved_at: raise ValueError("Provide the actual --retrieved-at date for a registered source; registration does not prove a new web fetch")
        from datetime import datetime,timezone
        parsed=datetime.fromisoformat(retrieved_at)
        retrieved_at=parsed.replace(tzinfo=timezone.utc).isoformat() if parsed.tzinfo is None else parsed.isoformat()
        raw=Path(file).read_bytes(); final=url; kind="registered"; suffix=Path(file).suffix.lower()
    else:
        kind="http"; suffix=Path(urlparse(url).path).suffix.lower()
        try:
            if mode=="browser": raise ValueError("browser explicitly selected")
            raw,final,mime=download(url)
            if mime=="application/pdf": suffix=".pdf"
            elif mime=="text/html": suffix=".html"
            extract(raw,suffix)  # Challenge/empty 200 responses must also trigger fallback.
        except (OSError,ValueError) as exc:
            if mode=="http": raise ValueError(f"Guide acquisition failed: {exc}") from exc
            try: raw,final,mime=asyncio.run(browser_download(url));kind="browser";suffix=".html"
            except (OSError,ValueError) as fallback: raise ValueError(f"Direct acquisition: {exc}; browser: {fallback}") from fallback
    jc.allowed_url(project,final)
    suffix,text,reader=extract(raw,suffix)
    key=jc.digest(url)[:16]; root=project/"08_submission/cache/guides"
    root.mkdir(parents=True,exist_ok=True)
    source={"id":key,"context_id":context["context_id"],"url":url,"final_url":final,
            "fetched_at":retrieved_at or jc.now(),"registered_at":jc.now(),"mode":kind,"registration_basis":why,
            "raw":f"08_submission/cache/guides/{key}.source{suffix}","text":f"08_submission/cache/guides/{key}.txt"}
    # Preserve exact original bytes and complete visible text. Reader text is optional,
    # never the only retained evidence and never a substitute for the complete guide.
    for rel,value in ((source["raw"],raw),(source["text"],text.encode("utf-8"))):
        path=project/rel; temp=path.with_suffix(path.suffix+".tmp");temp.write_bytes(value);temp.replace(path)
    source.update(raw_sha256=_sha256(project/source["raw"]),text_sha256=_sha256(project/source["text"]))
    if reader:
        path=root/(key+".reader.md");path.write_text(reader,encoding="utf-8");source["reader"]=path.relative_to(project).as_posix()
    old=context["sources"].get(key,{})
    if old.get("raw_sha256")!=source["raw_sha256"] or old.get("text_sha256")!=source["text_sha256"]:
        context.pop("seal",None)
    context["sources"][key]=source;atomic_json(project/jc.CONTEXT,context)
    target=jc.load(project,jc.TARGET)
    if url==target.get("guidelines_url"):
        target["guidelines_fetched_at"]=source["fetched_at"][:10];atomic_json(project/jc.TARGET,target)
    return source


def fetch_csl(project, style_id):
    """Resolve dependent styles to their actual independent parent; no style guessing."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*",style_id): raise ValueError("Use an exact CSL repository style id")
    context=jc.current(project); visited=set(); chosen=style_id; records=[]
    while True:
        if style_id in visited: raise ValueError("CSL independent-parent cycle")
        visited.add(style_id)
        url=f"https://raw.githubusercontent.com/citation-style-language/styles/v1.0.2/{style_id}.csl"
        raw,final,mime=download(url)
        if not final.startswith("https://raw.githubusercontent.com/citation-style-language/styles/"):
            raise ValueError("Unexpected CSL repository redirect")
        try: root=ET.fromstring(raw)
        except ET.ParseError as exc: raise ValueError("Invalid downloaded CSL XML; no default style substituted") from exc
        ns="{http://purl.org/net/xbiblio/csl}"
        if root.tag!=ns+"style": raise ValueError("Downloaded file is not a CSL style")
        path=project/f"08_submission/cache/csl/{style_id}.csl";path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        row={"file":path.relative_to(project).as_posix(),"sha256":_sha256(path),"url":url,"chosen_style":chosen}
        context["assets"]["csl:"+style_id]=row;records.append(row)
        parent=next((x.get("href") for x in root.iter(ns+"link") if x.get("rel")=="independent-parent"),None)
        if not parent:
            if root.find(ns+"citation") is None or root.find(ns+"bibliography") is None: raise ValueError("Independent CSL lacks citation/bibliography rules")
            break
        style_id=Path(urlparse(parent).path).name.removesuffix(".csl")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*",style_id): raise ValueError("Invalid CSL parent identifier")
    context.pop("seal",None);atomic_json(project/jc.CONTEXT,context)
    return records[-1]


def register_template(project, file, url, why, retrieved_at):
    """Retain an actual official Word template locally; never synthesize one as official."""
    from datetime import datetime
    from docx import Document
    jc.allowed_url(project,url);context=jc.current(project)
    file=Path(file)
    if file.suffix.lower()!=".docx" or len(why.strip())<20: raise ValueError("Register the genuine official DOCX and its actual download basis")
    datetime.fromisoformat(retrieved_at)
    try: Document(file)
    except Exception as exc: raise ValueError("Official Word template is unreadable; no default substituted") from exc
    key="template:"+jc.digest(url)[:16]
    output=project/"08_submission/cache/templates"/(jc.digest(url)[:16]+".docx")
    output.parent.mkdir(parents=True,exist_ok=True);raw=file.read_bytes()
    temp=output.with_suffix(".tmp");temp.write_bytes(raw);temp.replace(output)
    row={"file":output.relative_to(project).as_posix(),"sha256":_sha256(output),"url":url,
         "mode":"registered_official_template","retrieved_at":retrieved_at,"registration_basis":why}
    context["assets"][key]=row;context.pop("seal",None);atomic_json(project/jc.CONTEXT,context)
    return row
