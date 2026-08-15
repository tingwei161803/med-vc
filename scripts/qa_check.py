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

CO_SCHEMA_PATH = ROOT / "schema" / "company.schema.json"
CO_VALIDATOR = Draft202012Validator(json.loads(CO_SCHEMA_PATH.read_text("utf-8"))) \
    if CO_SCHEMA_PATH.exists() else None

VALID = {
    "type": {t["slug"] for t in TAX["types"]},
    "sector": {s["slug"] for s in TAX["sectors"]},
    "modality": {m["slug"] for m in TAX["modalities"]},
    "indication": {i["slug"] for i in TAX["indications"]},
    "stage": {s["slug"] for s in TAX["stages"]},
    "region": {r["slug"] for r in TAX["regions"]},
    "status": set(TAX["status"]),
    "confidence": set(TAX["confidence"]),
    "backer_kind": {b["slug"] for b in TAX.get("backer_kinds", [])},
    "backer_relationship": {b["slug"] for b in TAX.get("backer_relationships", [])},
    "company_status": {s["slug"] for s in TAX.get("company_status", [])},
    "development_stage": {s["slug"] for s in TAX.get("development_stages", [])},
}

# Placeholder / hallucination smells. Checked ONLY in human-facing text fields
# (name/thesis/summary) — NOT across the whole JSON, because URLs ("/en/about"
# contains "n/a"), money bands ("<$100M"), and honest verification_notes
# ("website was a 'Coming Soon' placeholder") produce false positives there.
SMELLS = ["example.com", "lorem ipsum", "placeholder text", "todo", "xxxx", "tbd", "your-", "insert here"]

# The id-prefix convention, derived from the dataset rather than declared: every
# existing record's id begins with its region's short code.
REGION_PREFIX = {
    "taiwan": "tw", "united-states": "us", "europe": "eu", "greater-china": "cn",
    "japan": "jp", "south-korea": "kr", "israel": "il", "canada": "ca",
    "india": "in", "southeast-asia": "sea", "australia-nz": "anz",
    "rest-of-world": "row",
}


