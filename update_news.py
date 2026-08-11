#!/usr/bin/env python3
import json, re, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from html import unescape

JST = timezone(timedelta(hours=9))
OUT = Path("news.json")
MAX_PER_SOURCE = 8
UA = "InsightBrief/1.1 (+GitHub Actions)"

SOURCES = [
    {
        "category": "DELIVERY",
        "name": "ヤマトホールディングス",
        "url": "https://www.yamato-hd.co.jp/investors/information/info.xml",
        "fallback": "https://www.yamato-hd.co.jp/news/"
    },
    {
        "category": "NEWS",
        "name": "NHKニュース",
        "url": "https://news.web.nhk/n-data/conf/na/rss/cat0.xml",
        "fallback": "https://news.web.nhk/"
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
    enc_match = re.search(br'encoding=["\']([^"\']+)["\']', raw[:200], re.I)
    enc = enc_match.group(1).decode("ascii") if enc_match else "utf-8"
    root = ET.fromstring(raw.decode(enc, errors="replace"))
    rows = []

    for item in root.findall(".//item"):
        title = clean(txt(item, ["title"]))
        link = clean(txt(item, ["link"]))
        desc = clean(txt(item, ["description", "{http://purl.org/rss/1.0/modules/content/}encoded"]))
        date = clean(txt(item, ["pubDate", "{http://purl.org/dc/elements/1.1/}date"]))
        if title and link:
            rows.append((title, link, desc, date))

    if not rows:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for item in root.findall(".//a:entry", ns):
            title = clean(txt(item, ["{http://www.w3.org/2005/Atom}title"]))
            link_el = item.find("{http://www.w3.org/2005/Atom}link")
            link = link_el.get("href", "") if link_el is not None else ""
            desc = clean(txt(item, ["{http://www.w3.org/2005/Atom}summary",
                                    "{http://www.w3.org/2005/Atom}content"]))
            date = clean(txt(item, ["{http://www.w3.org/2005/Atom}updated",
                                    "{http://www.w3.org/2005/Atom}published"]))
            if title and link:
                rows.append((title, link, desc, date))

    out = []
    for i, (title, link, desc, date) in enumerate(rows[:MAX_PER_SOURCE]):
        if src["name"] == "NHKニュース":
            summary = desc[:180] if desc else "NHKの主要ニュース。見出しと要点だけ確認します。"
            why = "今日の一般ニュースとして押さえておきたい主要トピックです。"
            importance = "一般"
            relation = "社会"
        elif src["category"] == "DELIVERY":
            summary = desc[:200] if desc else "物流・宅配に関する公式発表。仕事との関係を確認します。"
            why = "軽配送の仕事や宅配業界の流れをつかむための情報です。"
            importance = "仕事"
            relation = "高"
        else:
            summary = desc[:180] if desc else "AIに関する公式発表。実際の使い方が変わるかを確認します。"
            why = "仕事・学習・情報整理で実際に使える変化かを見るためです。"
            importance = "AI"
            relation = "中"

        out.append({
            "id": f"{src['category'].lower()}-{src['name']}-{i}",
            "category": src["category"],
            "source": src["name"],
            "title": title,
            "summary": summary,
            "published": date,
            "url": link,
            "importance": importance,
            "relation": relation,
            "why": why
        })
    return out

def select_brief(stories):
    buckets = {"DELIVERY": [], "NEWS": [], "AI": []}
    for s in stories:
        buckets.setdefault(s.get("category", "NEWS"), []).append(s)

    selected = []
    # 朝刊の基本構成：仕事3、一般ニュース3、AI2
    for cat, n in [("DELIVERY", 3), ("NEWS", 3), ("AI", 2)]:
        selected.extend(buckets.get(cat, [])[:n])

    if len(selected) < 8:
        seen = {x.get("id") for x in selected}
        for s in stories:
            if s.get("id") not in seen:
                selected.append(s)
            if len(selected) >= 8:
                break
    return selected[:8]

def main():
    stories, errors = [], []
    for src in SOURCES:
        try:
            stories.extend(parse_feed(fetch(src["url"]), src))
        except Exception as e:
            errors.append({
                "source": src["name"],
                "error": str(e),
                "fallback": src["fallback"]
            })

    payload = {
        "updated_at": datetime.now(JST).isoformat(timespec="minutes"),
        "edition": "AUTO v2",
        "stories": select_brief(stories),
        "errors": errors
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload['stories'])} selected stories to {OUT}")
    if errors:
        print("Feed errors:", errors)

if __name__ == "__main__":
    main()
