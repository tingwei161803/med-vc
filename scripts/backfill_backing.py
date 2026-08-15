# /// script
# requires-python = ">=3.11"
# ///
"""Infer entity.backing.backers[] and write the overlay file data/backing.json.

`data/<region>/entities.json` and `data/all-entities.json` are DERIVED artifacts —
`build.py` regenerates them from `_raw/`, so writing enrichment there is lost on
the next build. Instead this script emits a standalone overlay keyed by entity id,
which `build.py` merges in during the build. That keeps the layer regenerable,
keeps agent research out of the raw segment files, and lets agent-verified rows
(`evidence: "verified"`) coexist with machine-inferred ones without either
clobbering the other.

Pipeline order:  build.py  ->  backfill_backing.py  ->  build.py

The dataset never had a first-class "whose money is this" field. Corporate parents
were only ever implicit — buried in the org name ("Philips Ventures"), in tags
(1,053 distinct free-text tags, unusable for filtering), or in prose. This script
lifts that into structured `backing.backers[]` so the site can answer
"which of these funds have a heavyweight standing behind them?".

Three extraction passes, in precision order — later passes run only when the
earlier ones found nothing:

  1. NAME MATCH — the entity's own name/aka contains a registry org
     ("Sony Innovation Fund" -> Sony). Very high precision for CVCs, because
     corporate venture arms are near-universally named after their parent.

  2. PHRASE MATCH — prose in summary/thesis states a backing relationship
     ("the corporate venture arm of X", "backed by X", "anchored by X").
     We only accept an org when it appears inside one of these relationship
     frames; a bare mention of Google in a thesis means nothing.

  3. UNLISTED PARENT — for CVCs whose parent is real but not a registry
     heavyweight (Kasikornbank, Sinar Mas Land, Zydus Lifesciences). The org
     name is taken verbatim from the prose instead of being registry-matched,
     which is only safe because this pass is gated on the entity's own tags
     already fixing the backer `kind` — so a stray capture can put a wrong name
     on a row, but never invent a category. Falls back to deriving the parent
     from the fund's name when the prose does not say.

Everything written here is marked `evidence: "inferred"`. Rows researched by an
agent with a citation carry `evidence: "verified"` and are never overwritten.

Run:  uv run scripts/backfill_backing.py            # write
      uv run scripts/backfill_backing.py --dry-run  # report only
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# --------------------------------------------------------------------------
# Registry of notable backer organizations.
#   canonical -> (kind, [alias regexes])
# Aliases are matched case-insensitively with word boundaries. Keep them
# specific enough not to collide (e.g. "Apple" would swallow "Apple Tree
# Partners", so Apple is matched only as "Apple Inc"/"Apple Health").
# --------------------------------------------------------------------------
REGISTRY: dict[str, tuple[str, list[str]]] = {
    # ---- Big Tech ----------------------------------------------------------
    "Alphabet / Google": ("big-tech", [r"Alphabet", r"Google", r"GV \(Google Ventures\)", r"CapitalG", r"Verily"]),
    "Microsoft": ("big-tech", [r"Microsoft", r"\bM12\b"]),
    # "AWS" is deliberately absent: Austria's promotional bank is also called aws.
    "Amazon": ("big-tech", [r"Amazon", r"Alexa Fund"]),
    "Apple": ("big-tech", [r"Apple Inc", r"Apple Health"]),
    "Meta": ("big-tech", [r"Meta Platforms", r"\bFacebook\b"]),
    "NVIDIA": ("big-tech", [r"NVIDIA", r"NVentures"]),
    "Intel": ("big-tech", [r"Intel Corporation", r"Intel Capital"]),
    "IBM": ("big-tech", [r"\bIBM\b"]),
    "Oracle": ("big-tech", [r"Oracle", r"\bCerner\b"]),
    "Salesforce": ("big-tech", [r"Salesforce"]),
    "Qualcomm": ("big-tech", [r"Qualcomm"]),
    "Cisco": ("big-tech", [r"Cisco"]),
    "Dell Technologies": ("big-tech", [r"Dell Technologies"]),
    "SAP": ("big-tech", [r"\bSAP\b"]),
    "Tencent": ("big-tech", [r"Tencent", r"腾讯", r"騰訊"]),
    "Alibaba / Ant Group": ("big-tech", [r"Alibaba", r"Ant Group", r"阿里巴巴"]),
    "Baidu": ("big-tech", [r"Baidu", r"百度"]),
    "ByteDance": ("big-tech", [r"ByteDance", r"字节跳动"]),
    "Xiaomi": ("big-tech", [r"Xiaomi", r"小米"]),
    "Naver": ("big-tech", [r"\bNaver\b"]),
    "Kakao": ("big-tech", [r"Kakao"]),
    "Sony": ("big-tech", [r"\bSony\b"]),
    "Panasonic": ("big-tech", [r"Panasonic"]),
    "Samsung": ("big-tech", [r"Samsung", r"삼성"]),
    "LG": ("big-tech", [r"\bLG Electronics\b", r"\bLG Corp", r"LG Technology Ventures", r"LG Chem"]),
    "Grab": ("big-tech", [r"\bGrab Holdings\b"]),
    "Sea Group": ("big-tech", [r"\bSea Group\b", r"\bSea Limited\b"]),
    "Rakuten": ("big-tech", [r"Rakuten"]),
    "SoftBank": ("big-tech", [r"SoftBank", r"ソフトバンク"]),
    "Siemens": ("big-tech", [r"\bSiemens\b(?! Healthineers)", r"next47"]),

    # ---- Frontier AI labs --------------------------------------------------
    "OpenAI": ("ai-lab", [r"OpenAI"]),
    "Anthropic": ("ai-lab", [r"Anthropic"]),
    "Google DeepMind": ("ai-lab", [r"DeepMind", r"Isomorphic Labs"]),
    "xAI": ("ai-lab", [r"\bxAI\b"]),
    "Mistral AI": ("ai-lab", [r"Mistral AI"]),

    # ---- Pharma ------------------------------------------------------------
    "Johnson & Johnson": ("pharma", [r"Johnson & Johnson", r"Johnson and Johnson", r"\bJ&J\b", r"JJDC", r"JLABS", r"Janssen"]),
    "Pfizer": ("pharma", [r"Pfizer"]),
    "Roche": ("pharma", [r"\bRoche\b", r"Genentech"]),
    "Novartis": ("pharma", [r"Novartis"]),
    "Merck & Co (MSD)": ("pharma", [r"Merck & Co", r"\bMSD\b", r"Merck Research"]),
    # \b matters: an unanchored "M Ventures" also matches "Qualcomm Ventures".
    "Merck KGaA": ("pharma", [r"Merck KGaA", r"\bM Ventures\b"]),
    "AstraZeneca": ("pharma", [r"AstraZeneca", r"MedImmune", r"Alexion"]),
    "GSK": ("pharma", [r"\bGSK\b", r"GlaxoSmithKline", r"SR One"]),
    "Sanofi": ("pharma", [r"Sanofi"]),
    "Bayer": ("pharma", [r"\bBayer\b", r"Leaps by Bayer"]),
    "Eli Lilly": ("pharma", [r"Eli Lilly", r"\bLilly\b"]),
    "Bristol Myers Squibb": ("pharma", [r"Bristol[- ]Myers", r"\bBMS\b"]),
    "AbbVie": ("pharma", [r"AbbVie"]),
    "Amgen": ("pharma", [r"Amgen"]),
    "Gilead": ("pharma", [r"Gilead"]),
    "Takeda": ("pharma", [r"Takeda", r"武田"]),
    "Astellas": ("pharma", [r"Astellas"]),
    "Daiichi Sankyo": ("pharma", [r"Daiichi Sankyo"]),
    "Eisai": ("pharma", [r"Eisai"]),
    "Otsuka": ("pharma", [r"Otsuka"]),
    "Shionogi": ("pharma", [r"Shionogi"]),
    "Chugai": ("pharma", [r"Chugai"]),
    "Boehringer Ingelheim": ("pharma", [r"Boehringer Ingelheim"]),
    "Novo Nordisk / Novo Holdings": ("pharma", [r"Novo Nordisk", r"Novo Holdings"]),
    "Lundbeck": ("pharma", [r"Lundbeck"]),
    "Ipsen": ("pharma", [r"Ipsen"]),
    "Servier": ("pharma", [r"Servier"]),
    "UCB": ("pharma", [r"\bUCB\b"]),
    "Debiopharm": ("pharma", [r"Debiopharm"]),
    "Vertex Pharmaceuticals": ("pharma", [r"Vertex Pharmaceuticals"]),
    "Regeneron": ("pharma", [r"Regeneron"]),
    "Biogen": ("pharma", [r"Biogen"]),
    "Moderna": ("pharma", [r"Moderna"]),
    "BioNTech": ("pharma", [r"BioNTech"]),
    "Teva": ("pharma", [r"\bTeva\b"]),
    # \b matters: unanchored "Sun Pharma" also matches "Fosun Pharma".
    "Sun Pharma": ("pharma", [r"\bSun Pharma\b"]),
    "Dr. Reddy's": ("pharma", [r"Dr\.? Reddy"]),
    "Cipla": ("pharma", [r"\bCipla\b"]),
    "Hanmi": ("pharma", [r"Hanmi"]),
    "Yuhan": ("pharma", [r"Yuhan"]),
    "Celltrion": ("pharma", [r"Celltrion"]),
    "Fosun Pharma": ("pharma", [r"Fosun", r"复星"]),
    "Hengrui": ("pharma", [r"Hengrui", r"恒瑞"]),
    "WuXi": ("pharma", [r"WuXi", r"药明"]),
    "CSL": ("pharma", [r"\bCSL\b", r"CSL Behring"]),

    # ---- Medtech / devices -------------------------------------------------
    "Medtronic": ("medtech", [r"Medtronic"]),
    "Abbott": ("medtech", [r"Abbott"]),
    "Boston Scientific": ("medtech", [r"Boston Scientific"]),
    "Stryker": ("medtech", [r"Stryker"]),
    "Becton Dickinson": ("medtech", [r"Becton[, ]+Dickinson", r"\bBD\b"]),
    "Baxter": ("medtech", [r"Baxter"]),
    "Edwards Lifesciences": ("medtech", [r"Edwards Lifesciences"]),
    "Zimmer Biomet": ("medtech", [r"Zimmer Biomet"]),
    "Intuitive Surgical": ("medtech", [r"Intuitive Surgical"]),
    "Philips": ("medtech", [r"\bPhilips\b"]),
    "Siemens Healthineers": ("medtech", [r"Siemens Healthineers"]),
    "GE HealthCare": ("medtech", [r"GE HealthCare", r"GE Healthcare"]),
    "B. Braun": ("medtech", [r"B\.? Braun"]),
    "Fresenius": ("medtech", [r"Fresenius"]),
    "Olympus": ("medtech", [r"Olympus"]),
    "Terumo": ("medtech", [r"Terumo"]),
    "Nipro": ("medtech", [r"\bNipro\b"]),
    "ZEISS": ("medtech", [r"ZEISS", r"Zeiss"]),
    "Dentsply Sirona": ("medtech", [r"Dentsply"]),
    "Coloplast": ("medtech", [r"Coloplast"]),
    "Demant": ("medtech", [r"William Demant", r"\bDemant\b"]),
    "Getinge": ("medtech", [r"Getinge"]),
    "Canon Medical": ("medtech", [r"Canon Medical", r"\bCanon Inc\b"]),
    "Fujifilm": ("medtech", [r"Fujifilm", r"FUJIFILM"]),
    "Konica Minolta": ("medtech", [r"Konica Minolta"]),

    # ---- Diagnostics / life-science tools ----------------------------------
    "Thermo Fisher Scientific": ("diagnostics-tools", [r"Thermo Fisher"]),
    "Danaher": ("diagnostics-tools", [r"Danaher", r"Cytiva"]),
    "Illumina": ("diagnostics-tools", [r"Illumina"]),
    "Agilent": ("diagnostics-tools", [r"Agilent"]),
    "Qiagen": ("diagnostics-tools", [r"Qiagen", r"QIAGEN"]),
    "bioMérieux": ("diagnostics-tools", [r"bioM[ée]rieux"]),
    "Sartorius": ("diagnostics-tools", [r"Sartorius"]),
    "Merck Millipore": ("diagnostics-tools", [r"MilliporeSigma", r"Merck Millipore"]),
    "Quest Diagnostics": ("diagnostics-tools", [r"Quest Diagnostics"]),
    "Labcorp": ("diagnostics-tools", [r"Labcorp", r"LabCorp"]),
    "Sonic Healthcare": ("diagnostics-tools", [r"Sonic Healthcare"]),
    "Oxford Nanopore": ("diagnostics-tools", [r"Oxford Nanopore"]),
    "BGI": ("diagnostics-tools", [r"\bBGI\b", r"华大"]),

    # ---- Payers / insurers -------------------------------------------------
    "UnitedHealth Group": ("payer-insurer", [r"UnitedHealth", r"Optum"]),
    "CVS Health": ("payer-insurer", [r"CVS Health", r"\bAetna\b"]),
    "Cigna": ("payer-insurer", [r"\bCigna\b", r"Evernorth"]),
    "Elevance Health": ("payer-insurer", [r"Elevance", r"Anthem"]),
    "Humana": ("payer-insurer", [r"Humana"]),
    "Blue Cross Blue Shield": ("payer-insurer", [r"Blue Cross", r"BlueCross", r"\bBCBS\b"]),
    "Kaiser Permanente": ("payer-insurer", [r"Kaiser Permanente"]),
    "Bupa": ("payer-insurer", [r"\bBupa\b"]),
    "Medibank": ("payer-insurer", [r"Medibank"]),
    "AXA": ("payer-insurer", [r"\bAXA\b"]),
    "Allianz": ("payer-insurer", [r"Allianz"]),
    "Munich Re": ("payer-insurer", [r"Munich Re"]),
    "Zurich Insurance": ("payer-insurer", [r"Zurich Insurance", r"Zurich Global Ventures"]),
    "Ping An": ("payer-insurer", [r"Ping An", r"平安"]),
    "Nippon Life": ("payer-insurer", [r"Nippon Life", r"日本生命"]),
    "Dai-ichi Life": ("payer-insurer", [r"Dai-ichi Life"]),
    "Discovery Health": ("payer-insurer", [r"Discovery Health", r"Discovery Limited"]),

    # ---- Conglomerates / retail / telecom ---------------------------------
    "Mitsubishi": ("conglomerate", [r"Mitsubishi"]),
    "Mitsui": ("conglomerate", [r"Mitsui"]),
    "Sumitomo": ("conglomerate", [r"Sumitomo"]),
    "Marubeni": ("conglomerate", [r"Marubeni"]),
    "Itochu": ("conglomerate", [r"Itochu", r"ITOCHU"]),
    "Hitachi": ("conglomerate", [r"Hitachi"]),
    "Toshiba": ("conglomerate", [r"Toshiba"]),
    "SK Group": ("conglomerate", [r"\bSK Group\b", r"SK Holdings", r"SK Telecom", r"SK biopharm"]),
    "Hyundai": ("conglomerate", [r"Hyundai"]),
    "Lotte": ("conglomerate", [r"\bLotte\b"]),
    "Tata Group": ("conglomerate", [r"Tata Sons", r"Tata Group", r"Tata Capital"]),
    "Reliance Industries": ("conglomerate", [r"Reliance Industries", r"Jio Platforms"]),
    "Wesfarmers": ("conglomerate", [r"Wesfarmers"]),
    "Bosch": ("conglomerate", [r"Robert Bosch", r"Bosch Ventures"]),
    "Merck Group": ("conglomerate", [r"Merck Group"]),
    "Nestlé": ("retail-consumer", [r"Nestl[ée]"]),
    "Danone": ("retail-consumer", [r"Danone"]),
    "Unilever": ("retail-consumer", [r"Unilever"]),
    "Walmart": ("retail-consumer", [r"Walmart"]),
    "Walgreens": ("retail-consumer", [r"Walgreens", r"Boots Alliance"]),
    "Woolworths": ("retail-consumer", [r"Woolworths"]),
    "Best Buy": ("retail-consumer", [r"Best Buy"]),
    "Procter & Gamble": ("retail-consumer", [r"Procter & Gamble", r"\bP&G\b"]),
    "L'Oréal": ("retail-consumer", [r"L'Or[ée]al"]),
    "Telstra": ("telecom", [r"Telstra"]),
    "TELUS": ("telecom", [r"TELUS", r"Telus"]),
    "NTT": ("telecom", [r"\bNTT\b", r"NTT Docomo"]),
    "KDDI": ("telecom", [r"\bKDDI\b"]),
    "Deutsche Telekom": ("telecom", [r"Deutsche Telekom"]),
    "Singtel": ("telecom", [r"Singtel", r"SingTel"]),
    "China Mobile": ("telecom", [r"China Mobile"]),

    # ---- Financial institutions / sovereign --------------------------------
    "Goldman Sachs": ("financial-institution", [r"Goldman Sachs"]),
    "Morgan Stanley": ("financial-institution", [r"Morgan Stanley"]),
    "J.P. Morgan": ("financial-institution", [r"J\.?P\.? Morgan", r"JPMorgan"]),
    "BlackRock": ("financial-institution", [r"BlackRock"]),
    "Fidelity": ("financial-institution", [r"Fidelity Investments", r"Fidelity Management"]),
    "T. Rowe Price": ("financial-institution", [r"T\.? Rowe Price"]),
    "Wellington Management": ("financial-institution", [r"Wellington Management"]),
    "Baillie Gifford": ("financial-institution", [r"Baillie Gifford"]),
    "Temasek": ("government", [r"Temasek"]),
    "GIC": ("government", [r"\bGIC\b"]),
    "Mubadala": ("government", [r"Mubadala"]),
    "PIF (Saudi)": ("government", [r"Public Investment Fund", r"\bPIF\b"]),
    "Qatar Investment Authority": ("government", [r"Qatar Investment Authority", r"\bQIA\b"]),
    "EIF / European Investment Fund": ("government", [r"European Investment Fund", r"European Investment Bank"]),
    "British Patient Capital": ("government", [r"British Patient Capital", r"British Business Bank"]),
    "Bpifrance": ("government", [r"Bpifrance"]),
    "JIC (Japan Investment Corp)": ("government", [r"Japan Investment Corporation", r"\bJIC\b", r"INCJ"]),
    "KDB (Korea Development Bank)": ("government", [r"Korea Development Bank", r"\bKDB\b"]),
    "National Development Fund (Taiwan)": ("government", [r"National Development Fund", r"國發基金"]),
    "EDBI / Enterprise Singapore": ("government", [r"\bEDBI\b", r"Enterprise Singapore", r"SGInnovate"]),
    "BARDA / NIH / ARPA-H": ("government", [r"\bBARDA\b", r"\bNIH\b", r"ARPA-H"]),

    # ---- Foundations -------------------------------------------------------
    "Gates Foundation": ("foundation", [r"Gates Foundation", r"Bill & Melinda Gates"]),
    "Wellcome Trust": ("foundation", [r"Wellcome Trust", r"Wellcome Leap"]),
    "Chan Zuckerberg Initiative": ("foundation", [r"Chan Zuckerberg"]),
    "Howard Hughes Medical Institute": ("foundation", [r"Howard Hughes Medical"]),
    "Cystic Fibrosis Foundation": ("foundation", [r"Cystic Fibrosis Foundation"]),
    "Michael J. Fox Foundation": ("foundation", [r"Michael J\.? Fox"]),
    "Leukemia & Lymphoma Society": ("foundation", [r"Leukemia & Lymphoma Society", r"\bLLS\b"]),
    "Novo Nordisk Foundation": ("foundation", [r"Novo Nordisk Foundation"]),
    "Wallenberg Foundations": ("foundation", [r"Wallenberg"]),
}

# Prose frames that actually assert a backing relationship. The org name is
# captured, then looked up in REGISTRY — a bare mention elsewhere in the
# sentence is ignored, which is what keeps co-investor noise out.
# The capture allows commas so multi-backer lists ("backed by Tata Group,
# Temasek and others") yield every org, not just the first.
_ORG = r"([A-Z][\w&.\-', ]{2,60})"
PHRASE_FRAMES: list[tuple[str, str]] = [
    (rf"(?:corporate )?(?:venture|investment|innovation) (?:arm|unit|fund|vehicle) of {_ORG}", "wholly-owned-cvc"),
    (rf"wholly[- ]owned (?:subsidiary|venture arm) of {_ORG}", "wholly-owned-cvc"),
    (rf"\bsubsidiary of {_ORG}", "wholly-owned-cvc"),
    (rf"funded (?:entirely |solely )?(?:off|from) (?:the )?balance sheet of {_ORG}", "balance-sheet-fund"),
    (rf"\b(?:jointly )?(?:backed|established|founded|created) by {_ORG}", "major-lp"),
    (rf"\banchored by {_ORG}", "anchor-lp"),
    (rf"\banchor (?:LP|investor) {_ORG}", "anchor-lp"),
    (rf"\bsponsored by {_ORG}", "affiliated-program"),
    (rf"\bspun out (?:of|from) {_ORG}", "spinout"),
    (rf"\bjoint venture (?:between|with) {_ORG}", "joint-venture"),
    (rf"\b{_ORG}'s (?:corporate )?(?:venture|investment) arm", "wholly-owned-cvc"),
]

# A capture mentioning a person's title describes an individual, not corporate
# money: "the investment vehicle of SAP co-founder Dietmar Hopp" is Hopp's
# family office, and SAP the company has nothing to do with it.
PERSON_GUARD = re.compile(
    r"\b(co-?founder|founder|chairman|chairwoman|\bCEO\b|\bCTO\b|executive|alumn|veteran|former)\b",
    re.IGNORECASE,
)

# Entity types where a name match implies the parent, rather than just a
# coincidence of words. A "vc" called "Sequoia China Smart Healthcare
# Accelerator" is not backed by a registry org just because a word matched.
NAME_MATCH_TYPES = {"cvc", "venture-studio", "accelerator", "incubator", "government-program"}
# Fund types where a match on a BANK/ASSET-MANAGER name implies sponsorship
# rather than ownership. Deliberately not applied to other backer kinds: a VC
# sharing a word with a pharma company is a coincidence, not a parent.
FUND_MATCH_TYPES = {"vc", "growth-equity", "crossover-fund", "micro-vc"}

_COMPILED = {
    canonical: (kind, [re.compile(a, re.IGNORECASE) for a in aliases])
    for canonical, (kind, aliases) in REGISTRY.items()
}
_FRAMES = [(re.compile(p), rel) for p, rel in PHRASE_FRAMES]


def lookup(text: str) -> list[tuple[str, str]]:
    """Return [(canonical, kind)] for every registry org named in `text`."""
    hits = []
    for canonical, (kind, patterns) in _COMPILED.items():
        if any(p.search(text) for p in patterns):
            hits.append((canonical, kind))
    return hits


def canonical_of(name: str) -> str | None:
    """Registry identity for a backer name, or None if it is not a known org.

    Researchers write "Microsoft Corporation", "Amazon.com, Inc.", "Intel
    Corporation"; the inference layer writes "Microsoft", "Amazon", "Intel".
    Deduplicating on the raw string lists the same parent twice, so both layers
    are compared through this instead. build.py imports it for that merge.
    """
    hits = lookup(name)
    return hits[0][0] if hits else None


def _is_self_reference(e: dict, canonical: str) -> bool:
    """True when the registry org IS the entity, rather than a backer of it.

    Several registry organizations are themselves listed investors, so a bare
    name match would record "T. Rowe Price is backed by T. Rowe Price".

    Exact match is the whole test, and deliberately so: an entity whose name
    merely *contains* the firm is a named sub-vehicle of it — "Wellington
    Management (Private Biotech)", "Baillie Gifford (Health Innovation)" — and
    for those the firm genuinely is the sponsor, which is worth recording.
    """
    return norm(e.get("name", {}).get("en", "")) == norm(canonical)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def from_name(e: dict) -> list[dict]:
    etype = e.get("type")
    haystack = " ".join([e.get("name", {}).get("en", ""), *(e.get("aka") or [])])
    out = []
    for canonical, kind in lookup(haystack):
        if _is_self_reference(e, canonical):
            continue
        if etype in NAME_MATCH_TYPES:
            # A corporate venture arm named after its parent is owned by it.
            out.append({
                "name": canonical, "kind": kind, "relationship": "wholly-owned-cvc",
                "note": f"Named after its parent organization ({canonical}); relationship inferred from the entity name.",
                "evidence": "inferred"})
        elif kind == "financial-institution" and etype in FUND_MATCH_TYPES:
            # A bank or asset manager's named fund is sponsored and managed by
            # it, but capitalized by outside LPs — structurally the opposite of
            # a wholly-owned CVC. Verified as such for Goldman's West Street
            # Life Sciences fund, which is the template for this rule.
            out.append({
                "name": canonical, "kind": kind, "relationship": "sponsor-gp",
                "note": (f"Carries {canonical}'s name, so {canonical} sponsors and manages the vehicle; "
                         "such funds are typically raised from external LPs rather than the institution's "
                         "own balance sheet. Relationship inferred from the entity name — confirm the "
                         "capital source before relying on it."),
                "evidence": "inferred"})
    return out


# A CVC's parent is often real but not a REGISTRY heavyweight — "nib Group" is
# an Australian health insurer, "HBF Ventures" belongs to HBF. The registry
# cannot know them, but the entity's own tags often already state what KIND of
# organization the parent is, which is the half of the row that cannot be
# guessed from the name. Only tags that describe the PARENT's industry are
# listed; tags like "medtech" or "digital-health" describe what the fund invests
# in, not who owns it, so they are deliberately absent.
TAG_KIND_HINTS = {
    "payer-cvc": "payer-insurer",
    "health-insurer": "payer-insurer",
    "insurtech-cvc": "payer-insurer",
    "blue-plan": "payer-insurer",
    "provider-cvc": "hospital-system",
    "hospital-venture": "hospital-system",
    "hospital-operator": "hospital-system",
    "academic-medical-center": "hospital-system",
    "pharma-cvc": "pharma",
    "specialty-pharma": "pharma",
    "telecom-cvc": "telecom",
    "bank-cvc": "financial-institution",
    "conglomerate-cvc": "conglomerate",
    "retail-cvc": "retail-consumer",
    "retail-conglomerate-cvc": "retail-consumer",
    "dairy-cooperative-cvc": "other",
}

# Words that mark the tail of a fund's name rather than part of the parent's.
_FUND_SUFFIX = re.compile(
    r"\s*[-—–]?\s*(?:Corporate\s+)?(?:Venture\s+Capital\s+Fund|Corporate\s+Venture\s+Capital|"
    r"Venture\s+Capital|Venture\s+Management|Venture\s+Group|Ventures?|Capital|Investments?|"
    r"Innovation\s+Fund|Venture\s+Fund|New\s+Ventures|Enterprises|Holdings?|Fund|CVC)\s*$",
    re.IGNORECASE,
)
# A parenthetical that names the actual corporate parent, e.g.
# "Bausch + Lomb (Bausch Health Companies)".
_PAREN_PARENT = re.compile(
    r"\(([^)]*\b(?:Group|Holdings?|Compan(?:y|ies)|Inc\.?|Corp\.?|Corporation|Ltd\.?|"
    r"Limited|plc|PLC|AB|AG|S\.?A\.?|N\.?V\.?)\b[^)]*)\)")

# Hand-vetted exclusions: rows this heuristic gets wrong, confirmed by reading
# the entity. Ki Tua is Fonterra's fund but carries no trace of Fonterra in its
# name, so name-derivation would assert it is its own parent.
UNLISTED_PARENT_DENY = {"anz-ki-tua-fonterra"}


# Frames used ONLY for unlisted parents. They are looser than PHRASE_FRAMES
# because the captured text is taken verbatim as the parent name instead of
# being matched against the registry, and they only ever run for a CVC whose
# tags already fix the backer kind — so a stray capture cannot invent a new
# category, only a wrong name on a row already marked `inferred`.
_UNLISTED_FRAMES = [
    (re.compile(rf"(?:corporate\s+)?(?:venture|investment|innovation)\s+(?:capital\s+)?"
                rf"(?:arm|unit|fund|vehicle)\s+(?:of|launched by)\s+{_ORG}"), "wholly-owned-cvc"),
    (re.compile(rf"\bCVC\s+(?:arm\s+)?of\s+{_ORG}"), "wholly-owned-cvc"),
    (re.compile(rf"\b{_ORG}'s\s+(?:wholly[- ]owned\s+)?(?:corporate\s+)?(?:CVC|VC|venture|investment)\b"),
     "wholly-owned-cvc"),
    (re.compile(rf"\b(?:launched|established|founded)\s+by\s+{_ORG}"), "wholly-owned-cvc"),
    (re.compile(rf"\banchored by\s+{_ORG}"), "anchor-lp"),
]
# Corporate-form tokens that legitimately follow a comma inside a company name.
_CORP_TAIL = re.compile(r"^(?:Inc|Corp|Corporation|Ltd|Limited|LLC|LP|S\.?A|N\.?V|AG|AB|plc|PLC|Co)\b", re.I)
# Descriptors a capture may open with; the company name is what follows.
_LEAD_DESCRIPTOR = re.compile(
    r"^(?:Brazilian|Indonesian|Japanese|Korean|Chinese|Indian|Thai|Malaysian|Singaporean|Australian|"
    r"German|French|Swiss|Dutch|Spanish|Italian|Nordic|European|American|general insurer|insurer|"
    r"pharmaceutical group|pharma group|health insurer|telecom operator|conglomerate)\s+",
    re.I)


# Lowercase words that legitimately sit inside a company name.
_NAME_CONNECTORS = {"&", "de", "del", "der", "van", "von", "of", "y", "e"}


def _clean_org(span: str) -> str:
    """Trim a prose capture down to just the organization name.

    A capture routinely runs past the name into the rest of the sentence
    ("Eurofarma in 2019 with R$45M", "Providence and additional strategic LPs").
    Company names are title-cased, so keeping only the leading run of
    capitalized tokens cuts each of those at the right place.
    """
    span = span.split(". ")[0].strip()
    # a comma usually starts a continuation clause ("Zydus Lifesciences, backing
    # next-generation medtech…") unless it introduces a corporate form
    if "," in span:
        head, tail = span.split(",", 1)
        if not _CORP_TAIL.match(tail.strip()):
            span = head
    while True:
        stripped = _LEAD_DESCRIPTOR.sub("", span.strip())
        if stripped == span.strip():
            break
        span = stripped

    # Collect every run of title-cased tokens, then keep the longest — ties go
    # to the first. A descriptor prefix is almost always shorter than the name
    # it introduces ("Philippine telecom Globe Telecom" -> "Globe Telecom"),
    # while trailing sentence debris is short and late ("Eurofarma in 2019 with
    # R" -> "Eurofarma", "Providence and additional strategic LPs" ->
    # "Providence").
    runs: list[list[str]] = []
    current: list[str] = []
    for w in span.split():
        if w[:1].isupper() or (current and (w.isdigit() or w.lower() in _NAME_CONNECTORS)):
            current.append(w)
        else:
            if current:
                runs.append(current)
            current = []
    if current:
        runs.append(current)
    if not runs:
        return ""
    best = max(runs, key=len)
    while best and best[-1].lower() in _NAME_CONNECTORS:
        best = best[:-1]
    return " ".join(best[:6]).strip(" -–—&")


def from_unlisted_parent(e: dict) -> list[dict]:
    """Find a corporate parent the registry does not know about.

    Runs only for CVCs nothing else could place, and only when a tag states what
    kind of organization the parent is — prose can supply *who*, but not *what
    sort*, and a guessed `kind` would poison the facet this feature exists for.

    Prose first, because these entities usually say it outright ("Globe
    Telecom's corporate VC arm", "corporate venture capital arm of Zydus
    Lifesciences"); the main extractor misses them only because it requires a
    registry match, which by definition these parents fail. Name derivation is
    the fallback, in three shapes:

      "Bausch + Lomb (Bausch Health Companies)" -> the parenthetical is the parent
      "HBF Ventures"                            -> strip the fund suffix -> HBF
      "Ramsay Health Care"                      -> no suffix to strip: the company
                                                   itself is the investor, so the
                                                   money is its own balance sheet

    Everything produced here is `inferred` and says so in its note.
    """
    if e.get("type") != "cvc" or e.get("id") in UNLISTED_PARENT_DENY:
        return []
    kind = next((TAG_KIND_HINTS[t] for t in (e.get("tags") or []) if t in TAG_KIND_HINTS), None)
    if kind is None:
        return []

    name_en = (e.get("name") or {}).get("en", "").strip()
    prose = " ".join([
        (e.get("summary", {}) or {}).get("en", ""),
        (e.get("strategy", {}) or {}).get("thesis", ""),
    ])
    for frame, relationship in _UNLISTED_FRAMES:
        m = frame.search(prose)
        if not m:
            continue
        org = _clean_org(m.group(1))
        # "Perth-based not-for-profit health insurer HBF" puts the name last, so
        # a leading-run capture returns a descriptor; and a capture that merely
        # restates the entity ("Telkomsel Ventures is Telkomsel's…") names no
        # parent at all. Both fall through to name derivation, which does better.
        if len(org) < 3 or PERSON_GUARD.search(org) or "-based" in org.lower():
            continue
        if norm(org).startswith(norm(name_en)):
            continue
        return [{"name": org, "kind": kind, "relationship": relationship,
                 "note": f"Parent named in the entity's own description: “{m.group(0).strip()[:140]}”. "
                         f"Backer kind taken from the entity's tags. Inferred, not separately sourced.",
                 "evidence": "inferred"}]

    name = name_en
    if not name:
        return []

    paren = _PAREN_PARENT.search(name)
    if paren:
        return [{"name": paren.group(1).strip(), "kind": kind, "relationship": "wholly-owned-cvc",
                 "note": "Parent organization named in the entity's own title; inferred, not separately sourced.",
                 "evidence": "inferred"}]

    bare = re.sub(r"\s*\([^)]*\)", "", name).strip()
    stripped = _FUND_SUFFIX.sub("", bare).strip()
    if stripped and stripped != bare:
        return [{"name": stripped, "kind": kind, "relationship": "wholly-owned-cvc",
                 "note": f"Fund named after its parent ({stripped}); parent derived from the entity name and "
                         f"kind from its own tags — inferred, not separately sourced.",
                 "evidence": "inferred"}]

    return [{"name": bare, "kind": kind, "relationship": "balance-sheet-fund",
             "note": "The name carries no separate fund identity, so the operating company appears to invest "
                     "directly off its own balance sheet rather than through a named vehicle — inferred from "
                     "the entity name and tags, not separately sourced.",
             "evidence": "inferred"}]


def from_prose(e: dict) -> list[dict]:
    prose = " ".join([
        (e.get("summary", {}) or {}).get("en", ""),
        (e.get("strategy", {}) or {}).get("thesis", ""),
        e.get("verification_notes", "") or "",
    ])
    out = []
    for frame, relationship in _FRAMES:
        for m in frame.finditer(prose):
            # the capture may run past a sentence break because "." is allowed
            # inside org names ("Inc."); keep only the first sentence of it
            span = m.group(1).split(". ")[0]
            if PERSON_GUARD.search(span):
                continue
            for canonical, kind in lookup(span):
                out.append({
                    "name": canonical, "kind": kind, "relationship": relationship,
                    "note": f"From the entity description: “{m.group(0).strip()[:160]}”",
                    "evidence": "inferred",
                })
    return out


def merge(existing: list[dict], found: list[dict]) -> list[dict]:
    """Union by backer name. Researched rows (evidence=verified) always win."""
    by_name = {b["name"]: b for b in existing}
    for b in found:
        prior = by_name.get(b["name"])
        if prior is None:
            by_name[b["name"]] = b
        elif prior.get("evidence") != "verified":
            # keep the stronger relationship claim: a name match beats a loose
            # "backed by" phrase for the same org
            rank = {"wholly-owned-cvc": 0, "balance-sheet-fund": 1, "spinout": 2,
                    "joint-venture": 3, "sponsor-gp": 4, "anchor-lp": 5, "major-lp": 6,
                    "affiliated-program": 7}
            if rank.get(b["relationship"], 9) < rank.get(prior["relationship"], 9):
                by_name[b["name"]] = b
    return list(by_name.values())


OVERLAY = DATA / "backing.json"


def main(dry_run: bool = False) -> None:
    entities = json.loads((DATA / "all-entities.json").read_text("utf-8"))
    # keep whatever is already there — agent-researched rows live in the same file
    overlay: dict[str, dict] = json.loads(OVERLAY.read_text("utf-8")) if OVERLAY.exists() else {}

    by_kind: dict[str, int] = {}
    inferred = verified = 0

    for e in entities:
        eid = e["id"]
        # Only hand/agent-verified rows survive a regeneration. Previously
        # inferred rows are discarded and re-derived, otherwise a fixed regex
        # never actually removes the bad row it used to produce — e.g. an
        # unanchored "Sun Pharma" pattern matching "Fosun Pharma" would linger
        # in the overlay forever after the pattern was corrected.
        prior = [b for b in ((overlay.get(eid) or {}).get("backers") or [])
                 if b.get("evidence") == "verified"]
        found = from_name(e) + from_prose(e)
        # last resort, and only when nothing better placed the parent: a
        # registry hit or a sourced prose relationship always wins over a name
        # derivation, so this never overwrites a stronger signal
        if not found:
            found = from_unlisted_parent(e)
        merged = merge(prior, found)
        if not merged:
            continue
        entry = overlay.setdefault(eid, {})
        entry["backers"] = merged
        entry["name"] = e["name"]["en"]  # human-readable anchor for hand-editing
        for b in merged:
            by_kind[b["kind"]] = by_kind.get(b["kind"], 0) + 1
            if b.get("evidence") == "verified":
                verified += 1
            else:
                inferred += 1

    # drop ids that no longer exist in the dataset
    live = {e["id"] for e in entities}
    overlay = {k: v for k, v in overlay.items() if k in live}

    if not dry_run:
        OVERLAY.write_text(json.dumps(dict(sorted(overlay.items())), ensure_ascii=False, indent=2) + "\n", "utf-8")

    verb = "would write" if dry_run else "wrote"
    print(f"{verb} {OVERLAY.relative_to(ROOT)} — {len(overlay)} entities, "
          f"{inferred + verified} backer rows ({verified} verified, {inferred} inferred)")
    for kind, n in sorted(by_kind.items(), key=lambda kv: -kv[1]):
        print(f"  {n:4d}  {kind}")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
