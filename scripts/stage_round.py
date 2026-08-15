# /// script
# requires-python = ">=3.11"
# ///
"""Move one research round's agent output into the repo's _raw/ directories.

    uv run scripts/stage_round.py <dir> <round-prefix>
    uv run scripts/stage_round.py /tmp/scratch r5

Agents write one JSON file per slice, each `{"companies": [...]}` or
`{"entities": [...]}` plus `wanted` / `skipped` / `rejected` / `notes`. This
routes each part to where the build expects it:

    {"companies": [...]}  -> data/companies/_raw/<slice>.json
    {"entities":  [...]}  -> data/<region>/_raw/<slice>.json   (split by region)
    wanted/skipped/rejected/notes -> reports/research-backlog.json

Two things it fixes on the way through, both learned the hard way:

  * **id prefix vs region.** Every one of the directory's records begins with
    its region's short code, and build.py files records by `region` while
    humans read the prefix — so a `us-` id sitting in data/europe/ is a record
    nobody finds again. Agents get this wrong when they discover, say, a
    Singapore sovereign fund on a US company's cap table. Corrected here rather
    than by asking every prompt to remember.
  * **the backlog is not optional.** `wanted` (what an agent could not source)
    and `rejected` (what it deliberately excluded, and why) are the most
    perishable output of a round and the easiest to lose in a scratch
    directory. They are merged into reports/research-backlog.json so the next
    round does not redo settled work.

Idempotent: re-running overwrites the same destination files. It does NOT run
the build — do that afterwards, in the documented order.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BACKLOG = ROOT / "reports" / "research-backlog.json"

PREFIX = {
    "taiwan": "tw", "united-states": "us", "europe": "eu", "greater-china": "cn",
    "japan": "jp", "south-korea": "kr", "israel": "il", "canada": "ca",
    "india": "in", "southeast-asia": "sea", "australia-nz": "anz",
    "rest-of-world": "row",
}
ALL_PREFIXES = set(PREFIX.values())


def fix_id(rec: dict) -> tuple[str, str] | None:
    """Force the id prefix to agree with the record's region."""
    want = PREFIX.get(rec.get("region", ""))
    if not want:
        return None
    old = rec.get("id", "")
    head = old.split("-")[0]
    if head == want:
        return None
    body = old[len(head) + 1:] if head in ALL_PREFIXES else old
    rec["id"] = f"{want}-{body}"
    return (old, rec["id"])


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, prefix = Path(sys.argv[1]), sys.argv[2]
    files = sorted(src.glob(f"{prefix}-*.json"))
    if not files:
        sys.exit(f"no {prefix}-*.json under {src}")

    fixed: list[tuple[str, str]] = []
    n_co = n_ent = 0

    for f in files:
        try:
            d = json.loads(f.read_text("utf-8"))
        except json.JSONDecodeError as e:
            print(f"  SKIP {f.name}: unparseable ({e})")
            continue
        if not isinstance(d, dict):
            print(f"  SKIP {f.name}: expected an object with companies/entities")
            continue
        slice_name = f.stem

        for rec in (d.get("companies") or []) + (d.get("entities") or []):
            if (m := fix_id(rec)):
                fixed.append(m)

        if (cos := d.get("companies")):
            out = DATA / "companies" / "_raw" / f"{slice_name}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(cos, ensure_ascii=False, indent=2), "utf-8")
            n_co += len(cos)
            print(f"  {len(cos):3d} companies -> {out.relative_to(ROOT)}")

        if (ents := d.get("entities")):
            by_region: dict[str, list[dict]] = defaultdict(list)
            for e in ents:
                by_region[e.get("region", "rest-of-world")].append(e)
            for region, rows in sorted(by_region.items()):
                out = DATA / region / "_raw" / f"{slice_name}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
                n_ent += len(rows)
                print(f"  {len(rows):3d} investors -> {out.relative_to(ROOT)}")

    # --- backlog ---
    backlog = {"_comment": [
        "Named gaps the research rounds could not close, kept in the repo so they",
        "survive the scratchpad. `wanted` is what an agent would have researched",
        "with a working WebSearch; `skipped`/`rejected` record deliberate exclusions",
        "and WHY, so a later round does not redo the same rejected work.",
        "Machine-generated per round by scripts/stage_round.py; edit freely.",
    ], "rounds": {}}
    if BACKLOG.exists():
        try:
            backlog["rounds"] = json.loads(BACKLOG.read_text("utf-8")).get("rounds", {})
        except json.JSONDecodeError:
            pass
    for f in files:
        try:
            d = json.loads(f.read_text("utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        entry = {k: d[k] for k in ("wanted", "skipped", "notes") if d.get(k)}
        if d.get("rejected"):
            # An agent that both rejected and then included a name writes
            # "INCLUDED — see entities[]" as the reason; that is bookkeeping,
            # not a rejection, and carrying it forward would make a later round
            # skip a firm this one actually added.
            keep = [r for r in d["rejected"] if "INCLUDED" not in str(r.get("reason", ""))]
            if keep:
                entry["rejected"] = keep
        if entry:
            backlog["rounds"][f.stem] = entry
    BACKLOG.parent.mkdir(exist_ok=True)
    BACKLOG.write_text(json.dumps(backlog, ensure_ascii=False, indent=2), "utf-8")

    print(f"\nstaged {n_co} companies + {n_ent} investors from {len(files)} slice(s)")
    if fixed:
        print(f"id prefix corrected on {len(fixed)}:")
        for old, new in fixed:
            print(f"    {old}  ->  {new}")
    r = backlog["rounds"]
    print(f"backlog: {len(r)} slices · "
          f"wanted {sum(len(v.get('wanted', [])) for v in r.values())} · "
          f"skipped {sum(len(v.get('skipped', [])) for v in r.values())} · "
          f"rejected {sum(len(v.get('rejected', [])) for v in r.values())}")
    print("\nnow run, in this order:")
    print("  uv run scripts/build.py && uv run scripts/backfill_backing.py && uv run scripts/build.py")
    print("  uv run scripts/build_companies.py && uv run scripts/qa_check.py && uv run scripts/build_site.py")


if __name__ == "__main__":
    main()
