# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema>=4.21", "zhconv>=1.4"]
# ///
"""Build the company half of the directory and wire it to the investor half.

    data/companies/_raw/*.json   (source of truth, one file per research slice)
        -> dedupe -> normalize vocab -> validate
        -> data/all-companies.json      DERIVED
        -> data/links.json              DERIVED
        -> data/company-stats.json      DERIVED
        -> reports/links.json           unresolved names, for the next round

DERIVED means exactly what it means in build.py: these files are rewritten from
scratch on every run. Editing them by hand, or having an agent write research
into them, loses that work on the next build. Research goes in _raw/.

Run AFTER build.py, because the link resolver needs a current
data/all-entities.json to resolve investor names against.

Run:  uv run scripts/build_companies.py


The link graph
--------------
The point of this directory is that the two halves point at each other. Edges
come from BOTH sides and are merged:

  company side   funding.investors[].name        -> an investor id
  investor side  track_record.notable_investments[].company -> a company id

An edge asserted by both sides is stronger than one asserted by either alone,
so each edge carries `via`: "company", "investor", or "both". The investor side
already held 1,645 such claims before a single company was researched, which is
why this file resolves names rather than asking anyone to research relationships
that were already recorded.

Resolution is deliberately conservative. A wrong link is worse than a missing
one: a missing link is visibly missing, a wrong link reads as a fact. So a name
resolves only on a UNIQUE hit, and ambiguity is written to reports/links.json
for a human rather than guessed. "Sequoia" matching three different firms on
three continents is the case this protects against.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "companies" / "_raw"
SCHEMA = json.loads((ROOT / "schema" / "company.schema.json").read_text("utf-8"))
TAX = json.loads((DATA / "taxonomy.json").read_text("utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)

VOCAB = {
    "sector": {s["slug"] for s in TAX["sectors"]},
    "modality": {m["slug"] for m in TAX["modalities"]},
    "indication": {i["slug"] for i in TAX["indications"]},
    "stage": {s["slug"] for s in TAX["stages"]},
    "region": {r["slug"] for r in TAX["regions"]},
}
# funding rounds have shapes the investor-stage vocabulary does not cover
EXTRA_STAGES = {"ipo", "debt", "grant", "crowdfunding", "secondary", "acquisition", "unknown"}

# Researcher shorthand -> canonical slug. Same idea as build.py's _ALIAS: an
# agent writing "digital health" instead of "digital-health" is a formatting
# slip, not a data error, and silently dropping it loses real research.
ALIAS = {
    "sector": {
        "digital health": "digital-health", "healthtech": "digital-health",
        "health tech": "digital-health", "telehealth": "digital-health",
        "biotech": "therapeutics", "biotechnology": "therapeutics",
        "pharma": "therapeutics", "pharmaceuticals": "therapeutics",
        "drug development": "therapeutics", "drug discovery": "ai-drug-discovery",
        "medtech": "medtech-devices", "devices": "medtech-devices",
        "medical devices": "medtech-devices", "medical device": "medtech-devices",
        "diagnostics": "diagnostics", "dx": "diagnostics",
        "tools": "life-science-tools", "research tools": "life-science-tools",
        "health it": "healthcare-it", "healthit": "healthcare-it",
        "health services": "healthcare-services", "care delivery": "healthcare-services",
        "provider": "healthcare-services", "payer": "healthcare-services",
        "insurtech": "healthcare-services", "value-based care": "healthcare-services",
        "genomics": "genomics-omics", "omics": "genomics-omics",
        "synbio": "synthetic-biology", "cell therapy": "cell-gene-therapy",
        "gene therapy": "cell-gene-therapy", "cgt": "cell-gene-therapy",
        "cro": "pharma-services", "cdmo": "pharma-services",
        "robotics": "surgical-robotics", "imaging": "medical-imaging",
        "radiology": "medical-imaging", "consumer": "consumer-health",
        "wellness": "consumer-health", "longevity": "longevity-aging",
        "womens health": "femtech-womens-health", "femtech": "femtech-womens-health",
        "behavioral health": "mental-health", "mental health": "mental-health",
        "vet": "animal-health", "veterinary": "animal-health",
        "ai": "ai-drug-discovery", "healthcare ai": "digital-health",
    },
    "stage": {
        "pre seed": "pre-seed", "preseed": "pre-seed",
        "a": "series-a", "b": "series-b", "c": "series-c-plus",
        "series c": "series-c-plus", "series d": "series-c-plus",
        "series e": "series-c-plus", "series f": "series-c-plus",
        "series g": "series-c-plus", "series h": "series-c-plus",
        "late stage": "growth", "growth equity": "growth",
        "public": "ipo", "listing": "ipo",
    },
    "region": {
        "us": "united-states", "usa": "united-states", "north america": "united-states",
        "uk": "europe", "united kingdom": "europe", "eu": "europe",
        "china": "greater-china", "hong kong": "greater-china",
        "korea": "south-korea", "singapore": "southeast-asia",
        "australia": "australia-nz", "new zealand": "australia-nz",
    },
}

DEV_STAGES = {"discovery", "preclinical", "phase-1", "phase-2", "phase-3",
              "approved", "commercial", "pilot", "unknown"}
STATUSES = {"private", "public", "acquired", "merged", "shut-down", "unknown"}

CONF_RANK = {"high": 0, "medium": 1, "low": 2}


# --------------------------------------------------------------------------
# name normalization
# --------------------------------------------------------------------------
_LEGAL = r"\b(?:inc|incorporated|llc|l\.?l\.?c|ltd|limited|corp|corporation|co|company|" \
         r"companies|plc|s\.?a|ag|gmbh|b\.?v|n\.?v|ab|a/s|oy|kk|pte|pty|srl|s\.?p\.?a|" \
         r"sas|sarl|kft|oyj)\b"
# tails that carry no identity on their own — "Foo Capital" and "Foo Ventures"
# are the same firm often enough that stripping them finds real matches
_TAIL = ("capital", "ventures", "venture", "partners", "partner", "management",
         "advisors", "advisers", "investments", "investment", "fund", "funds",
         "group", "holdings", "holding", "associates", "equity", "asset",
         "technologies", "technology", "labs", "lab", "health", "bio",
         "therapeutics", "sciences", "science", "systems", "medical", "inc",
         # The life-science half of the vocabulary. A company files as
         # "AbCellera Biologics Inc." and the world writes "AbCellera"; without
         # these the two never meet. Aggressive stripping is safe here because
         # _pick still demands a UNIQUE hit — two companies collapsing to the
         # same core produce a refusal, not a wrong link.
         "biologics", "biosciences", "bioscience", "biopharma",
         "biopharmaceuticals", "biopharmaceutical", "pharmaceuticals",
         "pharmaceutical", "pharma", "biotechnologies", "biotechnology",
         "biotech", "diagnostics", "genomics", "medicines", "medicine",
         "healthcare", "biolabs", "bioworks", "biotherapeutics")
# a core this generic identifies nobody; refuse to match on it
_TOO_GENERIC = {"health", "bio", "medical", "care", "life", "new", "first",
                "global", "national", "the", "one", "open", "med", "digital",
                "science", "sciences", "group", "fund", "capital", "ventures"}


# CJK ranges must survive normalization or every Chinese, Japanese and Korean
# name in the dataset resolves to the empty string and can never be linked.
_CJK = r"㐀-䶿一-鿿぀-ゟ゠-ヿ가-힯"
_KEEP = re.compile(rf"[^a-z0-9{_CJK}]+")
_HAS_CJK = re.compile(rf"[{_CJK}]")
# Han characters trigger traditional/simplified folding. Any kana or Hangul in
# the string vetoes it — those are a reliable signal the text is Japanese or
# Korean, where a Chinese converter has no business.
_HAS_HAN = re.compile(r"[㐀-䶿一-鿿]")
_HAS_KANA_HANGUL = re.compile(r"[぀-ゟ゠-ヿ가-힯]")

try:
    from zhconv import convert as _zh_convert
except ImportError:  # keep the build runnable without the optional dependency
    _zh_convert = None


def norm(s: str) -> str:
    """Casefold, strip accents and punctuation, drop legal suffixes, collapse.

    NFKC folds full-width Latin and CJK compatibility forms. Accents are then
    dropped via a decompose/strip/RECOMPOSE cycle so "Sanofi" and "Sanofí"
    agree. The recompose step is not cosmetic: NFD explodes Hangul syllables
    into Jamo and detaches the Japanese dakuten, both of which the character
    filter below would then delete — turning "한미약품" into "" and "ソニーグループ"
    into "ソニークルーフ". NFC puts them back before anything is filtered.

    Han text is folded to SIMPLIFIED as the canonical key, so "紅杉" and "红杉"
    land on the same entry. The direction matters and is not arbitrary:
    traditional -> simplified is many-to-one and deterministic, while
    simplified -> traditional is one-to-many and has to guess — round-tripping
    "台杉投資" through traditional yields "臺杉投資", and "启明创投" yields
    "啓明創投". Folding one way is exact; folding the other invents variants.

    Strings containing kana or Hangul skip the fold entirely — those characters
    reliably mark Japanese or Korean text, where a Chinese converter has no
    business. A pure-kanji Japanese name like 塩野義製薬 is indistinguishable
    from Chinese by characters alone and DOES get folded, to 塩野义制薬. That is
    mojibake, and it is harmless here for one specific reason: this value is a
    hash key, never displayed, and the same fold is applied to both the index
    and the query, so the two sides still meet. Display always uses the
    original `name` field.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = unicodedata.normalize("NFC", s)
    if _zh_convert and _HAS_HAN.search(s) and not _HAS_KANA_HANGUL.search(s):
        s = _zh_convert(s, "zh-hans")
    s = s.lower().replace("&", " and ").replace("+", " and ")
    s = _KEEP.sub(" ", s)
    s = re.sub(_LEGAL, " ", s)
    return " ".join(s.split())


