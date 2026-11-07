"""Map actual guide clauses to existing configuration and final-upload measurements."""
from __future__ import annotations

import json
from pathlib import Path

from . import journalcontext as jc
from .guides import normalize
from .packagefreeze import _safe_path, _sha256, expected_files
from .readiness import load, atomic_json

TOPICS = {"article_type", "length", "abstract", "keywords", "references", "figures", "tables",
          "supplements", "statements", "uploads", "layout", "blinding", "cover_letter"}
STATUSES = {"required", "recommended", "allowed", "unspecified", "not_applicable"}
STYLE = {"font_family", "body_font_pt", "title_font_pt", "section_heading_font_pt", "subsection_heading_font_pt",
         "line_spacing", "paragraph_spacing_after_pt", "margins_in", "paper_size", "all_text_black", "external_hyperlinks"}
PROFILE = {"keywords", "main_text_headings", "line_numbers", "blinded_main_manuscript", "submission_layout"}
METHODS = {"style", "profile", "limit", "uploads", "figure", "csl", "template", "manual", "context"}


def rules(project): return load(project,jc.REQUIREMENTS).get("guide_rules",[])


def config_value(project, check):
    kind=check["type"]; field=check.get("field")
    if kind=="style":
        if field not in STYLE: raise ValueError("Unsupported automatic Word style field; use actual manual inspection")
        return load(project,"08_submission/docx_style.json").get(field)
    if kind=="profile":
        if field not in PROFILE: raise ValueError("Unsupported automatic profile field; use manual inspection")
        return load(project,jc.TARGET).get(field)
    if kind=="context": return jc.current(project)["identity"].get(field)
    if kind=="uploads": return load(project,jc.REQUIREMENTS).get("required_upload_roles")
    if kind=="limit":
        req=load(project,jc.REQUIREMENTS)
        if field in {"main", "abstract", "references"}:
            legacy={"main":"limit","abstract":"abstract_limit","references":"reference_limit"}
            return req.get("limits",{}).get(field,{}).get("value",req.get("word_count",{}).get(legacy[field]))
        if field not in {"main_figures","main_tables","main_display_items","supp_figures","supp_tables"}: raise ValueError("Unknown measured limit field")
        return req.get("display_limits",{}).get(field,{}).get("value")
    raise ValueError("No configuration value for this check type")


def validate(project, context):
    failures=[];req=load(project,jc.REQUIREMENTS); rows=req.get("guide_rules",[])
    if req.get("journal_context_id") not in {None,context["context_id"]}: failures.append("Submission requirements belong to another journal attempt")
    if req.get("article_type")!=context["identity"]["article_type"]: failures.append("Requirements article type differs from current target")
    if not isinstance(rows,list) or not rows: return failures+["guide_rules must cover the current official guide topics"]
    seen=set();topics=set();source_texts={}
    for row in rows:
        if not isinstance(row,dict):
            failures.append("guide_rules entries must be objects");continue
        try:
            key=row["id"]
            if not isinstance(key,str) or not key.strip() or key in seen: raise ValueError("unique rule id required")
            seen.add(key);topic=row["topic"];topics.add(topic)
            if topic not in TOPICS or row.get("status") not in STATUSES: raise ValueError("unknown topic/status")
            source=context["sources"][row["source_id"]]
            if row["source_id"] not in source_texts:
                source_texts[row["source_id"]]=normalize(_safe_path(project,source["text"])[1].read_text(encoding="utf-8")).casefold()
            quote=normalize(row.get("quote",""))
            if len(quote)<15 or quote.casefold() not in source_texts[row["source_id"]] or len(str(row.get("locator","")).strip())<3:
                raise ValueError("cite a real passage and section/page in this attempt's captured source")
            if row["status"] in {"unspecified","not_applicable"}:
                if len(str(row.get("reason","")).strip())<30: raise ValueError("explain actual search scope or study-specific inapplicability")
                continue
            check=row["check"];kind=check.get("type")
            if kind not in METHODS: raise ValueError("choose a supported actual-output check or manual inspection")
            if kind in {"style","profile","limit","uploads","context"}:
                if "value" not in check or config_value(project,check)!=check["value"]: raise ValueError("the actual configuration does not implement this guide rule's value")
            if kind=="context" and check.get("field") not in {"journal","issn","article_type","submission_stage"}:
                raise ValueError("Unknown context field")
            if kind=="figure" and (not isinstance(check.get("formats"),list) or not check["formats"] or
                    any(x not in {"png","tif","tiff","jpg","jpeg","pdf","eps","svg"} for x in check["formats"]) or
                    (check.get("min_dpi") is not None and (type(check["min_dpi"]) not in (int,float) or check["min_dpi"]<=0))):
                raise ValueError("Declare actual accepted figure formats and positive raster DPI when required")
            if kind=="limit":
                if type(check["value"]) is not int or check["value"]<0: raise ValueError("Limit must be an explicit nonnegative integer")
                field=check["field"]; settings=req.get("limits",{}) if field in {"main","abstract","references"} else req.get("display_limits",{})
                status=settings.get(field,{}).get("status","required" if config_value(project,check) is not None else "unspecified")
                if row["status"]=="required" and status!="required": raise ValueError("mandatory guide limit cannot be softened in configuration")
            if kind in {"style","profile","figure","csl","template","manual"} and not check.get("roles"):
                raise ValueError("declare actual upload roles to inspect, not a generic PASS")
            if kind in {"csl","template"}:
                path=_safe_path(project,check["path"])[1]
                if not any(a["file"]==check["path"] and a["sha256"]==_sha256(path) for a in context.get("assets",{}).values()):
                    raise ValueError("selected CSL/template must be captured for this context")
        except (OSError,ValueError,KeyError,TypeError) as exc: failures.append(f"{row.get('id','rule')}: {exc}")
    if TOPICS-topics: failures.append("Guide topics unassessed: "+", ".join(sorted(TOPICS-topics)))
    from .submissionlayout import enabled,policy
    if enabled(project):
        try: policy(project)
        except (OSError,ValueError,KeyError,TypeError) as exc: failures.append(str(exc))
    return failures


