"""Section-local medical editing, bound to actual prose and its read-back sources.

This records an executor's reading, not an AI detector or a semantic proof. It reuses
the existing build receipts and never stores a duplicate draft or a report per section.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import buildproof
from .packagefreeze import _safe_path, _sha256
from .readiness import atomic_json
from .state import State, version_tuple

TOOL = "section_medical_polish"
SECTIONS = {"methods": "S08_methods", "supplementary_methods": "S08_methods",
            "results": "S09_results", "introduction": "S14_introduction",
            "discussion": "S16_discussion", "abstract": "S17_assemble"}


def section_path(value):
    rel = f"07_manuscript/{value}.md" if value in SECTIONS else str(value).replace("\\", "/")
    if rel not in {f"07_manuscript/{name}.md" for name in SECTIONS}:
        raise ValueError("Use one scientific section, not full_manuscript.md or an upload")
    return rel


def _modern(project):
    state = State(project)
    return state.exists() and version_tuple(str(state.load().data.get("engine_pin", "0"))) >= (1, 28, 0)


def enabled(project):
    return _modern(project) or any(row.get("tool") == TOOL for row in buildproof.load(project).values())


def facts(text):
    # Keep values/operators, negation and core design signals. This is deliberately
    # stricter than publication-house-style normalization: section editing is wording.
    from text.polish import CITE_RE, KEY_RE, ART_RE, _normalize_for_facts
    citations = sorted({k for group in CITE_RE.findall(text) for k in KEY_RE.findall(group)})
    artifacts = sorted({re.sub(r"\s+", " ", a).casefold().replace("fig.", "figure").replace("fig ", "figure ")
                        for a in ART_RE.findall(text)})
    body = CITE_RE.sub(" ", ART_RE.sub(" ", text))
    body = re.sub(r"^\s{0,3}#{1,6}\s+.*$", " ", body, flags=re.M)
    number_text = _normalize_for_facts(body)
    numbers = sorted(re.findall(r"(?<![\w.])[-+−]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?", number_text))
    pvalues = sorted(re.sub(r"\s+", "", p).casefold().replace("≤", "<=").replace("≥", ">=")
                     for p in re.findall(r"\b[Pp]\s*[<>=≤≥]\s*(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?", body))
    negative = re.findall(r"\b(?:not|no|never|neither|without|cannot|unable)\b", body.casefold().replace("can't", "cannot"))
    negation = {"markers":len(negative)}
    design = sorted({token.replace("randomised","randomized") for token in re.findall(
        r"\b(?:retrospective|prospective|observational|non-randomi[sz]ed|randomi[sz]ed|cross-sectional|case-control|post-hoc|exploratory|prespecified)\b", body.casefold())})
    return {"numbers": numbers, "pvalues": pvalues, "citekeys": citations, "artifacts": artifacts,
            "negation": negation, "design": design}


def _source_paths(project, sources):
    paths=[]
    for source in sources:
        rel,path=_safe_path(project,str(source).replace("\\", "/"))
        if not path.is_file(): raise ValueError(f"Actual reading source missing: {rel}")
        if rel.startswith((".wf/", "08_submission/")):
            raise ValueError("Use scientific facts/literature as reading sources, not workflow receipts or journal uploads")
        paths.append(path)
    if not paths: raise ValueError("Declare at least one actual source used to read back this section (--source)")
    return paths


def begin(project, section, sources, *, scientific_reset=False):
    project=Path(project).resolve();rel=section_path(section);path=_safe_path(project,rel)[1]
    if Path(rel).stem=="abstract" and State(project).exists():
        from . import earlyreview
        errors=earlyreview.verify(project)
        if errors: raise ValueError("; ".join(errors))
    text=path.read_text(encoding="utf-8");rows=buildproof.load(project);old=rows.get(rel,{})
    if old.get("tool")==TOOL and old.get("parameters",{}).get("status")=="editing":
        if not scientific_reset:
            return {"section":rel,"status":"editing","preserved_baseline":True}
        from .revision import active
        revision=active(project)
        items=(revision or {}).get("items",[])
        if not any(item.get("change_type")=="scientific" and
                   (rel in item.get("affected_sources",[]) or rel in (revision or {}).get("rebuild_files",[])) for item in items):
            raise ValueError("Reset an unfinished baseline only inside the section's actual scientific revision")
    source_paths=_source_paths(project,sources)
    if path in source_paths: raise ValueError("The section is the output; declare its actual factual reading sources")
    parameters={"schema":1,"status":"editing","original_sha256":_sha256(path),"facts_before":facts(text)}
    buildproof.record(project,path,[*source_paths,Path(__file__)],entrypoints=source_paths,tool=TOOL,parameters=parameters)
    return {"section":rel,"status":"editing"}


def _specific(value):
    value=str(value or "").strip()
    return len(value)>=40 and bool(re.search(r"[A-Za-z\u4e00-\u9fff]",value)) and not re.fullmatch(r"(?:checked|reviewed|passed|no changes|all correct)[.! ]*",value,re.I)


def accept(project,section,review):
    project=Path(project).resolve();rel=section_path(section);path=_safe_path(project,rel)[1]
    rows=buildproof.load(project);row=rows.get(rel,{})
    params=row.get("parameters",{})
    if row.get("tool")!=TOOL or params.get("status")!="editing":
        raise ValueError("Begin this section's medical reading before editing it")
    if not buildproof.inputs_current(row): raise ValueError("A factual reading source changed; resolve its scientific revision before accepting wording")
    text=path.read_text(encoding="utf-8")
    changes=[name for name,value in facts(text).items() if value!=params.get("facts_before",{}).get(name)]
    if changes:
        raise ValueError("Medical wording changed protected content: "+", ".join(changes)+
                         ". Restore meaning or route a real scientific correction; do not reset to make the gate green.")
    if not isinstance(review,dict): raise ValueError("Use the executor's actual medical reading, not a boolean pass")
    quote=str(review.get("quote","")).strip()
    normal=lambda s: re.sub(r"\s+"," ",s).strip()
    if len(quote)<20 or normal(quote) not in normal(text): raise ValueError("Quote a real current section passage being medically interpreted")
    if not _specific(review.get("clinical_reading")) or not _specific(review.get("fact_readback")):
        raise ValueError("Explain the actual medical meaning and scientific read-back, including applicable design, uncertainty and limitations")
    from .medicalstyle import diagnose
    findings=diagnose(text,rel);resolutions=review.get("resolutions",{})
    if not isinstance(resolutions,dict): raise ValueError("Retained wording needs source-specific reasons")
    unresolved=[f for f in findings if not _specific(resolutions.get(f["id"]))]
    if unresolved:
        raise ValueError("Read/fix actual medical-language findings or explain legitimate retained use: "+
                         "; ".join(f["kind"]+" at "+f["locator"] for f in unresolved[:5]))
    row.update(sha256=_sha256(path),content_sha256=buildproof.content_digest(path))
    row["parameters"]={**params,"status":"accepted","review":{key:review[key] for key in ("quote","clinical_reading","fact_readback")},
                       "retained_wording":{f["id"]:resolutions[f["id"]] for f in findings}}
    rows[rel]=row;atomic_json(project/buildproof.RECEIPTS,rows)
    return {"section":rel,"status":"accepted","actual_source_files":len(buildproof.project_inputs(project,row))}


def problems(project,sections,optional=()):
    if not enabled(project): return []
    rows=buildproof.load(project);out=[]
    optional={section_path(x) for x in optional}
    for section in sections:
        rel=section_path(section);path=_safe_path(project,rel)[1];row=rows.get(rel,{})
        if not _modern(project) and row.get("tool")!=TOOL:
            continue  # One scoped edit in an old project never backfills all old sections.
        if not path.is_file() and rel in optional: continue
        if (not path.is_file() or row.get("tool")!=TOOL or row.get("parameters",{}).get("status")!="accepted"
                or row.get("sha256")!=_sha256(path) or not buildproof.inputs_current(row)):
            out.append(f"{rel}: current section-level medical edit/read-back is missing, changed or stale")
    return out