def core(s: str) -> str | None:
    """The distinctive part of a name, or None when nothing distinctive is left.

    "Google Ventures" -> "google";  "Health Capital" -> None (too generic).
    Returning None is the point: it is what keeps a dozen firms whose names
    reduce to "health" from all collapsing onto each other.

    CJK names get a shorter minimum length. "红杉" is two characters and
    perfectly distinctive; the 4-character floor is a fact about how much
    information a Latin token carries, not a universal one.
    """
    toks = norm(s).split()
    while len(toks) > 1 and toks[-1] in _TAIL:
        toks.pop()
    if not toks:
        return None
    c = " ".join(toks)
    if len(toks) == 1:
        floor = 2 if _HAS_CJK.search(toks[0]) else 4
        if toks[0] in _TOO_GENERIC or len(toks[0]) < floor:
            return None
    return c


class Resolver:
    """Name -> id, on unique hits only.

    Two indexes rather than one fuzzy score. `strict` holds full normalized
    names and aliases; `loose` holds cores. A lookup tries the curated alias
    table, then strict, then loose, and reports WHY it failed so the miss is
    actionable: "not in the directory" and "matched four firms" need different
    fixes.
    """

    def __init__(self, records: list[dict], aliases: dict[str, str]):
        self.aliases = {norm(k): v for k, v in aliases.items()}
        self.strict: dict[str, set[str]] = defaultdict(set)
        self.loose: dict[str, set[str]] = defaultdict(set)
        self.ids = {r["id"] for r in records}
        self.region = {r["id"]: r.get("region", "") for r in records}
        for r in records:
            names = [r["name"].get("en", ""), r["name"].get("local", "")]
            names += r.get("aka") or []
            for n in self._variants(names):
                if (k := norm(n)):
                    self.strict[k].add(r["id"])
                if (c := core(n)):
                    self.loose[c].add(r["id"])

    @staticmethod
    def _variants(names: list[str]) -> set[str]:
        """Every name, plus a copy with parenthetical qualifiers removed.

        This directory disambiguates by parenthesis — "New Enterprise
        Associates (NEA)", "General Catalyst (Health Assurance)", "OrbiMed
        (India / Asia healthcare growth investing)" — but the outside world
        writes the bare name. Indexing both forms is what makes a press release
        saying "New Enterprise Associates" find the record. Where stripping the
        qualifier creates a collision (all four OrbiMed vehicles collapse to
        "OrbiMed"), the region tiebreaker in _pick handles it, and where it
        cannot, the match is refused rather than guessed.
        """
        out: set[str] = set()
        for n in names:
            if not n:
                continue
            out.add(n)
            if (base := re.sub(r"\s*[（(].*", "", n).strip()) and base != n:
                out.add(base)
        return out

    def _pick(self, cands: set[str], region: str | None, how: str) -> tuple[str | None, str]:
        """Collapse a candidate set to one id, using region as the tiebreaker.

        A name matching several ids is usually one global firm holding a
        separate vehicle per geography — OrbiMed runs US, Israel, India and
        Asia funds, all legitimately called "OrbiMed". For a US company, the
        US fund is the right answer, not a coin flip and not a refusal. Only
        when region fails to single one out does this give up.
        """
        if len(cands) == 1:
            return next(iter(cands)), how
        if region:
            same = {i for i in cands if self.region.get(i) == region}
            if len(same) == 1:
                return next(iter(same)), f"{how}+region"
        return None, f"ambiguous-{how}:{len(cands)}"

    def resolve(self, name: str, region: str | None = None) -> tuple[str | None, str]:
        k = norm(name)
        if not k:
            return None, "empty"
        if (hit := self.aliases.get(k)):
            return (hit, "alias") if hit in self.ids else (None, "alias-dangling")
        if (s := self.strict.get(k)):
            return self._pick(s, region, "exact")
        c = core(name)
        if c and (s := self.loose.get(c)):
            return self._pick(s, region, "core")
        return None, "unknown"