def _uploads(project, row):
    manifest=load(project,"08_submission/bundle/manifest.json")
    wanted=set(row["check"].get("roles",[]))
    items=[i for i in manifest.get("items",[]) if i.get("upload",True) is not False and i.get("role") in wanted]
    if not items: raise ValueError("no actual uploads have the declared inspection roles")
    actual={i["file"]:_safe_path(project,i["file"])[1] for i in items}
    if any(not p.is_file() for p in actual.values()): raise ValueError("required inspection upload is missing")
    return items,actual


def record_review(project, rule_id, files, render, observation):
    jc.guard(project);context=jc.current(project)
    row=next((r for r in rules(project) if r["id"]==rule_id),None)
    if row is None or row.get("check",{}).get("type")!="manual": raise ValueError("Use an actual manual-inspection rule id")
    _,expected=_uploads(project,row)
    provided={_safe_path(project,x)[0] for x in files}
    if not set(expected)<=provided or not provided<=set(expected_files(project)): raise ValueError("review must cover all uploads in the rule's roles, using actual manifest files")
    if len(observation.strip())<60: raise ValueError("record concrete medical/editorial/layout findings, not a generic PASS")
    rel,path=_safe_path(project,render)
    if path.suffix.lower() not in {".png",".pdf",".svg"} or not path.is_file(): raise ValueError("actual rendered preview/page required")
    from .submissionqc import RECEIPT
    payload=load(project,RECEIPT) if (project/RECEIPT).is_file() else {}
    payload.setdefault("guide_rule_reviews",{})[rule_id]={"context_id":context["context_id"],"rule_hash":jc.digest(row),
        "files":{x:_sha256(_safe_path(project,x)[1]) for x in sorted(provided)},"render":rel,"render_sha256":_sha256(path),
        "observation":observation,"at":jc.now()}
    payload["ok"]=False;payload.pop("input_signature",None);payload.pop("sources",None);payload.pop("engine",None)
    atomic_json(project/RECEIPT,payload)
    return payload["guide_rule_reviews"][rule_id]


