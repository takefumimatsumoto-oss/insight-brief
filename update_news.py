#!/usr/bin/env python3
import json, re, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from html import unescape

JST = timezone(timedelta(hours=9))
OUT = Path("news.json")
MAX_PER_SOURCE = 5
UA = "InsightBrief/1.0 (+GitHub Actions)"

SOURCES = [
    {
        "category": "DELIVERY",
        "name": "ヤマトホールディングス",
        "url": "https://www.yamato-hd.co.jp/news/rss.xml",
        "fallback": "https://www.yamato-hd.co.jp/news/"
    },
    {
        "category": "NEWS",
        "name": "日本銀行",
        "url": "https://www.boj.or.jp/rss/whatsnew.xml",
        "fallback": "https://www.boj.or.jp/"
    },
    {
        "category": "NEWS",
        "name": "国土交通省",
        "url": "https://www.mlit.go.jp/report/press/rss.xml",
        "fallback": "https://www.mlit.go.jp/report/press/"
    },
    {
        "category": "AI",
        "name": "OpenAI",
        "url": "https://openai.com/news/rss.xml",
        "fallback": "https://openai.com/news/"
    },
]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def txt(node, names):
    for name in names:
        el = node.find(name)
        if el is not None and el.text:
            return el.text.strip()
    return ""

def clean(s):
    s = unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()

def parse_feed(raw, src):
    root = ET.fromstring(raw)
    rows = []
    # RSS
    for item in root.findall(".//item"):
        title = clean(txt(item, ["title"]))
        link = clean(txt(item, ["link"]))
        desc = clean(txt(item, ["description", "{http://purl.org/rss/1.0/modules/content/}encoded"]))
        date = clean(txt(item, ["pubDate", "{http://purl.org/dc/elements/1.1/}date"]))
        if title and link:
            rows.append((title, link, desc, date))
    # Atom
    if not rows:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for item in root.findall(".//a:entry", ns):
            title = clean(txt(item, ["{http://www.w3.org/2005/Atom}title"]))
            link_el = item.find("{http://www.w3.org/2005/Atom}link")
            link = link_el.get("href", "") if link_el is not None else ""
            desc = clean(txt(item, ["{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content"]))
            date = clean(txt(item, ["{http://www.w3.org/2005/Atom}updated", "{http://www.w3.org/2005/Atom}published"]))
            if title and link:
                rows.append((title, link, desc, date))
    out = []
    for i, (title, link, desc, date) in enumerate(rows[:MAX_PER_SOURCE]):
        out.append({
            "id": f"{src['category'].lower()}-{src['name']}-{i}",
            "category": src["category"],
            "source": src["name"],
            "title": title,
            "summary": desc[:240] if desc else "公式発表。詳細は出典を確認してください。",
            "published": date,
            "url": link,
            "importance": "要確認",
            "relation": "要確認",
            "why": "公式情報の新着候補です。Insight Briefで重要性と自分との関係を確認します。"
        })
    return out

def main():
    stories, errors = [], []
    for src in SOURCES:
        try:
            stories.extend(parse_feed(fetch(src["url"]), src))
        except Exception as e:
            errors.append({"source": src["name"], "error": str(e), "fallback": src["fallback"]})
    payload = {
        "updated_at": datetime.now(JST).isoformat(timespec="minutes"),
        "edition": "AUTO v1",
        "stories": stories,
        "errors": errors
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(stories)} stories to {OUT}")
    if errors:
        print("Feed errors:", errors)

if __name__ == "__main__":
    main()
