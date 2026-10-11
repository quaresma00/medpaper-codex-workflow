"""Explicit, source-bound presentation migrations; never a whitelist of arbitrary new facts."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re

from .packagefreeze import _safe_path, _sha256

MAP = "08_submission/integration/presentation_map.json"


def check(project, snapshot, index, fact_reader):
    mapping=json.loads((project/MAP).read_text(encoding="utf-8"))
    if not index.get("snapshot_id") or mapping.get("snapshot_id") != index["snapshot_id"]:
        raise ValueError("Presentation map must identify this exact pre-edit snapshot")
    before={rel:(snapshot/Path(rel).name).read_text(encoding="utf-8") for rel in index["files"]}
    after={rel:_safe_path(project,rel)[1].read_text(encoding="utf-8") for rel in index["files"]}
    renumber=mapping.get("renumbering",{})
    canonical=lambda s: re.sub(r"\s+"," ",s).strip().casefold()
    for source,dest in renumber.items():
        if not re.fullmatch(r"(Figure|Table)\s+S?\d+",source,re.I) or not re.fullmatch(r"(Figure|Table)\s+S?\d+",dest,re.I) or source.split()[0].casefold()!=dest.split()[0].casefold():
            raise ValueError("Renumbering must retain the display family and use explicit ids")
    if len(set(map(canonical,renumber.values())))!=len(renumber):
        raise ValueError("Ambiguous many-to-one display renumbering")
    def rewrite(text):
        # One pass prevents chained renumbering from transforming an already mapped id again.
        if not renumber:return text
        pattern=re.compile(r"\b(?:"+"|".join(map(re.escape,sorted(renumber,key=len,reverse=True)))+r")\b",re.I)
        lookup={canonical(k):v for k,v in renumber.items()}
        return pattern.sub(lambda m:lookup[canonical(m[0])],text)
    for move in mapping.get("moves",[]):
        source,dest=move["from"],move["to"]
        original,updated=move["text"],move.get("after",rewrite(move["text"]))
        if source not in before or dest not in after or original not in before[source] or updated not in after[dest]:
            raise ValueError("Movement does not match an actual pre-edit source and current destination")
        if fact_reader(rewrite(original))!=fact_reader(updated):
            raise ValueError("Moved passage changed its facts/citations; this is not presentation-only")
    extras=[]
    for row in mapping.get("additions",[]):
        source,path=_safe_path(project,row["source"])
        approved={}
        freeze=project/"07_manuscript/scientific_master_freeze.json"
        if freeze.is_file():
            approved={item["path"]:item["sha256"] for item in json.loads(freeze.read_text(encoding="utf-8")).get("files",[])}
        if source not in approved or _sha256(path).casefold()!=approved[source].casefold():
            raise ValueError("Additional detail must come from a currently hash-bound approved scientific source")
        quote=row["text"];dest=row["to"]
        if quote not in path.read_text(encoding="utf-8") or dest not in after or rewrite(quote) not in after[dest]:
            raise ValueError("Additional detail lacks its actual approved source/destination passage")
        extras.append(quote)
    problems=[]
    old=[fact_reader(rewrite(t)) for t in [*before.values(),*extras]];new=[fact_reader(t) for t in after.values()]
    for field in ("numbers","citekeys","artifacts","pvalues"):
        # Citekeys/ids are identities across files; numerical occurrences remain exact.
        left=Counter(x for row in old for x in row[field]);right=Counter(x for row in new for x in row[field])
        if field in {"citekeys","artifacts"}:left=Counter(set(left));right=Counter(set(right))
        if left!=right:problems.append(f"Package-level {field} changed outside the declared presentation migration")
    return problems
