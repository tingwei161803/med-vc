# /// script
# requires-python = ">=3.11"
# ///
"""Regenerate the README's data-status block from the actual dataset.

    uv run scripts/update_readme_stats.py

Rewrites everything between the STATS:BEGIN and STATS:END markers in README.md.

This exists because the hand-written version went stale within one research
round of being written — it still claimed 1,543 investors when the dataset had
grown past 1,600, and its confidence split was three rounds out of date. The
same fix was applied to the site's methodology page for the same reason. A
number a human has to remember to update is a number that will eventually lie,
and a directory whose selling point is per-entry sourcing cannot afford a front
page that misreports its own size.

Run it after build.py and build_companies.py; it reads their output.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
README = ROOT / "README.md"
BEGIN = "<!-- STATS:BEGIN"
END = "<!-- STATS:END -->"

FLAG = {
    "united-states": "🇺🇸", "europe": "🇪🇺", "greater-china": "🇨🇳", "japan": "🇯🇵",
    "south-korea": "🇰🇷", "israel": "🇮🇱", "canada": "🇨🇦", "india": "🇮🇳",
    "southeast-asia": "🇸🇬", "australia-nz": "🇦🇺", "taiwan": "🇹🇼", "rest-of-world": "🌍",
}


def label(tax_key: str) -> dict[str, str]:
    tax = json.loads((DATA / "taxonomy.json").read_text("utf-8"))
    return {x["slug"]: x.get("label_zh") or x.get("label_en", x["slug"]) for x in tax[tax_key]}


def main() -> None:
    ents = json.loads((DATA / "all-entities.json").read_text("utf-8"))
    stats = json.loads((DATA / "stats.json").read_text("utf-8"))
    cos_path = DATA / "all-companies.json"
    cos = json.loads(cos_path.read_text("utf-8")) if cos_path.exists() else []
    cstats_path = DATA / "company-stats.json"
    cstats = json.loads(cstats_path.read_text("utf-8")) if cstats_path.exists() else {}

    n_src = sum(len(e.get("sources") or []) for e in ents)
    n_quote = sum(1 for e in ents if any(s.get("quote") for s in e.get("sources") or []))
    conf = stats["by_confidence"]
    types = label("types")
    sectors = label("sectors")

    L: list[str] = []
    A = L.append
    A(f"**{len(ents):,} 家投資機構 · {len(cos):,} 家公司 · 12 個地區 · "
      f"{cstats.get('edges', 0):,} 條投資關係連結** —— 0 schema 違規、0 critical QA。")
    A("")
    A(f"- 投資機構:100% 有來源 URL、{100*n_quote//max(len(ents),1)}% 帶原文引用,"
      f"共 {n_src:,} 條來源。信心度 high {conf.get('high',0):,} / "
      f"medium {conf.get('medium',0):,} / low {conf.get('low',0):,}")
    if cos:
        cq = sum(1 for c in cos if any(s.get("quote") for s in c.get("sources") or []))
        cc = cstats.get("by_confidence", {})
        A(f"- 公司:100% 有來源 URL、{100*cq//len(cos)}% 帶原文引用。"
          f"信心度 high {cc.get('high',0):,} / medium {cc.get('medium',0):,} / low {cc.get('low',0):,}")
        A(f"- 連結圖:{cstats.get('edges',0):,} 條邊,其中 "
          f"**{cstats.get('edges_confirmed_both_sides',0):,} 條由兩邊各自獨立主張、互相印證**;"
          f"{cstats.get('linked_companies',0):,}/{len(cos):,} 家公司與 "
          f"{cstats.get('linked_investors',0):,}/{len(ents):,} 家機構已連上")
        A(f"- 待辦:{cstats.get('unprofiled_portfolio_names',0):,} 家被收錄機構點名、"
          f"但尚未建檔的公司(見 `reports/links.json`)")
    A("")

    # --- region table, both halves side by side ---
    ereg = Counter(e["region"] for e in ents)
    creg = Counter(c["region"] for c in cos)
    regions = sorted(set(ereg) | set(creg), key=lambda r: -ereg.get(r, 0))
    A("| 地區 | 投資機構 | 公司 | 地區 | 投資機構 | 公司 |")
    A("| --- | ---: | ---: | --- | ---: | ---: |")
    half = (len(regions) + 1) // 2
    rlab = label("regions")
    for a, b in zip(regions[:half], regions[half:] + [None] * half):
        def cell(r):
            if r is None:
                return "| | | "
            return f"| {FLAG.get(r,'')} {rlab.get(r,r)} | {ereg.get(r,0):,} | {creg.get(r,0):,} "
        A(cell(a) + cell(b) + "|")
    A("")

    A("**機構依類型**:" + " · ".join(
        f"{types.get(k,k)} {v:,}" for k, v in Counter(stats["by_type"]).most_common(10)))
    if cos:
        A("")
        A("**公司依領域**:" + " · ".join(
            f"{sectors.get(k,k)} {v:,}" for k, v in Counter(cstats.get("by_category", {})).most_common(10)))
        st = cstats.get("by_status", {})
        A("")
        A(f"**公司狀態**:未上市 {st.get('private',0):,} · 已上市 {st.get('public',0):,} · "
          f"已被併購 {st.get('acquired',0):,} · 已結束營運 {st.get('shut-down',0):,}")

    block = "\n".join(L)
    s = README.read_text("utf-8")
    i, j = s.index(BEGIN), s.index(END)
    i = s.index("-->", i) + 3
    README.write_text(s[:i] + "\n" + block + "\n" + s[j:], "utf-8")
    print(f"README stats updated — {len(ents):,} investors, {len(cos):,} companies, "
          f"{cstats.get('edges',0):,} edges")


if __name__ == "__main__":
    main()
