"""Cited prior-study numbers require a real, registered, identity-checked full text."""
import json
import re
from .packagefreeze import _safe_path, _sha256
from .readiness import load


def mask(project, rel, text):
    from .benchmark import text_of
    from .checks.refs import citekeys
    from .checks.numbers import _scrub, NUM_RE
    from .refproof import validate_local_proof
    from pubmed.identity import errors
    folder="08_submission/integration" if rel.startswith("08_submission/") else "07_manuscript"
    file=project/folder/"claim_bindings.json"
    rows=json.loads(file.read_text(encoding="utf-8")).get("source_claims",[]) if file.is_file() else []
    selected=[r for r in rows if r.get("path")==rel]; problems=[]; result=text
    if selected:
        library={r["citekey"]:r for r in load(project,"06_refs/library.json")["entries"]}
        records={r["citekey"]:r for r in load(project,"06_refs/fulltext/retrieval_manifest.json")["retrievals"]}
        ok, defects, _=validate_local_proof(project,required_keys={r.get("citekey") for r in selected})
        if not ok: return text,["Cited numeric source identity: "+"; ".join(defects[:3])]
        for row in selected:
            key=row.get("citekey"); passage=row.get("text",""); excerpt=row.get("excerpt","")
            record=records.get(key,{})
            try:
                fullrel,path=_safe_path(project,row.get("fulltext",""))
                if (not passage or passage not in text or key not in citekeys(passage)
                        or not row.get("locator") or len(str(row.get("support","")))<20
                        or not fullrel.startswith("06_refs/fulltext/") or record.get("fulltext")!=fullrel
                        or record.get("access") not in {"oa","authorized"} or not path.is_file()
                        or _sha256(path).casefold()!=str(row.get("sha256","")).casefold()
                        or _sha256(path).casefold()!=str(record.get("sha256","")).casefold()):
                    raise ValueError("exact cited passage/full-text location/access/hash/support required")
                identity=errors(library[key],path,record)
                if identity: raise ValueError("; ".join(identity))
                norm=lambda s:re.sub(r"\s+"," ",s).strip()
                if len(excerpt)<12 or norm(excerpt) not in norm(text_of(path)): raise ValueError("excerpt absent from actual original source")
                source_numbers={m[1].replace("−","-") for m in NUM_RE.finditer(_scrub(excerpt))}
                claim_numbers={m[1].replace("−","-") for m in NUM_RE.finditer(_scrub(passage))}
                if not claim_numbers or not claim_numbers.issubset(source_numbers): raise ValueError("cited numbers absent from located original excerpt; no free numeric whitelist")
                result=result.replace(passage," ")
            except (OSError,ValueError,KeyError) as exc: problems.append(f"{key}: {exc}")
    # Numeric comparisons attributed to others cannot pass because their numbers happen
    # to occur in our own analysis. Author/year-only prose is not a numeric comparison.
    if rel.endswith(("discussion.md","introduction.md","full_manuscript.md")):
        for paragraph in re.split(r"\n\s*\n",result):
            if citekeys(paragraph) and NUM_RE.search(_scrub(paragraph)):
                problems.append("Numeric cited comparison needs its exact source_claims binding: "+paragraph[:100])
    return result,problems
