"""Concrete early contracts and assembly diagnostics, not extra review reports."""
import csv
import json
import re
from . import Ctx,Result,check
from ..readiness import load
from ..packagefreeze import _safe_path,_sha256

@check("research_context_known")
def research_context_known(ctx):
    try:
        idea=load(ctx.project,"01_protocol/idea.json"); sources=idea.get("research_context",{}).get("sources",[])
        if not idea.get("design") or not sources or any(not row.get("name") or not row.get("type") for row in sources):
            raise ValueError("At intake establish the actual design and every data-source type; ask only these missing facts")
    except (OSError,ValueError,TypeError) as exc: return Result(False,"research_context_known",str(exc))
    return Result(True,"research_context_known","Actual study design and source types established at intake")

@check("study_governance")
def study_governance(ctx):
    from ..studypolicy import assess,REPORT
    try:
        actual=assess(ctx.project); saved=load(ctx.project,REPORT)
        problems=actual["unresolved"]+([] if actual==saved else ["Governance assessment stale; run tools/study_policy.py"])
    except (OSError,ValueError,KeyError) as exc: problems=[str(exc)]
    return Result(not problems,"study_governance","; ".join(problems) or "Design/source-specific assessment supported; no invented institutional decisions")

@check("variable_definitions")
def variable_definitions(ctx):
    try:
        plan=load(ctx.project,"01_protocol/analysis_contract.json")
        rows=plan.get("variable_definitions",[]); needed={"role","source_field","definition","unit","coding","time_window","missing_rule","source_locator"}
        if not rows: raise ValueError("Before analysis, record the variable-definition crosswalk in analysis_contract.json")
        if any(any(not str(r.get(k,"")).strip() for k in needed) for r in rows): raise ValueError("Each crosswalk row needs role, field, definition, units, coding, time, missing rule and actual source locator")
        if not {"eligibility","outcome"}.issubset({r["role"] for r in rows}): raise ValueError("Crosswalk must include eligibility and outcome definitions; explicitly address exposure/comparator applicability")
    except (OSError,ValueError,TypeError) as exc: return Result(False,"variable_definitions",str(exc))
    return Result(True,"variable_definitions",f"{len(rows)} explicit variable definitions; executor must compare each against source documentation")

@check("statistical_reporting_plan")
def statistical_reporting_plan(ctx):
    try:
        row=load(ctx.project,"01_protocol/analysis_contract.json").get("statistical_reporting",{})
        if type(row.get("primary_comparisons")) is not int or row["primary_comparisons"]<0: raise ValueError("Specify how many primary comparisons before analysis (zero needs a justified descriptive-only plan)")
        for field in ("multiplicity","effect_measures","intervals","exploratory_labeling"):
            if len(str(row.get(field,"")))<12: raise ValueError(f"Specify {field}, with rationale when adjustment is not appropriate")
        if row["primary_comparisons"]==0 and len(str(row.get("descriptive_only_reason","")))<20: raise ValueError("Explain why the study is descriptive-only without primary comparisons")
    except (OSError,ValueError,TypeError) as exc: return Result(False,"statistical_reporting_plan",str(exc))
    return Result(True,"statistical_reporting_plan","Primary comparison family, multiplicity and effect/interval reporting explicit")

@check("source_record_spotcheck")
def source_record_spotcheck(ctx):
    try:
        rows=load(ctx.project,"03_analysis/results/dataset_summary.json").get("source_record_check",{})
        population=rows.get("eligible_records"); cases=rows.get("cases",[])
        if type(population) is not int or population<1: raise ValueError("Record the eligible source-record count")
        if len(cases)!=min(10,population) or len({r.get("record_locator") for r in cases})!=len(cases): raise ValueError("Trace ten distinct cases (all when fewer) to source; this is QC, never analysis sampling")
        if len(str(rows.get("selection_basis","")))<20: raise ValueError("State reproducible case selection covering outcome/groups and edge cases, not convenient matching records")
        digests={}
        for case in cases:
            for field in ("record_locator","source_file","source_sha256","derived_file","derived_sha256","comparisons"):
                if not case.get(field): raise ValueError(f"Spotcheck needs actual {field}")
            for prefix in ("source","derived"):
                _,path=_safe_path(ctx.project,case[prefix+"_file"])
                if not path.is_file(): raise ValueError("Source/derived record-check file missing")
                if path not in digests: digests[path]=_sha256(path)
                if digests[path].casefold()!=case[prefix+"_sha256"].casefold(): raise ValueError("Source/derived record-check evidence drifted")
            if not isinstance(case["comparisons"],list) or not case["comparisons"]: raise ValueError("Actually compare source fields and derived fields, not an empty checklist")
            if any(not item.get("variable") or "source_value" not in item or "derived_value" not in item for item in case["comparisons"]): raise ValueError("Each comparison needs the actual variable and both observed values, including explicit nulls")
            if any(item.get("source_value")!=item.get("derived_value") and len(str(item.get("resolved_by","")))<20 for item in case["comparisons"]): raise ValueError("Unresolved source/derived discrepancy; correct producer and affected results")
        if not rows.get("reviewer") or not rows.get("checked_at"): raise ValueError("Record who actually checked the source records and when")
    except (OSError,ValueError,KeyError,TypeError) as exc: return Result(False,"source_record_spotcheck",str(exc))
    return Result(True,"source_record_spotcheck","Ten-case/all-small-cohort source trace recorded and bound; not certification of every clinical record")

