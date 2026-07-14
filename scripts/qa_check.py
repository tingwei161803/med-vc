# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema>=4.21"]
# ///
"""Deterministic data-integrity QA for the med-vc dataset.

Layer-1 checks (cheap, no network). Run AFTER build.py.
Reports issues by severity so a human/agent can triage. Exit code 0 always
(this is a report, not a gate) — read the printed summary.

Run:  uv run scripts/qa_check.py
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCHEMA = json.loads((ROOT / "schema" / "entity.schema.json").read_text("utf-8"))
TAX = json.loads((DATA / "taxonomy.json").read_text("utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)

VALID = {
    "type": {t["slug"] for t in TAX["types"]},
    "sector": {s["slug"] for s in TAX["sectors"]},
    "modality": {m["slug"] for m in TAX["modalities"]},
    "indication": {i["slug"] for i in TAX["indications"]},
    "stage": {s["slug"] for s in TAX["stages"]},
    "region": {r["slug"] for r in TAX["regions"]},
    "status": set(TAX["status"]),
    "confidence": set(TAX["confidence"]),
}

# Placeholder / hallucination smells. Checked ONLY in human-facing text fields
# (name/thesis/summary) — NOT across the whole JSON, because URLs ("/en/about"
# contains "n/a"), money bands ("<$100M"), and honest verification_notes
# ("website was a 'Coming Soon' placeholder") produce false positives there.
SMELLS = ["example.com", "lorem ipsum", "placeholder text", "todo", "xxxx", "tbd", "your-", "insert here"]


def norm_name(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return " ".join(s.split())


def main() -> None:
    issues: dict[str, list[str]] = defaultdict(list)
    all_ids: Counter[str] = Counter()
    all_entities = json.loads((DATA / "all-entities.json").read_text("utf-8"))
    # cross-region duplicate map: normalized name/domain -> regions seen
    name_regions: dict[str, set[str]] = defaultdict(set)
    domain_regions: dict[str, set[str]] = defaultdict(set)

    n_total = len(all_entities)
    n_with_quote = 0
    n_sourced = 0
    conf_counter: Counter[str] = Counter()

    for e in all_entities:
        eid = e.get("id", "??")
        region = e.get("region", "??")
        label = f"{region}/{eid}"
        all_ids[eid] += 1

        # --- CRITICAL: schema ---
        errs = list(VALIDATOR.iter_errors(e))
        for err in errs:
            issues["schema"].append(f"{label}: {err.message[:120]}")

        # --- CRITICAL: sources present & real-looking ---
        srcs = e.get("sources") or []
        if not srcs:
            issues["no-sources"].append(label)
        else:
            n_sourced += 1
            has_url = any(s.get("url", "").startswith("http") for s in srcs)
            if not has_url:
                issues["no-http-source"].append(label)
            if any(s.get("quote") for s in srcs):
                n_with_quote += 1
            for s in srcs:
                u = s.get("url", "")
                if u and not u.startswith("http"):
                    issues["malformed-url"].append(f"{label}: {u[:60]}")

        # --- taxonomy adherence ---
        if e.get("type") not in VALID["type"]:
            issues["bad-type"].append(f"{label}: {e.get('type')}")
        if e.get("region") not in VALID["region"]:
            issues["bad-region"].append(f"{label}: {e.get('region')}")
        if e.get("confidence") not in VALID["confidence"]:
            issues["bad-confidence"].append(f"{label}: {e.get('confidence')}")
        conf_counter[e.get("confidence", "?")] += 1
        strat = e.get("strategy") or {}
        for s in strat.get("sector_focus") or []:
            if s not in VALID["sector"]:
                issues["bad-sector"].append(f"{label}: {s}")
        for s in strat.get("stages") or []:
            if s not in VALID["stage"]:
                issues["bad-stage"].append(f"{label}: {s}")
        ls = e.get("lifesci") or {}
        for m in ls.get("modalities") or []:
            if m not in VALID["modality"]:
                issues["bad-modality"].append(f"{label}: {m}")
        for i in ls.get("indications") or []:
            if i not in VALID["indication"]:
                issues["bad-indication"].append(f"{label}: {i}")

        # --- id format ---
        if not re.fullmatch(r"[a-z0-9-]+", eid):
            issues["bad-id-format"].append(label)

        # --- name present ---
        name_en = (e.get("name") or {}).get("en", "")
        if not name_en.strip():
            issues["no-name"].append(label)
        else:
            name_regions[norm_name(name_en)].add(region)

        # --- medical nexus sanity: some sector/modality/indication OR thesis/summary mentions health ---
        text = json.dumps(e, ensure_ascii=False).lower()
        if not (strat.get("sector_focus") or ls.get("modalities") or ls.get("indications")):
            # allow if thesis/summary clearly medical
            blurb = (strat.get("thesis", "") + " " + (e.get("summary") or {}).get("en", "")).lower()
            if not any(k in blurb for k in ("health", "medic", "bio", "life scien", "therap", "clinical", "patient", "pharma", "drug", "diagnost", "device")):
                issues["weak-medical-nexus"].append(label)

        # --- hallucination smells (human-facing text only) ---
        blurb = " ".join([
            name_en,
            (strat.get("thesis") or ""),
            (e.get("summary") or {}).get("en", ""),
        ]).lower()
        for smell in SMELLS:
            if smell in blurb:
                issues["smell"].append(f"{label}: '{smell}' in name/thesis/summary")
                break

        # --- website domain for cross-region dupe ---
        w = e.get("website", "")
        if w:
            host = urlparse(w if "//" in w else f"https://{w}").netloc.lower().removeprefix("www.")
            if host:
                domain_regions[host].add(region)

    # duplicate ids (should be unique across whole dataset ideally, at least within region)
    for eid, c in all_ids.items():
        if c > 1:
            issues["duplicate-id"].append(f"{eid} appears {c}x")

    # same org (by name) appearing in multiple regions
    for nm, regions in name_regions.items():
        if len(regions) > 1 and nm:
            issues["cross-region-name"].append(f"'{nm}' in {sorted(regions)}")
    for host, regions in domain_regions.items():
        if len(regions) > 1:
            issues["cross-region-domain"].append(f"{host} in {sorted(regions)}")

    # thin raw files (possible truncation/overwrite damage)
    for region_dir in sorted(DATA.iterdir()):
        raw = region_dir / "_raw"
        if not raw.is_dir():
            continue
        for f in sorted(raw.glob("*.json")):
            try:
                arr = json.loads(f.read_text("utf-8"))
            except json.JSONDecodeError:
                issues["INVALID-JSON"].append(f"{region_dir.name}/{f.stem}")
                continue
            if not isinstance(arr, list) or len(arr) <= 1:
                issues["thin-file"].append(f"{region_dir.name}/{f.stem} (n={len(arr) if isinstance(arr, list) else '?'})")

    # ---- report ----
    SEV = {
        "critical": ["INVALID-JSON", "schema", "no-sources", "no-http-source", "no-name", "bad-type", "bad-region", "duplicate-id"],
        "warning": ["malformed-url", "bad-sector", "bad-stage", "bad-modality", "bad-indication", "bad-confidence", "bad-id-format", "cross-region-domain", "smell"],
        "review": ["thin-file", "cross-region-name", "weak-medical-nexus"],
    }
    print("=" * 60)
    print(f"med-vc QA — {n_total} entities")
    print(f"  sourced: {n_sourced}/{n_total} ({100*n_sourced//max(n_total,1)}%) · with quote: {n_with_quote} ({100*n_with_quote//max(n_total,1)}%)")
    print(f"  confidence: {dict(conf_counter)}")
    print("=" * 60)
    for sev, keys in SEV.items():
        total = sum(len(issues[k]) for k in keys)
        print(f"\n### {sev.upper()} — {total} issue(s)")
        for k in keys:
            if issues[k]:
                print(f"  [{k}] {len(issues[k])}")
                for line in issues[k][:8]:
                    print(f"      - {line}")
                if len(issues[k]) > 8:
                    print(f"      … +{len(issues[k]) - 8} more")
    # persist full detail
    out = ROOT / "reports" / "qa.json"
    out.write_text(json.dumps({k: v for k, v in issues.items()}, ensure_ascii=False, indent=2), "utf-8")
    print(f"\nFull detail: {out}")


if __name__ == "__main__":
    main()
