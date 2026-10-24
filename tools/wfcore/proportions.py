"""Validate percentage numerator/denominator and comparison basis from executed facts."""
from decimal import Decimal,InvalidOperation
import re

def validate(claim,catalog,text,required=True):
    from .checks.numbers import _scrub
    scrubbed=re.sub(r"\b(?:90|95|99)%\s*(?:credible|prediction|highest posterior density)\s+(?:intervals?|regions?)\b"," ",_scrub(text),flags=re.I)
    tokens=[token.replace("−","-") for token in re.findall(r"(?<!\w)([+\-−]?\d+(?:\.\d+)?)\s*%",scrubbed)]
    rows=claim.get("proportions",[])
    if not rows and not (required and tokens): return []
    problems=[]; reported=[]; bases=[]
    for row in rows:
        try:
            fact=catalog[row["fact_id"]]
            if row["fact_id"] not in claim.get("fact_ids",[]): raise ValueError("Percentage fact must belong to this exact claim")
            values=fact["values"]; n=Decimal(str(values[row["numerator_key"]])); d=Decimal(str(values[row["denominator_key"]]))
            value=str(row["reported"]).strip().rstrip("%").replace("−","-"); shown=Decimal(value)
            kind=fact["context"].get("percentage_kind","part_whole")
            if kind not in {"part_whole","relative_change","probability"}: raise ValueError("Unknown scientific percentage type")
            if d<=0 or (kind!="relative_change" and not 0<=n<=d): raise ValueError("Invalid percentage denominator/type; don't treat change percentages as patient proportions")
            tolerance=Decimal(1).scaleb(shown.as_tuple().exponent)/2
            if abs(shown-100*n/d)>tolerance: raise ValueError("Percentage does not match its actual numerator/denominator")
            basis=fact["context"].get("percentage_basis")
            if not isinstance(basis,str) or not basis.strip(): raise ValueError("Executed fact context needs percentage_basis (eligibility, available-case rule, unit and time), not a claim-side guess")
            reported.append(value); bases.append(basis)
        except (KeyError,ValueError,TypeError,InvalidOperation) as exc: problems.append(str(exc))
    from collections import Counter
    if required and Counter(tokens)!=Counter(reported): problems.append("Bind each reported percentage to its executed numerator and denominator")
    if len(bases)>1 and len(set(bases))>1:
        explanation=claim.get("different_percentage_bases","")
        if not isinstance(explanation,str) or len(explanation)<20 or explanation not in text:
            problems.append("Compared percentages use different denominator bases; correct them or explicitly explain the actual distinction in the reported clause")
    return problems