@check("reference_usage")
def reference_usage(ctx):
    from .refs import citekeys
    try:
        library=load(ctx.project,"06_refs/library.json"); entries={r["citekey"]:r for r in library["entries"]}
        cited=set()
        for name in ("introduction","methods","results","discussion","abstract","supplementary_methods"):
            path=ctx.project/f"07_manuscript/{name}.md"
            if path.is_file(): cited.update(citekeys(path.read_text(encoding="utf-8")))
        usage=ctx.project/"06_refs/usage.json"
        reasons=json.loads(usage.read_text(encoding="utf-8")).get("uncited_reasons",{}) if usage.is_file() else {}
        absent=[key for key in entries.keys()-cited if len(str(reasons.get(key,"")))<20]
        if absent: return Result(False,"reference_usage","Each unused library entry needs a concrete non-use reason: "+", ".join(sorted(absent)))
    except (OSError,ValueError,KeyError) as exc: return Result(False,"reference_usage",str(exc))
    return Result(True,"reference_usage",f"library={len(entries)}, actually cited={len(cited)}, unused explained={len(entries.keys()-cited)}; never pad citations")

@check("manuscript_size_health")
def manuscript_size_health(ctx):
    from .refs import citekeys
    try:
        text=ctx.read("07_manuscript/full_manuscript.md"); count=len(set(citekeys(text)))
        words=len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b",text))
        return Result(45<=count<=60,"manuscript_size_health",f"Advisory assembly health: {count} cited sources (45–60 reference band, not a quota), {words} words incl. all sections. Explain project/benchmark fit; never add irrelevant papers.",severity="warn")
    except OSError as exc: return Result(False,"manuscript_size_health",str(exc))

@check("journal_display_fit")
def journal_display_fit(ctx):
    from ..journalrules import display_limits,compare
    try:
        plan=load(ctx.project,"08_submission/integration/artifact_plan.json")
        counts={k:len(plan.get(k,[])) for k in ("main_figures","main_tables","supp_figures","supp_tables")}
        counts["main_display_items"]=counts["main_figures"]+counts["main_tables"]
        problems=compare(counts,display_limits(ctx.project))
        if len(str(plan.get("journal_adaptation_reason","")))<30: problems.append("At journal choice, justify actual retain/combine/move decisions before adapting text; keep scientific inventory unchanged")
    except (OSError,ValueError,TypeError) as exc: problems=[str(exc)]
    return Result(not problems,"journal_display_fit","; ".join(problems) or "Journal display inventory checked before production")


@check("legend_length_advice")
def legend_length_advice(ctx):
    from ..qualitylimits import check_limit
    from .artifacts import _split_blocks
    rel=ctx.spec.get("path","05_figures/legends.md")
    if not ctx.p(rel).is_file(): return Result(False,"legend_length_advice",f"missing {rel}")
    cap=check_limit(ctx)
    advisory=int(ctx.target("figure_legend_words_max",180)); long=[]
    for key,value in _split_blocks(ctx.read(rel)).items():
        count=len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b",value))
        if count>(cap or advisory): long.append(f"{key}: {count} words")
    return Result(not long,"legend_length_advice","; ".join(long) or "Legend length checked without discarding necessary decoding",
                  severity="fail" if cap is not None else "warn")
