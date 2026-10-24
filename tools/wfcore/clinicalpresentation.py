"""A shared clinical display vocabulary and reversible production defaults, not new science."""
import json
from .readiness import load

def plan(project,journal=False):
    rel="08_submission/integration/artifact_plan.json" if journal else "01_protocol/artifact_plan.json"
    return load(project,rel)

def vocabulary(project,journal=False):
    path=project/("08_submission/integration/artifact_plan.json" if journal else "01_protocol/artifact_plan.json")
    rows=plan(project,journal).get("display_dictionary",[]) if path.is_file() else []
    seen=set()
    for row in rows:
        if (not isinstance(row,dict) or any(not isinstance(row.get(k),str) or not row[k].strip() for k in ("key","internal","label","definition","scope"))
                or row["key"] in seen): raise ValueError("Display dictionary needs unique key, internal name, clinical label, definition and source scope")
        seen.add(row["key"])
    return rows

def label(value,project,scope=None,journal=False):
    if not isinstance(value,str): return value
    rows=[r for r in vocabulary(project,journal) if value in {r["key"],r["internal"]} and (scope is None or r["scope"] in {scope,"all"})]
    labels={r["label"] for r in rows}
    if len(labels)>1: raise ValueError("Ambiguous source-specific clinical label; pass its unique key/scope")
    return next(iter(labels)) if labels else value

def profile(project,journal=False):
    path=project/("08_submission/integration/artifact_plan.json" if journal else "01_protocol/artifact_plan.json")
    value=plan(project,journal).get("presentation_profile",{}) if path.is_file() else {}
    allowed={"figure_font_pt_min","figure_font_pt_max","figure_dpi_min","column_width_mm_single","column_width_mm_double","number_format","basis"}
    if set(value)-allowed: raise ValueError("Unknown project presentation-profile field; this is not a journal decision")
    for key in allowed-{"number_format","basis"}:
        if key in value and (isinstance(value[key],bool) or not isinstance(value[key],(int,float)) or value[key]<=0): raise ValueError("Presentation dimensions/fonts/resolution must be positive")
    if value and not str(value.get("basis","")).strip(): raise ValueError("Explain production assumptions; do not claim an unselected journal's requirements")
    if journal:
        target=project/"08_submission/target_journal.json"
        if target.is_file():
            data=json.loads(target.read_text(encoding="utf-8")); overrides=data.get("figure_requirements",{})
            if overrides and not data.get("figure_rule_source"): raise ValueError("Actual journal figure overrides need an official source")
            if set(overrides)-{k for k in allowed if k not in {"basis","number_format"}}: raise ValueError("Unknown journal figure requirement")
            value={**value,**overrides}
    for key in allowed-{"number_format","basis"}:
        if key in value and (isinstance(value[key],bool) or not isinstance(value[key],(int,float)) or value[key]<=0): raise ValueError("Invalid merged journal production requirement")
    if value.get("figure_font_pt_max",float("inf"))<value.get("figure_font_pt_min",0): raise ValueError("Maximum figure font is below minimum")
    return value

def verify_plan(project,journal=False):
    from .state import State,version_tuple
    vocabulary(project,journal); value=profile(project,journal)
    if version_tuple(str(State(project).load().data.get("pipeline_version","0")))>=(1,16,0):
        if not value or (value.get("figure_font_pt_min",0)<8 and not journal):
            return ["Set reversible S07 presentation_profile with at least 8 pt at final size and its basis; use sourced journal overrides only in integration"]
    return []
