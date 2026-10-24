"""Every actionable review observation has one disposition, regardless of priority list."""
import re

def catalogue(text,evidence,headings):
    rows=evidence.get("findings")
    if evidence.get("finding_inventory_complete") is not True or not isinstance(rows,list):
        raise ValueError("Reviewer must inventory all actionable findings, including comprehension/presentation prose, not only mandatory revisions")
    ids=[r.get("id") for r in rows]
    if len(set(ids))!=len(ids) or any(not isinstance(key,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*",key) for key in ids): raise ValueError("Findings need unique stable IDs")
    markers=set(re.findall(r"\[finding:([A-Za-z][A-Za-z0-9_-]*)\]",text))
    if markers!=set(ids): raise ValueError("Every [finding:ID] in review prose must match the complete JSON inventory")
    section_states=evidence.get("section_verdicts",{})
    for heading in headings:
        state=section_states.get(heading)
        selected=[row for row in rows if row.get("section")==heading]
        if state!=("findings_listed" if selected else "no_actionable_findings"): raise ValueError(f"Account for all actionable observations in {heading}")
    for row in rows:
        if (row.get("section") not in headings or len(str(row.get("text","")))<12 or not row.get("locator")
                or row.get("category") not in {"numbers","grouping","conclusion_strength","objective","preference"}
                or type(row.get("affects_science")) is not bool): raise ValueError("Finding needs section, location, actual issue text, category and scientific-impact flag")
    return rows

def close(record,current,changes,kept,resolutions,project=None):
    findings={r["id"]:r for r in record.get("findings",[])}
    resolutions=resolutions or {}; kept_ids={row[0] for row in kept}
    if set(resolutions)&kept_ids or set(resolutions)|kept_ids!=set(findings):
        raise ValueError("Every finding in all review sections must be fixed or explicitly kept; no omitted, duplicated or unknown IDs")
    edited={rel for rel in set(record["before"])|set(current) if record["before"].get(rel)!=current.get(rel)}
    changed={row[0] for row in changes}
    for key,row in resolutions.items():
        verified=edited&changed
        if row.get("revision_round") and project is not None:
            from .readiness import load
            from .determinism import holds
            if not re.fullmatch(r"R\d+",row["revision_round"]): raise ValueError("Invalid scoped correction round ID")
            proof=load(project,f".wf/revisions/{row['revision_round']}.json")
            if proof.get("status")!="complete" or not proof.get("validation",{}).get("ok") or not proof.get("validation",{}).get("results"):
                raise ValueError("Finding correction needs a real completed scoped validation, not a planned edit")
            from datetime import datetime
            try:
                if datetime.fromisoformat(proof["completed_at"]) < datetime.fromisoformat(record["started_at"]):
                    raise ValueError("Scoped correction predates this review; old passing evidence cannot resolve a new finding")
            except (KeyError,TypeError) as exc:
                raise ValueError("Scoped correction needs completion time bound to the current review") from exc
            verified|={receipt["path"] for item in proof.get("items",[]) for receipt in item.get("changed_files",[])
                       if receipt.get("path") and holds(project,receipt)}
        if (row.get("status")!="fixed" or len(str(row.get("reason","")))<20 or not row.get("files")
                or not set(row["files"])<=verified): raise ValueError(f"{key}: fixed needs changed review inputs or actual closed scoped producer correction; no typed PASS")
    return resolutions
