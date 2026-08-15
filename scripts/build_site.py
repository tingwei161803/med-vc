# /// script
# requires-python = ">=3.11"
# ///
"""Generate the static-site data layer (docs/data/data.js) from the merged dataset.

Projects data/all-entities.json + taxonomy.json into a trimmed, render-ready
window.MED_VC global plus window.SITE_META / window.SITE_PAGES for the multipage
shell. Bilingual labels come from taxonomy.json (label_zh); entity free-text
(summary/thesis) stays in its researched language.

Run:  uv run scripts/build_site.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "data" / "data.js"

ent = json.loads((DATA / "all-entities.json").read_text("utf-8"))
tax = json.loads((DATA / "taxonomy.json").read_text("utf-8"))
stats = json.loads((DATA / "stats.json").read_text("utf-8"))


def optional(name, fallback):
    """Company data is built by a separate script and may not exist yet.

    The site must build from the investor half alone — otherwise a failure in
    scripts/build_companies.py takes the whole site down with it.
    """
    p = DATA / name
    return json.loads(p.read_text("utf-8")) if p.exists() else fallback


comp = optional("all-companies.json", [])
links = optional("links.json", {"investor_to_company": {}, "company_to_investor": {}})
cstats = optional("company-stats.json", {"total": 0})


def vocab(key, label_en="label_en", label_zh="label_zh"):
    return [{"slug": x["slug"], "en": x.get(label_en, x["slug"]), "zh": x.get(label_zh, x.get(label_en, x["slug"]))}
            for x in tax[key]]


TAXONOMY = {
    "types": vocab("types"),
    "sectors": vocab("sectors"),
    "modalities": [{"slug": m["slug"], "en": m["label_en"], "zh": m["label_en"]} for m in tax["modalities"]],
    "indications": [{"slug": i["slug"], "en": i["label_en"], "zh": i["label_en"]} for i in tax["indications"]],
    "stages": [{"slug": s["slug"], "en": s["label_en"], "zh": s.get("label_en")} for s in tax["stages"]],
    "regions": vocab("regions"),
    "backerKinds": vocab("backer_kinds"),
    "backerRels": vocab("backer_relationships"),
    "companyStatus": vocab("company_status"),
    "devStages": vocab("development_stages"),
}


def money(m):
    if not isinstance(m, dict):
        return None
    raw = m.get("raw")
    return raw or None


def trim(e):
    """Keep only fields the site renders; flatten money to display strings."""
    name = e.get("name", {})
    strat = e.get("strategy", {}) or {}
    ls = e.get("lifesci", {}) or {}
    cap = e.get("capital", {}) or {}
    tr = e.get("track_record", {}) or {}
    prog = e.get("program", {}) or {}
    # backers ship as compact triples: [name, kind, relationship]. Positional
    # rather than keyed because this repeats up to a few hundred times and the
    # keys would cost more than the values.
    backers = [[b.get("name", ""), b.get("kind", "other"), b.get("relationship", "")]
               for b in (e.get("backing", {}) or {}).get("backers", []) or []
               if b.get("name")]
    out = {
        "id": e["id"],
        "name": {"en": name.get("en", ""), "local": name.get("local", "")},
        "type": e.get("type"),
        "region": e.get("region"),
        "country": e.get("country", ""),
        "city": e.get("hq_city", ""),
        "founded": e.get("founded_year"),
        "status": e.get("status", ""),
        "website": e.get("website", ""),
        "conf": e.get("confidence", ""),
        "sectors": strat.get("sector_focus", []) or [],
        "stages": strat.get("stages", []) or [],
        "modalities": ls.get("modalities", []) or [],
        "indications": ls.get("indications", []) or [],
        "thesis": strat.get("thesis", ""),
        "summary": (e.get("summary", {}) or {}).get("en", ""),
        "check": (strat.get("check_size", {}) or {}).get("raw"),
        "aum": money(cap.get("aum")),
        "fund": money(cap.get("current_fund")),
        "backers": backers,
        "portfolio": tr.get("portfolio_count"),
        "notable": [n.get("company", "") for n in (tr.get("notable_investments", []) or [])[:6] if n.get("company")],
        "program": {
            "invest": money(prog.get("investment")),
            "equity": prog.get("equity_taken_pct"),
            "lab": prog.get("lab_space"),
            "url": prog.get("application_url"),
        } if prog else None,
        "sources": [{"url": s.get("url", ""), "title": s.get("title", ""), "quote": s.get("quote", "")}
                    for s in (e.get("sources", []) or [])[:6] if s.get("url")],
    }
    # drop empty/None to shrink payload
    clean = {}
    for k, v in out.items():
        if v in (None, "", [], {}):
            continue
        clean[k] = v
    if clean.get("program") and not any(clean["program"].get(x) for x in ("invest", "equity", "lab", "url")):
        clean.pop("program", None)
    return clean


def trim_company(c):
    """Same shape discipline as trim(): only what the page renders.

    Investors ship as positional triples [name, entity_id, role]. entity_id is
    null when that investor is not in the directory — the site renders those as
    plain text rather than a dead link, which is the honest rendering of "we
    know who funded this, we just haven't profiled them".
    """
    name = c.get("name", {})
    p = c.get("profile", {}) or {}
    f = c.get("funding", {}) or {}
    lr = f.get("last_round") or {}
    ex = f.get("exit") or {}
    out = {
        "id": c["id"],
        "name": {"en": name.get("en", ""), "local": name.get("local", "")},
        "cat": c.get("category", ""),
        "sectors": c.get("sectors", []) or [],
        "region": c.get("region", ""),
        "country": c.get("country", ""),
        "city": c.get("hq_city", ""),
        "founded": c.get("founded_year"),
        "status": c.get("status", ""),
        "website": c.get("website", ""),
        "conf": c.get("confidence", ""),
        "what": p.get("what", ""),
        "dev": p.get("development_stage", ""),
        "lead": p.get("lead_asset", ""),
        "modalities": p.get("modalities", []) or [],
        "indications": p.get("indications", []) or [],
        "reg": [[r.get("body", ""), r.get("kind", ""), r.get("item", ""), r.get("year")]
                for r in (p.get("regulatory") or [])],
        "raised": money(f.get("total_raised")),
        "val": money(f.get("valuation")),
        "unicorn": bool(f.get("unicorn")) or None,
        "last": {"stage": lr.get("stage", ""), "date": lr.get("date", ""),
                 "amount": money(lr.get("amount"))} if lr else None,
        "inv": [[i.get("name", ""), i.get("entity_id"), i.get("role", "")]
                for i in (f.get("investors") or []) if i.get("name")],
        "exit": {"type": ex.get("type", ""), "year": ex.get("year"),
                 "acquirer": ex.get("acquirer", ""), "value": money(ex.get("value")),
                 "ticker": ex.get("ticker", "")} if ex else None,
        "summary": (c.get("summary", {}) or {}).get("en", ""),
        "sources": [{"url": s.get("url", ""), "title": s.get("title", ""), "quote": s.get("quote", "")}
                    for s in (c.get("sources", []) or [])[:6] if s.get("url")],
    }
    clean = {}
    for k, v in out.items():
        if v in (None, "", [], {}):
            continue
        clean[k] = v
    if clean.get("last") and not any(clean["last"].values()):
        clean.pop("last", None)
    if clean.get("exit") and not any(clean["exit"].values()):
        clean.pop("exit", None)
    return clean


entities = [trim(e) for e in ent]
# sort: confidence (high first) then region then name — stable, nice default order
_rank = {"high": 0, "medium": 1, "low": 2}
entities.sort(key=lambda e: (_rank.get(e.get("conf"), 3), e.get("region", ""), e.get("name", {}).get("en", "").lower()))

companies = [trim_company(c) for c in comp]
companies.sort(key=lambda c: (_rank.get(c.get("conf"), 3), c.get("region", ""), c.get("name", {}).get("en", "").lower()))

# Only the investor -> company direction ships as a lookup table. The reverse
# is already inside each company's `inv` triples, so shipping it too would be
# paying twice for the same edges.
i2c = {k: v for k, v in (links.get("investor_to_company") or {}).items() if v}
# ...except for edges the investor asserted and the company record does not
# mention. Those exist only in the link table, so the company page would show
# an investor list missing rows the investor page shows. Fold them in.
_from_company = {c["id"]: {i[1] for i in c.get("inv", []) if i[1]} for c in companies}
c2i_extra = {}
for cid, invs in (links.get("company_to_investor") or {}).items():
    extra = sorted(set(invs) - _from_company.get(cid, set()))
    if extra:
        c2i_extra[cid] = extra

MED_VC = {
    "entities": entities,
    "companies": companies,
    "links": {"i2c": i2c, "c2iExtra": c2i_extra},
    "taxonomy": TAXONOMY,
    "stats": {
        "total": stats["total"],
        "by_region": stats["by_region"],
        "by_type": stats["by_type"],
        "by_sector": stats["by_sector"],
        "by_modality": stats.get("by_modality", {}),
        "by_indication": stats.get("by_indication", {}),
        "by_backer_kind": stats.get("by_backer_kind", {}),
        "by_confidence": stats["by_confidence"],
        "sources": sum(len(e.get("sources", [])) for e in ent),
        # The methodology page used to hardcode these and they went stale the
        # moment the dataset grew. Derive them so the page can never lie.
        "quoted": sum(1 for e in ent if any(s.get("quote") for s in e.get("sources") or [])),
    },
    "companyStats": cstats,
}

SITE_META = {
    "title": {"en": "med-vc", "zh": "med-vc"},
    "subtitle": {
        "en": "A global directory of medical & biomedical venture investors — and the companies they fund",
        "zh": "全球醫療 / 生醫創投名錄 —— 以及它們投資的公司",
    },
    "repo": "tingwei161803/med-vc",
}

# Hardcoding these went stale the moment the dataset grew. Derive them.
_N_INV = f"{stats['total']:,}"
_N_CO = f"{cstats.get('total', 0):,}"
_N_REGION = len(stats["by_region"])

SITE_PAGES = [
    {"slug": "home", "layout": "hub", "icon": "home",
     "title": {"en": "Overview", "zh": "總覽"},
     "subtitle": {"en": f"{_N_INV} medical & biomedical investors and {_N_CO} companies across {_N_REGION} regions",
                  "zh": f"{_N_REGION} 個地區、{_N_INV} 家醫療生醫投資機構與 {_N_CO} 家新創"}},
    {"slug": "directory", "layout": "directory", "icon": "travel_explore",
     "title": {"en": "Investors", "zh": "投資機構"},
     "subtitle": {"en": "Filter by region, type, sector, modality, indication & stage — search anything",
                  "zh": "依地區 × 類型 × 子領域 × 治療模式 × 適應症 × 階段篩選,全文搜尋"}},
    {"slug": "companies", "layout": "companies", "icon": "rocket_launch",
     "title": {"en": "Companies", "zh": "新創"},
     "subtitle": {"en": "The medical and biomedical companies these investors fund — every one linked to its backers",
                  "zh": "被這些機構投資的醫療生醫公司 —— 每一家都連得回它的投資人"}},
    {"slug": "analysis", "layout": "analysis", "icon": "monitoring",
     "title": {"en": "Analysis", "zh": "分析"},
     "subtitle": {"en": "The shape of medical venture capital, by the numbers",
                  "zh": "用數字看醫療創投的樣貌"}},
    {"slug": "methodology", "layout": "methodology", "icon": "menu_book",
     "title": {"en": "Methodology", "zh": "方法論"},
     "subtitle": {"en": "How this dataset was built, sourced, and verified",
                  "zh": "資料如何蒐集、溯源與查核"}},
]

payload = (
    "/* Auto-generated by scripts/build_site.py — do not edit by hand. */\n"
    "window.SITE_META = " + json.dumps(SITE_META, ensure_ascii=False) + ";\n"
    "window.SITE_PAGES = " + json.dumps(SITE_PAGES, ensure_ascii=False) + ";\n"
    "window.MED_VC = " + json.dumps(MED_VC, ensure_ascii=False) + ";\n"
)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(payload, "utf-8")
kb = len(payload.encode("utf-8")) / 1024
print(f"wrote {OUT.relative_to(ROOT)} — {len(entities)} entities, {kb:.0f} KB")
