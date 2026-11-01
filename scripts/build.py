#!/usr/bin/env python3
"""AI Pulse Weekly: collect official feeds, summarize ES/EN, render HTML."""
import json, os, re, sys, html, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
BERLIN = ZoneInfo("Europe/Berlin")
UA = {"User-Agent": "ai-pulse-weekly/1.0 (+https://github.com/sae-git-azure/ai-pulse-weekly)"}


def local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def strip_html(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def fetch_feed(src):
    req = urllib.request.Request(src["url"], headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())
    items = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        f = {}
        for c in el:
            n = local(c.tag)
            if n == "link":
                f.setdefault("link", c.get("href") or (c.text or "").strip())
            elif n in ("title", "description", "summary", "content", "pubDate", "published", "updated"):
                f.setdefault(n, c.text or "")
        d = parse_date(f.get("pubDate") or f.get("published") or f.get("updated"))
        if f.get("title") and f.get("link") and d:
            items.append({"title": strip_html(f["title"]), "link": f["link"], "date": d,
                          "text": strip_html(f.get("description") or f.get("summary") or f.get("content"))[:1500],
                          "source": src["name"]})
    return items


def meta(page, prop):
    m = (re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"' % prop, page)
         or re.search(r'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="%s"' % prop, page))
    return strip_html(m.group(1)) if m else ""


def fetch_sitemap(src, cutoff):
    """Sources without RSS: read sitemap lastmod, then title/description from each recent page."""
    def get(u):
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
            return r.read()
    root = ET.fromstring(get(src["url"]))
    items = []
    for u in root.iter():
        if local(u.tag) != "url":
            continue
        loc = next((c.text.strip() for c in u if local(c.tag) == "loc"), "")
        d = parse_date(next((c.text for c in u if local(c.tag) == "lastmod"), None))
        if src["path_contains"] in loc and d and d >= cutoff:
            page = get(loc).decode("utf-8", "replace")
            title = meta(page, "og:title")
            pub = parse_date(meta(page, "article:published_time")) or d
            if title and pub >= cutoff:
                items.append({"title": title, "link": loc, "date": pub, "source": src["name"],
                              "text": meta(page, "og:description")[:1500]})
    return items


def ask_model(model, prompt):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    body = json.dumps({"model": model, "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", body, {
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["content"][0]["text"]


def summarize(model, it):
    """Return (summary_es, summary_en); falls back to the feed text if no API/failed."""
    prompt = ("Summarize this official AI news item in 1-2 factual sentences, in English and in Spanish. "
              'Reply ONLY with JSON: {"en": "...", "es": "..."}\n\n'
              f"Title: {it['title']}\nText: {it['text']}")
    try:
        out = ask_model(model, prompt)
        if out:
            j = json.loads(out[out.index("{"): out.rindex("}") + 1])
            return j["es"], j["en"]
    except Exception as e:
        print(f"  summary failed for {it['link']}: {e}", file=sys.stderr)
    fb = it["text"][:280] or it["title"]
    return fb, fb


def main():
    force = "--force" in sys.argv
    now = datetime.now(BERLIN)
    # Cron fires at both 07:00 and 08:00 UTC; only run at 09:xx Berlin (manual runs always pass).
    if not force and os.environ.get("GITHUB_EVENT_NAME") == "schedule" and now.hour != 9:
        print(f"Berlin time is {now:%H:%M}, not 09:xx - skipping."); sys.exit(0)

    cfg = json.loads((ROOT / "config/sources.json").read_text())
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg["window_days"])
    seen, sections = set(), []
    for sec in cfg["sections"]:
        items, notes = [], []
        for src in sec["sources"]:
            try:
                got = (fetch_sitemap(src, cutoff) if src.get("type") == "sitemap"
                       else [i for i in fetch_feed(src) if i["date"] >= cutoff])
                kw = [re.compile(r"\b%s\b" % re.escape(k), re.I) for k in src.get("keywords", [])]
                if kw:
                    got = [i for i in got if any(k.search(i["title"] + " " + i["text"]) for k in kw)]
                items += got
            except Exception as e:
                print(f"Source failed {src['name']}: {e}", file=sys.stderr)
                notes.append(src["name"])
        items.sort(key=lambda i: i["date"], reverse=True)
        picked = []
        for i in items:
            if i["link"] in seen or i["title"].lower() in seen:
                continue
            seen.update((i["link"], i["title"].lower()))
            picked.append(i)
            if len(picked) >= cfg["max_items_per_section"]:
                break
        for i in picked:
            i["es"], i["en"] = summarize(cfg["model"], i)
        sections.append({"cfg": sec, "items": picked, "failed": notes})

    # Edition number: +1 per generated edition
    state_f = ROOT / "archive/state.json"
    state = json.loads(state_f.read_text()) if state_f.exists() else {"edition": 0}
    state["edition"] += 1
    iso = now.isocalendar()
    kw = f"{iso[0]}-KW{iso[1]:02d}"
    stamp = now.strftime("%Y-%m-%d %H:%M %Z")

    def esc(s): return html.escape(s, quote=True)
    body = []
    for s in sections:
        c = s["cfg"]
        cards = "".join(
            f'<article class="card"><h3>{esc(i["title"])}</h3>'
            f'<p lang="es" class="es">{esc(i["es"])}</p><p lang="en" class="en">{esc(i["en"])}</p>'
            f'<div class="meta">{i["date"].astimezone(BERLIN):%d.%m.%Y} · {esc(i["source"])} · '
            f'<a href="{esc(i["link"])}" rel="noopener" target="_blank">'
            f'<span class="es">Fuente original</span><span class="en">Original source</span></a></div></article>'
            for i in s["items"]) or ('<p class="empty"><span class="es">Sin novedades esta semana.</span>'
                                     '<span class="en">No news this week.</span></p>')
        warn = "".join(
            f'<p class="warn">⚠ <span class="es">Fuente no disponible:</span>'
            f'<span class="en">Source unavailable:</span> {esc(n)}</p>' for n in s["failed"])
        body.append(f'<section id="{c["id"]}"><h2><span class="es">{esc(c["name_es"])}</span>'
                    f'<span class="en">{esc(c["name_en"])}</span></h2>{warn}{cards}</section>')

    page = (ROOT / "templates/index.html").read_text()
    for k, v in {"{{SECTIONS}}": "\n".join(body), "{{STAMP}}": stamp,
                 "{{EDITION}}": str(state["edition"]), "{{KW}}": f"KW {iso[1]:02d}/{iso[0]}"}.items():
        page = page.replace(k, v)
    (ROOT / "site").mkdir(exist_ok=True)
    (ROOT / "site/index.html").write_text(page)
    (ROOT / "archive").mkdir(exist_ok=True)
    (ROOT / f"archive/{kw}-v{state['edition']}.html").write_text(page)
    state_f.write_text(json.dumps(state))
    print(f"Built edition {state['edition']} ({kw})")


if __name__ == "__main__":
    main()
