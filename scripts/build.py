# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema>=4.21"]
# ///
"""Merge raw agent research dumps into validated, deduped entity datasets.

Pipeline
--------
    data/<region>/_raw/*.json     (agent outputs; each file = JSON array of entities)
          | read + flatten + stamp researched_by
          v
    dedup via is_same_entity()    (merge duplicates, union their sources)
          | validate each vs schema/entity.schema.json
          v
    data/<region>/entities.json   (per-region, merged + validated)
    data/all-entities.json        (global merged)
    data/stats.json               (counts by region / type / sector / modality / indication / confidence)
    reports/validation.md         (schema violations + data-quality notes)

Run:  uv run scripts/build.py        (uv resolves jsonschema from the header above)
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCHEMA = json.loads((ROOT / "schema" / "entity.schema.json").read_text("utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)

_STOPWORDS = (
    r"\b(the|inc|llc|ltd|co|corp|ventures?|capital|partners?|fund|funds|vc|group|"
    r"holdings?|management|advisors?|bio|life|sciences?|health(care)?)\b"
)

# Domains that agents sometimes put in `website` but that never identify one org.
_SHARED_DOMAINS = {
    "linkedin.com", "crunchbase.com", "twitter.com", "x.com", "facebook.com",
    "wikipedia.org", "medium.com", "notion.site", "substack.com",
}


def norm_name(name: str) -> str:
    """Lowercase, fold accents, drop legal/role/sector suffixes and punctuation, collapse ws.

    Accent-folding matters: "Panakès Partners" and "Panakes Partners" are the same firm,
    but without NFKD-stripping the 'è', the second regex turns them into different tokens
    ('panak s' vs 'panakes') and dedup misses the duplicate.
    """
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    s = re.sub(_STOPWORDS, " ", folded.lower())
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def norm_domain(url: str | None) -> str | None:
    """Registrable-ish domain: strip scheme/www/path. Returns None for shared platforms."""
    if not url:
        return None
    host = urlparse(url if "//" in url else f"https://{url}").netloc.lower()
    host = host.removeprefix("www.")
    if not host or any(host == d or host.endswith("." + d) for d in _SHARED_DOMAINS):
        return None
    return host


# === CONTRIBUTION POINT =================================================
# Deciding when two rows are "the same organization" is a genuine design
# call with trade-offs:
#   - too LOOSE  -> "XYZ Health Ventures" and "XYZ Healthcare Partners"
#                   wrongly merge into one
#   - too STRICT -> "OrbiMed" and "OrbiMed Advisors" stay as two duplicates
# Medical fund names collide constantly (Health/Bio/Life prefixes), so the
# default below matches on: same region AND (normalized name OR website
# domain). Note _STOPWORDS strips health/bio/life tokens — that makes name
# matching aggressive on purpose; the domain check is the high-precision
# backstop. Tune per taste. See ARCHITECTURE.md > Dedup.
def is_same_entity(a: dict, b: dict) -> bool:
    if a.get("region") != b.get("region"):
        return False
    # Same agent-generated slug in the same region ⇒ same org. The id is derived
    # from the canonical name, so two segments that both landed on e.g.
    # "cn-lilly-asia-ventures" found the same firm even when their display names
    # ("Lilly Asia Ventures" vs "Lilly Asia Ventures (LAV)") or domains differ.
    if a.get("id") and a.get("id") == b.get("id"):
        return True
    da, db = norm_domain(a.get("website")), norm_domain(b.get("website"))
    if da and db and da == db:
        return True
    return norm_name(a["name"]["en"]) == norm_name(b["name"]["en"])
# ========================================================================


def merge(a: dict, b: dict) -> dict:
    """Merge b into a: union list-ish fields, keep highest confidence, backfill blanks."""
    out = dict(a)
    out["sources"] = (a.get("sources") or []) + (b.get("sources") or [])
    for key in ("aka", "subtypes", "tags"):
        out[key] = sorted(set((a.get(key) or []) + (b.get(key) or [])))
    rank = {"high": 3, "medium": 2, "low": 1}
    if rank.get(b.get("confidence"), 0) > rank.get(a.get("confidence"), 0):
        out["confidence"] = b["confidence"]
    for key, val in b.items():
        if out.get(key) in (None, "", [], {}):
            out[key] = val
    note = "merged from duplicate research rows"
    out["verification_notes"] = ((out.get("verification_notes") or "") + f" [{note}]").strip()
    return out


def load_raw(region_dir: Path) -> list[dict]:
    items: list[dict] = []
    raw = region_dir / "_raw"
    if not raw.exists():
        return items
    for f in sorted(raw.glob("*.json")):
        try:
            doc = json.loads(f.read_text("utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  ! {f.name}: invalid JSON ({exc})", file=sys.stderr)
            continue
        rows = doc if isinstance(doc, list) else doc.get("entities", [])
        for row in rows:
            if not isinstance(row, dict):
                continue
            row.setdefault("researched_by", f.stem)
            items.append(row)
    return items


def strip_nulls(obj):
    """Recursively drop dict keys whose value is None.

    Agents set unknown fields to null (e.g. "contact": null, money "raw": null).
    Semantically null == absent, and every optional schema field is happy when
    absent — so stripping nulls both satisfies the schema and de-clutters the
    output, without chasing nullable types field-by-field.
    """
    if isinstance(obj, dict):
        return {k: strip_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [strip_nulls(v) for v in obj]
    return obj


# Controlled vocab + known cross-field aliases (agents occasionally put an
# indication slug in sector_focus, or a sector slug in modalities). Map the
# obvious ones; drop anything still off-vocabulary so filters stay clean.
_TAX = json.loads((DATA / "taxonomy.json").read_text("utf-8"))
_VOCAB = {
    "sector_focus": {s["slug"] for s in _TAX["sectors"]},
    "stages": {s["slug"] for s in _TAX["stages"]},
    "modalities": {m["slug"] for m in _TAX["modalities"]},
    "indications": {i["slug"] for i in _TAX["indications"]},
}
_ALIAS = {
    "sector_focus": {"womens-health": "femtech-womens-health", "aging-longevity": "longevity-aging"},
}


def normalize_vocab(entity: dict) -> dict:
    """Map known slug aliases and drop off-vocabulary values from controlled fields."""
    for field, container_key in (("sector_focus", "strategy"), ("stages", "strategy"),
                                 ("modalities", "lifesci"), ("indications", "lifesci")):
        container = entity.get(container_key)
        if not isinstance(container, dict) or field not in container:
            continue
        aliases = _ALIAS.get(field, {})
        cleaned, seen = [], set()
        for v in container[field] or []:
            v = aliases.get(v, v)
            if v in _VOCAB[field] and v not in seen:
                cleaned.append(v)
                seen.add(v)
        container[field] = cleaned
    return entity


def dedup(items: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for item in items:
        for i, existing in enumerate(merged):
            if is_same_entity(existing, item):
                merged[i] = merge(existing, item)
                break
        else:
            merged.append(item)
    return merged


def main() -> None:
    region_dirs = [d for d in sorted(DATA.iterdir()) if d.is_dir() and not d.name.startswith("_")]
    all_entities: list[dict] = []
    violations: list[str] = []
    stats = {
        "total": 0,
        "by_region": {},
        "by_type": defaultdict(int),
        "by_sector": defaultdict(int),
        "by_modality": defaultdict(int),
        "by_indication": defaultdict(int),
        "by_confidence": defaultdict(int),
    }

    for region_dir in region_dirs:
        region = region_dir.name
        items = load_raw(region_dir)
        if not items:
            continue
        merged = [normalize_vocab(strip_nulls(e)) for e in dedup(items)]

        for entity in merged:
            label = entity.get("id") or entity.get("name", {}).get("en", "?")
            for err in sorted(VALIDATOR.iter_errors(entity), key=lambda e: list(e.path)):
                path = "/".join(str(p) for p in err.path) or "(root)"
                violations.append(f"- `{region}` / `{label}` @ `{path}`: {err.message}")

        (region_dir / "entities.json").write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), "utf-8"
        )
        stats["by_region"][region] = len(merged)
        stats["total"] += len(merged)
        for entity in merged:
            stats["by_type"][entity.get("type", "unknown")] += 1
            stats["by_confidence"][entity.get("confidence", "unknown")] += 1
            for sector in (entity.get("strategy", {}) or {}).get("sector_focus", []) or []:
                stats["by_sector"][sector] += 1
            lifesci = entity.get("lifesci", {}) or {}
            for modality in lifesci.get("modalities", []) or []:
                stats["by_modality"][modality] += 1
            for indication in lifesci.get("indications", []) or []:
                stats["by_indication"][indication] += 1
        all_entities.extend(merged)
        print(f"  ok {region:>16}: {len(items):>4} raw -> {len(merged):>4} merged")

    (DATA / "all-entities.json").write_text(
        json.dumps(all_entities, ensure_ascii=False, indent=2), "utf-8"
    )
    for key in ("by_type", "by_sector", "by_modality", "by_indication", "by_confidence"):
        stats[key] = dict(sorted(stats[key].items(), key=lambda kv: -kv[1]))
    (DATA / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), "utf-8")

    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    body = [
        "# Validation report",
        "",
        f"- Total entities: **{stats['total']}**",
        f"- Regions with data: **{len(stats['by_region'])}**",
        f"- Schema violations: **{len(violations)}**",
        "",
        "## By region",
        "",
        *[f"- {r}: {n}" for r, n in stats["by_region"].items()],
        "",
        f"## Schema violations ({len(violations)})",
        "",
        ("\n".join(violations) if violations else "None — every entity validates. :)"),
        "",
    ]
    (reports / "validation.md").write_text("\n".join(body), "utf-8")

    print(f"\nTotal: {stats['total']} entities across {len(stats['by_region'])} region(s)")
    print(f"Schema violations: {len(violations)} (see reports/validation.md)")


if __name__ == "__main__":
    main()