def norm_name(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return " ".join(s.split())


def check_companies(issues: dict[str, list[str]], entity_names: set[str]) -> dict:
    """QA the company half. Returns a summary dict; empty when there is no data.

    Kept in this file rather than a sibling script so `uv run scripts/qa_check.py`
    stays the single answer to "is the data healthy". A second entry point is a
    second thing to forget to run.
    """
    path = DATA / "all-companies.json"
    if not path.exists() or CO_VALIDATOR is None:
        return {}
    companies = json.loads(path.read_text("utf-8"))
    if not companies:
        return {"total": 0}

    ids: Counter[str] = Counter()
    n_sourced = n_quote = n_linked = 0
    conf: Counter[str] = Counter()

    for c in companies:
        cid = c.get("id", "??")
        label = f"co/{cid}"
        ids[cid] += 1
        for err in CO_VALIDATOR.iter_errors(c):
            issues["co-schema"].append(f"{label}: {err.message[:120]}")

        srcs = c.get("sources") or []
        if not srcs:
            issues["co-no-sources"].append(label)
        else:
            n_sourced += 1
            if any(s.get("quote") for s in srcs):
                n_quote += 1
            if not any(s.get("url", "").startswith("http") for s in srcs):
                issues["co-no-http-source"].append(label)

        if c.get("region") not in VALID["region"]:
            issues["co-bad-region"].append(f"{label}: {c.get('region')}")
        if c.get("category") and c["category"] not in VALID["sector"]:
            issues["co-bad-category"].append(f"{label}: {c.get('category')}")
        for s in c.get("sectors") or []:
            if s not in VALID["sector"]:
                issues["co-bad-sector"].append(f"{label}: {s}")
        st = c.get("status")
        if st and VALID["company_status"] and st not in VALID["company_status"]:
            issues["co-bad-status"].append(f"{label}: {st}")
        prof = c.get("profile") or {}
        ds = prof.get("development_stage")
        if ds and VALID["development_stage"] and ds not in VALID["development_stage"]:
            issues["co-bad-dev-stage"].append(f"{label}: {ds}")
        for m in prof.get("modalities") or []:
            if m not in VALID["modality"]:
                issues["co-bad-modality"].append(f"{label}: {m}")
        for i in prof.get("indications") or []:
            if i not in VALID["indication"]:
                issues["co-bad-indication"].append(f"{label}: {i}")

        if not re.fullmatch(r"[a-z0-9-]+", cid):
            issues["co-bad-id-format"].append(label)
        want = REGION_PREFIX.get(c.get("region", ""))
        if want and not cid.startswith(want + "-"):
            issues["co-id-prefix-region-mismatch"].append(f"{label}: expected '{want}-' prefix")

        conf[c.get("confidence", "?")] += 1

        invs = (c.get("funding") or {}).get("investors") or []
        if any(i.get("entity_id") for i in invs):
            n_linked += 1
        elif not invs:
            # not an error — a bootstrapped or state-funded company genuinely
            # has none — but it is the coverage gap this directory is about
            issues["co-no-investors"].append(label)

        # The two halves are supposed to be disjoint. A name in both is either
        # an operating company mis-filed as an investor, or a company that also
        # runs a venture arm and needs its two roles recorded as two records.
        nm = norm_name((c.get("name") or {}).get("en", ""))
        if nm and nm in entity_names:
            issues["co-name-in-both-halves"].append(f"{label}: '{nm}'")

        blurb = " ".join([(c.get("name") or {}).get("en", ""),
                          prof.get("what", ""),
                          (c.get("summary") or {}).get("en", "")]).lower()
        for smell in SMELLS:
            if smell in blurb:
                issues["co-smell"].append(f"{label}: '{smell}'")
                break

    for cid, n in ids.items():
        if n > 1:
            issues["co-duplicate-id"].append(f"{cid} appears {n}x")

    total = len(companies)
    # n_linked counts only the COMPANY side of the graph — companies whose own
    # record names an investor that resolved. The graph is bigger than that,
    # because investors also assert edges from their portfolio lists. Report
    # both, and label them, so the smaller number is not mistaken for total
    # connectivity.
    stats_path = DATA / "company-stats.json"
    graph_linked = None
    if stats_path.exists():
        graph_linked = json.loads(stats_path.read_text("utf-8")).get("linked_companies")
    return {"total": total, "sourced": n_sourced, "quoted": n_quote,
            "linked": n_linked, "graph_linked": graph_linked, "confidence": dict(conf)}


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
        # Every one of the 1,596 ids agrees with its region prefix, so this is a
        # real invariant rather than a style preference. It matters because
        # build.py files records by `region` while humans read the prefix — a
        # `us-` id sitting in data/europe/ is a record nobody will find again.
        want = REGION_PREFIX.get(region)
        if want and not eid.startswith(want + "-"):
            issues["id-prefix-region-mismatch"].append(f"{label}: expected '{want}-' prefix")

        # --- backing dimension ---
        backers = (e.get("backing") or {}).get("backers") or []
        for b in backers:
            if b.get("kind") not in VALID["backer_kind"]:
                issues["bad-backer-kind"].append(f"{label}: {b.get('kind')}")
            if b.get("relationship") not in VALID["backer_relationship"]:
                issues["bad-backer-relationship"].append(f"{label}: {b.get('relationship')}")
            if not (b.get("name") or "").strip():
                issues["backer-no-name"].append(label)
        # a CVC with no recorded parent is a coverage gap, not a data error —
        # the whole point of a corporate venture arm is that someone owns it
        if e.get("type") == "cvc" and not backers:
            issues["cvc-without-backer"].append(label)
        # inference is fine, but claiming a wholly-owned relationship on nothing
        # but a name match deserves a human look for the notable parents
        for b in backers:
            if b.get("evidence") == "inferred" and b.get("relationship") == "wholly-owned-cvc" \
                    and b.get("kind") in ("big-tech", "ai-lab"):
                issues["inferred-bigtech-parent"].append(f"{label}: {b.get('name')}")

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

    co = check_companies(issues, set(name_regions.keys()))

    # ---- report ----
    SEV = {
        "critical": ["INVALID-JSON", "schema", "no-sources", "no-http-source", "no-name", "bad-type", "bad-region", "duplicate-id",
                     "co-schema", "co-no-sources", "co-no-http-source", "co-bad-region", "co-duplicate-id"],
        "warning": ["malformed-url", "bad-sector", "bad-stage", "bad-modality", "bad-indication",
                    "bad-confidence", "bad-id-format", "cross-region-domain", "smell",
                    "bad-backer-kind", "bad-backer-relationship", "backer-no-name",
                    "id-prefix-region-mismatch",
                    "co-bad-category", "co-bad-sector", "co-bad-status", "co-bad-dev-stage",
                    "co-bad-modality", "co-bad-indication", "co-bad-id-format", "co-smell",
                    "co-id-prefix-region-mismatch"],
        "review": ["thin-file", "cross-region-name", "weak-medical-nexus",
                   "cvc-without-backer", "inferred-bigtech-parent",
                   "co-no-investors", "co-name-in-both-halves"],
    }
    print("=" * 60)
    print(f"med-vc QA — {n_total} entities")
    print(f"  sourced: {n_sourced}/{n_total} ({100*n_sourced//max(n_total,1)}%) · with quote: {n_with_quote} ({100*n_with_quote//max(n_total,1)}%)")
    print(f"  confidence: {dict(conf_counter)}")
    if co.get("total"):
        ct = co["total"]
        print(f"med-vc QA — {ct} companies")
        gl = co.get("graph_linked")
        print(f"  sourced: {co['sourced']}/{ct} ({100*co['sourced']//ct}%) · "
              f"with quote: {co['quoted']} ({100*co['quoted']//ct}%)")
        print(f"  investor named on the company record: {co['linked']} ({100*co['linked']//ct}%)"
              + (f" · connected in the link graph: {gl} ({100*gl//ct}%)" if gl else ""))
        print(f"  confidence: {co['confidence']}")
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