def measure(project, reviews):
    jc.guard(project);context=jc.current(project);result=[];cache={}
    from .checks import Ctx, get, load_all
    from .state import State
    from . import registry
    pipe=registry.load();state=State(project).load();load_all()
    def existing(name):
        if name not in cache:
            r=get(name)(Ctx(pipe,state,project,pipe.stage("S23_package"),{"check":name}))
            cache[name]=[] if r.ok else [r.detail]
        return cache[name]
    for row in rules(project):
        defects=[];kind=row.get("check",{}).get("type");status=row["status"]
        try:
            if status in {"unspecified","not_applicable"}: pass
            elif kind=="context":
                if config_value(project,row["check"])!=row["check"]["value"]: defects.append("current context value differs")
            elif kind=="limit":
                field=row["check"]["field"]
                if field in {"main","abstract","references"}: defects+=existing("journal_limits_met")
                else:
                    plan=load(project,"08_submission/integration/artifact_plan.json")
                    counts={k:len(plan.get(k,[])) for k in ("main_figures","main_tables","supp_figures","supp_tables")}
                    counts["main_display_items"]=counts["main_figures"]+counts["main_tables"]
                    if counts[field]>row["check"]["value"]: defects.append(f"actual journal inventory {counts[field]} exceeds {row['check']['value']}")
            elif kind=="uploads":
                defects+=existing("bundle_complete")
            elif kind in {"style","profile"}:
                _,files=_uploads(project,row)
                for rel,path in files.items():
                    if path.suffix.lower()!=".docx": raise ValueError("this automatic check requires actual Word uploads")
                    if kind=="style":
                        if rel not in cache:
                            from manuscript.build_docx import load_style,audit_docx
                            role=next(i["role"] for i in _uploads(project,row)[0] if i["file"]==rel)
                            cache[rel]=audit_docx(path,load_style(project/"08_submission/docx_style.json"),role)
                        defects+=cache[rel]
                    else:
                        from .journalspec import docx_problems
                        role=next(i["role"] for i in _uploads(project,row)[0] if i["file"]==rel)
                        defects+=docx_problems(path,load(project,jc.TARGET),project,role)
                        if row["check"]["field"]=="keywords":
                            from docx import Document
                            if not any(p.text.strip().lower().startswith("keywords:") for p in Document(path).paragraphs): defects.append("actual Keywords paragraph missing")
            elif kind=="figure":
                _,files=_uploads(project,row);check=row["check"]
                for rel,path in files.items():
                    if path.suffix.lower().lstrip(".") not in check["formats"]: defects.append(f"{rel}: wrong actual image format")
                    if check.get("min_dpi") and path.suffix.lower() not in {".pdf",".eps",".svg"}:
                        from PIL import Image
                        with Image.open(path) as im:
                            if min(im.info.get("dpi",(0,0)))<check["min_dpi"]: defects.append(f"{rel}: actual raster DPI missing/too low")
            elif kind in {"csl","template"}:
                from .buildproof import load as builds
                _,files=_uploads(project,row);receipts=builds(project)
                expected=_safe_path(project,row["check"]["path"])[1].resolve()
                for rel,path in files.items():
                    receipt=receipts.get(rel,{})
                    field="csl" if kind=="csl" else "reference_doc"
                    used=Path(receipt.get("parameters",{}).get(field,""))
                    if not used.is_absolute(): used=project/used
                    if used.resolve()!=expected or receipt.get("sources",{}).get(str(expected))!=_sha256(expected) or receipt.get("sha256")!=_sha256(path):
                        defects.append(f"{rel}: build does not prove use of the current selected {kind}")
            elif kind=="manual":
                _,files=_uploads(project,row);review=reviews.get(row["id"],{})
                if len(str(review.get("observation","")).strip())<60: raise ValueError("substantive actual-file inspection missing")
                if review.get("context_id")!=context["context_id"] or review.get("rule_hash")!=jc.digest(row): raise ValueError("current rule has no matching actual-render review")
                if any(review.get("files",{}).get(rel)!=_sha256(path) for rel,path in files.items()): raise ValueError("reviewed upload changed")
                render=_safe_path(project,review["render"])[1]
                if not render.is_file() or _sha256(render)!=review.get("render_sha256"): raise ValueError("reviewed render changed")
            else: raise ValueError("unimplemented rule verification cannot pass")
        except (OSError,ValueError,KeyError,TypeError) as exc: defects.append(str(exc))
        result.append({"rule_id":row["id"],"source_id":row["source_id"],"file":"guide:"+row["id"],
                       "status":"FAIL" if defects and status=="required" else "WARN" if defects else "PASS",
                       "checks":f"current official guide {row['topic']} ({status}); {kind or 'no explicit constraint'}",
                       "defects":defects})
    return result
