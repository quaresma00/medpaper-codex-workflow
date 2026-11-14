"""One source-bound scientific review before Abstract; no extra workflow stage.

Identity fields record actual delegation; they cannot manufacture or prove a host tool call.
The executor must really use a separate read-only agent and preserve its complete report.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .packagefreeze import _safe_path, _sha256
from .readiness import atomic_json, load

RECORD=".wf/early_review.json"
OWNER="S12_reconcile"
HEADINGS=("Methods and validity", "Results and uncertainty", "Figures and tables",
          "Original article suitability", "Further analysis value", "Required revisions")


def enabled(project):
    from .state import State,version_tuple
    if (project/RECORD).is_file(): return True
    return version_tuple(str(State(project).load().data.get("engine_pin","0"))) >= (1,28,0)


def inputs(project):
    """Actual scientific artifacts only; neither Abstract nor full manuscript is needed."""
    files={"01_protocol/protocol_final.md","01_protocol/analysis_contract.json",
           "01_protocol/study_facts.json","01_protocol/artifact_plan.json",
           "01_protocol/artifact_benchmark.md","07_manuscript/methods.md",
           "07_manuscript/results.md","05_figures/legends.md","04_tables/table_captions.md"}
    # Discussion notes and the aggregate claim-binding file gain writing-only
    # material later; they are not scientific dependencies of this early review.
    for rel in ("01_protocol/protocol_v1.md","01_protocol/protocol_diff.md",
                "07_manuscript/supplementary_methods.md","02_data/acquisition_manifest.json"):
        if (project/rel).is_file(): files.add(rel)
    for pattern in ("03_analysis/code/**/*","03_analysis/results/*.json"):
        files.update(p.relative_to(project).as_posix() for p in project.glob(pattern)
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc",".log",".tmp"})
    if not any(p.startswith("03_analysis/code/") for p in files) or not any(p.startswith("03_analysis/results/") for p in files):
        raise ValueError("Early scientific review needs the executed analysis code and actual result JSONs")
    plan=load(project,"01_protocol/artifact_plan.json")
    review_path=project/"01_protocol/display_review.json"
    rendered=load(project,"01_protocol/display_review.json").get("final_reviews",{}) if review_path.is_file() else {}
    for group in ("main_figures","main_tables","supp_figures","supp_tables"):
        for row in plan.get(group,[]):
            rel=row.get("file","")
            if not rel: raise ValueError("Every planned display needs an actual rendered file for independent reading")
            files.add(rel)
            for field in ("script","pdf","preview"):
                if row.get(field) and _safe_path(project,row[field])[1].is_file(): files.add(row[field])
            observed=rendered.get(row.get("id"),{})
            preview=observed.get("rendered_preview")
            if preview:
                preview_rel,path=_safe_path(project,preview)
                if (observed.get("reviewed_file")!=rel or not path.is_file()
                        or observed.get("rendered_sha256")!=_sha256(path)):
                    raise ValueError("Production reading preview is missing/stale for "+str(row.get("id")))
                files.add(preview_rel)
    from .benchmark import dossier
    files.update(row["fulltext"] for row in dossier(project)["comparators"])
    result={}
    for rel in sorted(files):
        rel,path=_safe_path(project,rel)
        if not path.is_file(): raise ValueError("Early-review source missing: "+rel)
        result[rel]=_sha256(path)
    return result


def _owner(project):
    from .state import State
    from .revision import permits
    state=State(project).load()
    if state.current!=OWNER and not permits(project,OWNER):
        raise ValueError("Prepare/attach early scientific review at S12 or its scoped owner correction; do not rewind stages")


def start(project,executor_id, *, reconsider=False, why=None):
    _owner(project)
    if not isinstance(executor_id,str) or not executor_id.strip(): raise ValueError("Record the actual executor identity before delegating")
    if type(reconsider) is not bool: raise ValueError("Reconsideration must be an explicit boolean request")
    if why and not reconsider: raise ValueError("Use --reconsider with --why only for an explicit independent opinion reconsideration")
    current=inputs(project)
    previous=load(project,RECORD) if (project/RECORD).is_file() else None
    reconsideration=None
    if reconsider:
        if not isinstance(why,str) or len(why.strip())<40 or not re.search(r"[A-Za-z\u4e00-\u9fff]",why):
            raise ValueError("Explicit reconsideration needs a concrete --why (>=40 characters): identify the disputed reading or author/source clarification")
        if not previous or not previous.get("report"):
            raise ValueError("Reconsider an attached independent opinion only; resume the pending/first actual review normally")
        if _drift(project,previous,current):
            raise ValueError("Scientific inputs changed; use ordinary start for focused scientific revalidation, not same-input reconsideration")
        old_path=_safe_path(project,previous["report"]["path"])[1]
        if not old_path.is_file() or _sha256(old_path)!=previous["report"]["sha256"]:
            raise ValueError("Prior independent report is missing/changed; preserve its actual identity before reconsidering")
        report_evidence(old_path.read_text(encoding="utf-8"),previous)
        reconsideration={"reason":why.strip(),"previous_review":previous["id"],"previous_report":dict(previous["report"]),
                         "basis":"Same scientific inputs; a new actual independent opinion is required, not an executor override"}
    if not reconsider and previous and (previous.get("reviewed_artifacts")==current or (previous.get("report") and not _drift(project,previous,current))):
        # Both pending handoffs and completed unchanged reviews are resumed, not reissued.
        return previous
    from .reviewguard import snapshot
    from .determinism import content_sha256
    number=int(previous.get("sequence",0))+1 if previous else 1
    record={"early_review_version":1,"sequence":number,"id":f"E{number:03d}",
            "executor_id":executor_id,"prepared_at":datetime.now(timezone.utc).isoformat(),
            "reviewed_artifacts":current,"reading_guard":snapshot(project),
            "container_content":{rel:content_sha256(project/rel) for rel in current if Path(rel).suffix.lower() in {".xlsx",".docx"}},
            "report_destination":f".wf/review_inbox/E{number:03d}.md","report":None,
            "changed_since_previous":[rel for rel in set(current)|set(previous.get("reviewed_artifacts",{}))
                                      if current.get(rel)!=previous["reviewed_artifacts"].get(rel)] if previous else list(current),
            "previous_review":previous.get("id") if previous else None}
    if reconsideration:
        if (project/record["report_destination"]).exists():
            raise ValueError("The next independent report path already exists; preserve/reconcile it rather than overwrite review history")
        record["reconsideration"]=reconsideration
    from .benchmark import plan_hash,dossier
    record["benchmark_plan_hash"]=plan_hash(dossier(project))
    from .revision import guard_outputs
    guard_outputs(project,[project/RECORD])
    atomic_json(project/RECORD,record)
    return record


def report_evidence(text,record):
    from .reviewfindings import sections,catalogue
    blocks=[json.loads(block) for block in re.findall(r"```json\s*\n(.*?)\n```",text,re.S)]
    selected=[r for r in blocks if isinstance(r,dict) and r.get("early_review_version")==1]
    if len(selected)!=1: raise ValueError("The actual early-review report needs one early_review_version=1 evidence block")
    evidence=selected[0]
    if evidence.get("review_id")!=record["id"] or evidence.get("reviewed_artifacts")!=record["reviewed_artifacts"]:
        raise ValueError("Independent early report must identify the exact current scientific input version")
    reviewer=evidence.get("reviewer",{})
    if (not isinstance(reviewer,dict) or reviewer.get("role")!="independent_subagent"
            or not isinstance(reviewer.get("agent_id"),str) or not reviewer["agent_id"].strip()
            or reviewer["agent_id"]==record["executor_id"]
            or reviewer["agent_id"].casefold() in {"main","executor","primary","self","simulation"}):
        raise ValueError("Use an actual independent subagent, never executor self-review or a typed simulation")
    if evidence.get("verdict") not in {"GO","REVISE","NO_GO"} or evidence.get("article_type")!="original_article":
        raise ValueError("Judge SCIE Original article suitability explicitly with GO, REVISE or NO_GO")
    if evidence.get("marginal_analysis_value") not in {"material","low","none"}:
        raise ValueError("Independently assess whether further analysis can materially change publication prospects")
    bodies=sections(text)
    if any(len(bodies.get(title,"").strip())<40 for title in HEADINGS):
        raise ValueError("Review actual methods, results, figures/tables, Original article suitability, further-analysis value and required corrections in prose")
    findings=catalogue(text,evidence,HEADINGS)
    if evidence["verdict"]=="GO" and any(r.get("category")!="preference" or r.get("affects_science") for r in findings):
        raise ValueError("GO cannot conceal unresolved scientific/objective defects; revise their actual sources first")
    if evidence["verdict"]=="REVISE" and not findings:
        raise ValueError("REVISE needs concrete located findings, not an unspecified request for more analysis")
    return evidence


def attach(project,report):
    _owner(project);record=load(project,RECORD)
    if record.get("report"): raise ValueError("An attached independent report is immutable; reuse it or prepare the changed scientific inputs")
    if inputs(project)!=record["reviewed_artifacts"]:
        raise ValueError("Scientific inputs changed during reading; prepare the current version before another actual review")
    from .reviewguard import verify,extract
    verify(project,record["reading_guard"])
    text=extract(Path(report).read_text(encoding="utf-8"))
    evidence=report_evidence(text,record)
    _,destination=_safe_path(project,record["report_destination"])
    from .revision import guard_outputs
    guard_outputs(project,[destination,project/RECORD])
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(text,encoding="utf-8")
    record.update(verdict=evidence["verdict"],marginal_analysis_value=evidence["marginal_analysis_value"],
                  reviewer=evidence["reviewer"],findings=evidence["findings"],
                  report={"path":record["report_destination"],"sha256":_sha256(destination)})
    atomic_json(project/RECORD,record)
    return record


def verify(project):
    if not enabled(project): return []
    try:
        record=load(project,RECORD)
        if not record.get("report"): return ["Independent scientific review is required before Abstract/assembly; run early_review.py start and actually delegate"]
        drift=_drift(project,record,inputs(project))
        if drift: return ["Early scientific review is stale only for changed inputs: "+", ".join(drift[:8])+"; use scoped owner fixes and actual independent delta reading, not a full stage replay"]
        path=_safe_path(project,record["report"]["path"])[1]
        if _sha256(path)!=record["report"]["sha256"]: return ["The independent early-review report changed after attachment"]
        prior=record.get("reconsideration",{}).get("previous_report")
        if prior and _sha256(_safe_path(project,prior["path"])[1])!=prior["sha256"]:
            return ["The preserved prior independent report changed; reconsideration cannot rewrite review history"]
        evidence=report_evidence(path.read_text(encoding="utf-8"),record)
        if evidence["verdict"]!="GO":
            return [f"Early independent verdict {evidence['verdict']}; notify the author now with report and exact barriers. Do not draft Abstract or spend on low-yield extra analyses. Correct true sources in scope, or obtain the author's pivot/stop decision"]
        return []
    except (OSError,ValueError,KeyError,TypeError) as exc: return [str(exc)]


def _drift(project,record,current):
    from .reviewrounds import input_drift
    from .benchmark import plan_hash,dossier,SCIENCE
    drift=input_drift(project,record["reviewed_artifacts"],current,record.get("container_content"))
    # S13–S16 legitimately complete supporting citekeys/passages in the same document.
    # Retain its actual originally read bytes; use the already-existing protected
    # benchmark plan to distinguish those mappings from changed science/display choices.
    if SCIENCE in drift and record.get("benchmark_plan_hash")==plan_hash(dossier(project)):
        drift.remove(SCIENCE)
    return drift
