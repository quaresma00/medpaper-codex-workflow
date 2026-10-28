"""Reuse genuine author decisions on unchanged OPTIONAL proposals, never waive new errors."""
import json,re
from .packagefreeze import _safe_path,_sha256


def proposal(project,finding):
    if finding.get("optional_method") is not True:
        raise ValueError("Only an explicitly optional methodological recommendation may reuse a prior author decision")
    key=finding.get("proposal_id",""); text=finding.get("proposal_text",""); basis=finding.get("proposal_basis",{})
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*",key) or len(text)<30 or not isinstance(basis,dict) or not basis:
        raise ValueError("Optional proposal needs a stable ID, exact recommendation and real scientific basis hashes")
    for rel,digest in basis.items():
        normalized,file=_safe_path(project,rel)
        science=normalized.startswith(("03_analysis/results/","03_analysis/code/","02_data/adjudication/","02_data/processed/")) or normalized in {"01_protocol/study_facts.json","01_protocol/analysis_contract.json","01_protocol/protocol_final.md","01_protocol/protocol_v1.md"}
        if not science or not file.is_file() or _sha256(file)!=digest:
            raise ValueError("Proposal's scientific basis changed or is not a bound scientific source; obtain actual renewed author adjudication")
    return key,text,basis


def reuse(project,current,finding,request):
    origin=request.get("reuse_from",{})
    scope=origin.get("scope"); rid=origin.get("round",""); fid=origin.get("finding")
    if scope!=current["scope"] or not re.fullmatch(r"[MP]\d+",rid) or rid==current["id"]:
        raise ValueError("Decision reuse must identify an earlier actual round in this scope")
    previous=json.loads((project/".wf/review_rounds"/(rid+".json")).read_text(encoding="utf-8"))
    if not previous.get("closed_at") or not previous.get("report") or previous.get("scope")!=scope:
        raise ValueError("Prior author decision is not from a closed genuine review")
    _,report=_safe_path(project,previous["report"]["path"])
    if _sha256(report)!=previous["report"]["sha256"]: raise ValueError("Original independent report changed")
    older=next((r for r in previous.get("findings",[]) if r.get("id")==fid),None)
    decision=previous.get("author_decisions",{}).get(fid,{})
    if not older or decision.get("reused_from") or not any(k==fid for k,_ in previous.get("kept",[])):
        raise ValueError("Reference the original adjudication, never a circular or chained executor assertion")
    if (decision.get("report_sha256")!=previous["report"]["sha256"] or decision.get("inputs")!=previous.get("after")
            or len(str(decision.get("author_words","")))<8 or len(str(decision.get("rationale","")))<20):
        raise ValueError("Original explicit author adjudication is missing or unbound")
    if proposal(project,older)!=proposal(project,finding): raise ValueError("Different proposal or new scientific evidence cannot inherit an author refusal")
    return {**decision,"reused_from":origin,"report_sha256":current["report"]["sha256"],"inputs":current["after"]}
