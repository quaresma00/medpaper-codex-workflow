"""Publication labels are not measurements. Alias roles are narrowly scoped and sourced."""
import re

LABEL=re.compile(r"\b(?:Online Resource|Supplementary (?:File|Material|Methods)|Appendix|Panel|Figure|Fig\.|Table)\s+[A-Z]?\d+[A-Za-z]?\b",re.I)
ROLES={"supplementary_methods":"Supplementary Methods","supplementary_tables":"Supplementary tables","supplementary_figures":"Supplementary figures"}

def aliases(target):
    rows=target.get("display_reference_aliases",{})
    if not isinstance(rows,dict): raise ValueError("Display reference aliases must map publication labels to explicit supplement roles")
    if rows and not target.get("display_reference_rule_source"): raise ValueError("Display reference aliases need the journal's official source")
    if any(not LABEL.fullmatch(key) or value not in ROLES for key,value in rows.items()): raise ValueError("Only recognized numbered publication labels and supplement roles can be aliased, never a scientific value")
    return rows

def normalize(text,target):
    for key,role in sorted(aliases(target).items(),key=lambda x:-len(x[0])):
        text=re.sub(r"(?<!\w)"+re.escape(key)+r"(?!\w)",ROLES[role],text,flags=re.I)
    return text

def scrub(text): return LABEL.sub(" ",text)