# --------------------------------------------------------------------------
# normalize / dedupe
# --------------------------------------------------------------------------
def fix_vocab(value: str, axis: str, dropped: Counter) -> str | None:
    if not value:
        return None
    v = value.strip()
    if v in VOCAB[axis]:
        return v
    k = norm(v).replace("-", " ")
    if (a := ALIAS.get(axis, {}).get(k)):
        return a
    slug = re.sub(r"[^a-z0-9]+", "-", norm(v)).strip("-")
    if slug in VOCAB[axis]:
        return slug
    dropped[f"{axis}:{value}"] += 1
    return None


def prune_nulls(obj):
    """Drop every null-valued key, recursively.

    Researchers write `"hq_city": null` to mean "couldn't find it", which is
    the right instinct but the wrong encoding — the schema types that field as
    a plain string, so null fails validation while ABSENT is exactly what the
    project asks for ("查不到就省略，不要塞假值"). Rather than push perfection
    onto every agent prompt, normalize it here once. Nullable fields
    (founded_year, money.usd, exit.year...) are optional too, so dropping their
    nulls is equally lossless.
    """
    if isinstance(obj, dict):
        return {k: prune_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [prune_nulls(v) for v in obj]
    return obj


def normalize(c: dict, dropped: Counter) -> dict:
    c = prune_nulls(c)
    c["region"] = fix_vocab(c.get("region", ""), "region", dropped) or c.get("region", "")
    cat = fix_vocab(c.get("category", ""), "sector", dropped)
    if cat:
        c["category"] = cat
    secs = []
    for s in c.get("sectors") or []:
        if (f := fix_vocab(s, "sector", dropped)) and f not in secs:
            secs.append(f)
    # the primary category is always also a sector, so one filter finds everything
    if c.get("category") in VOCAB["sector"] and c["category"] not in secs:
        secs.insert(0, c["category"])
    c["sectors"] = secs

    p = c.get("profile") or {}
    for axis, key in (("modality", "modalities"), ("indication", "indications")):
        vals = []
        for v in p.get(key) or []:
            # A value that is a valid SECTOR slug filed under modalities is real
            # research on the wrong axis, not a typo — "synthetic-biology" is a
            # field of work, not a treatment modality. Move it rather than drop
            # it; dropping loses a fact the researcher actually established.
            slug = re.sub(r"[^a-z0-9]+", "-", norm(v)).strip("-")
            if slug in VOCAB["sector"] and slug not in VOCAB[axis]:
                if slug not in secs:
                    secs.append(slug)
                continue
            if (f := fix_vocab(v, axis, dropped)) and f not in vals:
                vals.append(f)
        if vals or key in p:
            p[key] = vals
    c["sectors"] = secs
    ds = (p.get("development_stage") or "").strip().lower().replace(" ", "-")
    if ds:
        p["development_stage"] = ds if ds in DEV_STAGES else "unknown"
    if p:
        c["profile"] = p

    # Researchers write kind as "FDA 510(k)" while body already says "FDA",
    # which renders as "FDA FDA 510(k) 2019". Strip the redundant prefix only —
    # deliberately NOT rewriting vaguer kinds like "FDA clearance" into
    # "510(k)", because that would invent a precision the source did not give.
    for rg in (p.get("regulatory") or []):
        body, kind = (rg.get("body") or "").strip(), (rg.get("kind") or "").strip()
        if body and kind.lower().startswith(body.lower() + " "):
            rg["kind"] = kind[len(body):].strip()

    st = (c.get("status") or "").strip().lower().replace(" ", "-")
    if st:
        c["status"] = st if st in STATUSES else "unknown"

    f = c.get("funding") or {}
    for rnd in ([f.get("last_round")] if f.get("last_round") else []) + (f.get("rounds") or []):
        if not isinstance(rnd, dict):
            continue
        s = (rnd.get("stage") or "").strip().lower()
        if not s:
            continue
        if s in EXTRA_STAGES or s in VOCAB["stage"]:
            rnd["stage"] = s
        else:
            rnd["stage"] = fix_vocab(s, "stage", dropped) or "unknown"
    for inv in f.get("investors") or []:
        # entity_id is derived; whatever a researcher wrote there is discarded
        inv["entity_id"] = None
        r = (inv.get("role") or "").strip().lower()
        inv["role"] = r if r in {"lead", "co-lead", "participant", "angel", "unknown"} else "unknown"
    if f:
        c["funding"] = f
    return c


def score(c: dict) -> tuple:
    """Which duplicate wins: better-sourced first, then richer."""
    return (
        CONF_RANK.get(c.get("confidence"), 3),
        -len(c.get("sources") or []),
        -sum(1 for s in c.get("sources") or [] if s.get("quote")),
        -len(((c.get("funding") or {}).get("investors")) or []),
        -len(json.dumps(c, ensure_ascii=False)),
    )


def merge(winner: dict, loser: dict) -> dict:
    """Fold a duplicate's unique investors, sources and aka into the winner.

    Deduping by keeping only the better record throws away real research — the
    weaker row often names investors the stronger one missed. So the row is
    replaced but its distinct facts are salvaged.
    """
    seen_src = {s.get("url") for s in winner.get("sources") or []}
    for s in loser.get("sources") or []:
        if s.get("url") and s["url"] not in seen_src:
            winner.setdefault("sources", []).append(s)
            seen_src.add(s["url"])

    aka = winner.setdefault("aka", [])
    for n in [loser["name"].get("en", "")] + (loser.get("aka") or []):
        if n and norm(n) != norm(winner["name"].get("en", "")) and n not in aka:
            aka.append(n)

    wf = winner.setdefault("funding", {})
    seen_inv = {norm(i.get("name", "")) for i in wf.get("investors") or []}
    for i in (loser.get("funding") or {}).get("investors") or []:
        if (k := norm(i.get("name", ""))) and k not in seen_inv:
            wf.setdefault("investors", []).append(i)
            seen_inv.add(k)

    for key in ("sectors",):
        vals = winner.get(key) or []
        for v in loser.get(key) or []:
            if v not in vals:
                vals.append(v)
        if vals:
            winner[key] = vals
    return winner


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    raw_files = sorted(RAW.glob("*.json"))
    records: list[dict] = []
    for f in raw_files:
        arr = json.loads(f.read_text("utf-8"))
        if isinstance(arr, dict):
            arr = arr.get("companies") or []
        for c in arr:
            c.setdefault("researched_by", f.stem)
            records.append(c)
    print(f"read {len(records)} rows from {len(raw_files)} raw file(s)")

    dropped: Counter[str] = Counter()
    records = [normalize(c, dropped) for c in records]

    # --- dedupe on id, then normalized name, then website host ---
    by_key: dict[str, dict] = {}
    key_of: dict[str, str] = {}
    dupes = 0

    def keys_for(c: dict) -> list[str]:
        ks = [f"id:{c['id']}", f"nm:{norm(c['name'].get('en',''))}"]
        if (loc := c["name"].get("local")):
            ks.append(f"nm:{norm(loc)}")
        if (w := c.get("website")):
            host = re.sub(r"^https?://(www\.)?", "", w).split("/")[0].lower()
            if host:
                ks.append(f"web:{host}")
        return [k for k in ks if not k.endswith(":")]

    for c in sorted(records, key=score):
        hit = next((key_of[k] for k in keys_for(c) if k in key_of), None)
        if hit:
            merge(by_key[hit], c)
            dupes += 1
        else:
            by_key[c["id"]] = c
            hit = c["id"]
        for k in keys_for(by_key[hit]):
            key_of[k] = hit
    companies = sorted(by_key.values(), key=lambda c: c["id"])
    print(f"deduped: {dupes} row(s) folded -> {len(companies)} companies")

    # --- validate ---
    bad = 0
    for c in companies:
        for err in VALIDATOR.iter_errors(c):
            bad += 1
            print(f"  SCHEMA {c['id']}: {err.message[:140]}")
    print(f"schema violations: {bad}")
    if dropped:
        print(f"off-vocabulary values dropped: {sum(dropped.values())}")
        for k, n in dropped.most_common(12):
            print(f"    {n:3d}  {k}")

    # --- link resolution, both directions ---
    entities = json.loads((DATA / "all-entities.json").read_text("utf-8"))
    alias_path = DATA / "link_aliases.json"
    aliases = json.loads(alias_path.read_text("utf-8")) if alias_path.exists() else {}
    inv_res = Resolver(entities, aliases.get("investors", {}))
    co_res = Resolver(companies, aliases.get("companies", {}))

    edges: dict[tuple[str, str], dict] = {}
    misses: Counter[str] = Counter()
    miss_reason: dict[str, str] = {}

    for c in companies:
        for inv in (c.get("funding") or {}).get("investors") or []:
            eid, how = inv_res.resolve(inv.get("name", ""), c.get("region"))
            inv["entity_id"] = eid
            if eid:
                e = edges.setdefault((eid, c["id"]), {"via": set(), "role": inv.get("role")})
                e["via"].add("company")
            else:
                misses[inv.get("name", "")] += 1
                miss_reason[inv.get("name", "")] = how

    unresolved_portfolio: Counter[str] = Counter()
    for e in entities:
        for n in (e.get("track_record") or {}).get("notable_investments") or []:
            nm = (n.get("company") or "").strip()
            if not nm:
                continue
            # No region hint here, deliberately. An investor's region says
            # little about where its portfolio sits, and two DIFFERENT
            # companies sharing a name is far likelier than two vehicles of one
            # firm sharing a name. Guessing would attach a real investor to the
            # wrong real company; leaving it unresolved just delays the link.
            cid, how = co_res.resolve(nm)
            if cid:
                edge = edges.setdefault((e["id"], cid), {"via": set(), "role": None})
                edge["via"].add("investor")
            else:
                unresolved_portfolio[nm] += 1

    inv_to_co: dict[str, list[str]] = defaultdict(list)
    co_to_inv: dict[str, list[str]] = defaultdict(list)
    both = 0
    for (eid, cid), meta in sorted(edges.items()):
        via = "both" if len(meta["via"]) == 2 else next(iter(meta["via"]))
        both += via == "both"
        inv_to_co[eid].append(cid)
        co_to_inv[cid].append(eid)

    print(f"links: {len(edges)} edge(s) — {both} confirmed from both sides")
    print(f"       {len(inv_to_co)}/{len(entities)} investors and "
          f"{len(co_to_inv)}/{len(companies)} companies are connected")
    print(f"unresolved investor names: {len(misses)} distinct "
          f"({sum(misses.values())} mentions)")
    print(f"unresolved portfolio names: {len(unresolved_portfolio)} distinct "
          f"(companies not yet researched)")

    # --- write derived artifacts ---
    (DATA / "all-companies.json").write_text(
        json.dumps(companies, ensure_ascii=False, indent=2), "utf-8")
    (DATA / "links.json").write_text(json.dumps({
        "investor_to_company": {k: sorted(v) for k, v in sorted(inv_to_co.items())},
        "company_to_investor": {k: sorted(v) for k, v in sorted(co_to_inv.items())},
        "edges": [{"investor": eid, "company": cid,
                   "via": "both" if len(m["via"]) == 2 else next(iter(m["via"]))}
                  for (eid, cid), m in sorted(edges.items())],
    }, ensure_ascii=False, indent=2), "utf-8")

    stats = {
        "total": len(companies),
        "by_region": dict(Counter(c.get("region", "?") for c in companies).most_common()),
        "by_category": dict(Counter(c.get("category", "?") for c in companies).most_common()),
        "by_status": dict(Counter(c.get("status", "unknown") for c in companies).most_common()),
        "by_development_stage": dict(Counter(
            (c.get("profile") or {}).get("development_stage", "unknown") for c in companies).most_common()),
        "by_last_round": dict(Counter(
            ((c.get("funding") or {}).get("last_round") or {}).get("stage", "unknown")
            for c in companies).most_common()),
        "by_confidence": dict(Counter(c.get("confidence", "?") for c in companies).most_common()),
        "linked_companies": len(co_to_inv),
        "linked_investors": len(inv_to_co),
        "edges": len(edges),
        "edges_confirmed_both_sides": both,
        # Shipped to the site so the coverage gap is stated rather than implied.
        # A directory that quietly shows 40 companies reads as "there are 40";
        # showing "40 profiled, 1,400 named by investors and not yet profiled"
        # is the truth and doubles as the public backlog.
        "unprofiled_portfolio_names": len(unresolved_portfolio),
    }
    (DATA / "company-stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), "utf-8")

    # A normalized name that maps to two different records is usually not a
    # coincidence — it is the same organization entered twice. The resolver
    # already refuses to link on it, but refusing silently just hides a data
    # bug, so it is reported. Traditional/simplified folding makes this
    # especially productive on the Chinese records, where one firm entered
    # under both scripts previously looked like two unrelated rows.
    collisions = []
    ent_by_id = {e["id"]: e for e in entities}

    def _host(e: dict) -> str:
        w = (e.get("website") or "").strip().lower()
        return re.sub(r"^https?://(www\.)?", "", w).split("/")[0]

    for key, ids in sorted(inv_res.strict.items()):
        if len(ids) < 2:
            continue
        rows = [ent_by_id[i] for i in sorted(ids) if i in ent_by_id]
        regions = {r.get("region") for r in rows}
        countries = {(r.get("country") or "").strip().lower() for r in rows if r.get("country")}
        hosts = {h for r in rows if (h := _host(r))}

        # `region` is a filing decision, not evidence about the organization.
        # Two rounds of research can put one global foundation in `united-states`
        # and `rest-of-world` purely by disagreeing, which is exactly what
        # happened to the Gates Foundation SIF — same country, same city, same
        # domain, two records. So region alone cannot clear a collision.
        #
        # What actually discriminates is the website and the country. A firm
        # running genuinely separate regional teams (Boehringer Ingelheim
        # Venture Fund, Sanofi Ventures) has offices in different countries;
        # one organization entered twice has the same domain and the same
        # country whatever region it got filed under.
        if len(hosts) == 1 and len(countries) <= 1:
            verdict = "likely-duplicate"          # one domain, one country
        elif len(regions) < len(rows):
            verdict = "likely-duplicate"          # two records in one region
        elif len(countries) > 1 or len(hosts) > 1:
            verdict = "regional-vehicles"         # separate countries or sites
        else:
            verdict = "undetermined"              # not enough to say either way

        collisions.append({
            "normalized": key,
            "ids": sorted(ids),
            "names": [r["name"].get("en", "") for r in rows],
            "countries": sorted(countries),
            "hosts": sorted(hosts),
            "verdict": verdict,
        })
    n_dupe = sum(1 for c in collisions if c["verdict"] == "likely-duplicate")
    n_undet = sum(1 for c in collisions if c["verdict"] == "undetermined")

    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "links.json").write_text(json.dumps({
        "unresolved_investor_names": [
            {"name": n, "mentions": k, "reason": miss_reason.get(n, "")}
            for n, k in misses.most_common()],
        "unresolved_portfolio_companies": [
            {"name": n, "investors_naming_it": k}
            for n, k in unresolved_portfolio.most_common()],
        "investor_name_collisions": collisions,
    }, ensure_ascii=False, indent=2), "utf-8")
    print(f"name collisions: {len(collisions)} — {n_dupe} likely duplicates, "
          f"{len(collisions) - n_dupe - n_undet} per-region vehicles, {n_undet} undetermined")

    print(f"\nwrote data/all-companies.json, data/links.json, data/company-stats.json")
    print(f"      reports/links.json  <- the backlog for the next round")


if __name__ == "__main__":
    main()
