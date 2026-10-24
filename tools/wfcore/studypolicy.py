"""Evidence-first declarations: infer applicability, never an institutional decision."""
from pathlib import Path
from .readiness import load, atomic_json
from .packagefreeze import _safe_path, _sha256

CONTEXT = "01_protocol/idea.json"
REPORT = "01_protocol/governance.json"


def assess(project: Path) -> dict:
    idea = load(project, CONTEXT); context = idea.get("research_context", {})
    questions, sources, availability = [], [], []
    if not idea.get("design"): questions.append("design: state the actual study design")
    if not context.get("jurisdiction"): questions.append("jurisdiction: identify the applicable location/institution policy, not a default US rule")
    if type(context.get("vulnerable_groups")) is not bool: questions.append("vulnerable_groups: establish whether vulnerable participants are involved")
    if not context.get("sources"): questions.append("sources: identify every source, including any local clinical validation cohort")
    for row in context.get("sources", []):
        name = row.get("name", "unnamed source"); problems = []
        for field in ("type", "identifiability", "access", "redistribution"):
            if not row.get(field): problems.append(f"{name}.{field}: establish from the actual source")
        if type(row.get("third_party")) is not bool: problems.append(f"{name}.third_party: establish source ownership")
        evidence = row.get("policy_evidence", [])
        valid = []
        for record in evidence:
            try:
                rel, file = _safe_path(project, record.get("file", ""))
                quote = str(record.get("excerpt", ""))
                if (not record.get("source") or not record.get("retrieved_at") or not file.is_file()
                        or _sha256(file).casefold() != str(record.get("sha256", "")).casefold()
                        or len(quote) < 12 or quote not in file.read_text(encoding="utf-8")):
                    raise ValueError("source/excerpt/hash/date missing or changed")
                valid.append(record)
            except (OSError, ValueError) as exc: problems.append(f"{name}: policy evidence {exc}")
        # Public/deidentified is NOT, by itself, evidence of exemption or a consent waiver.
        ethics = row.get("ethics_applicability")
        consent = row.get("consent_applicability")
        public_secondary = (row.get("type") == "public_database" and row.get("identifiability") == "anonymous"
                            and not context.get("vulnerable_groups")
                            and not any(word in str(idea.get("design","")).casefold() for word in ("prospective","intervention","前瞻","干预")))
        if not valid: problems.append(f"{name}: retrieve applicable official access/ethics/consent policy")
        if ethics not in {"institutional_review", "not_required_by_applicable_policy"}: problems.append(f"{name}.ethics_applicability: resolve from applicable policy")
        if consent not in {"required", "not_required_by_applicable_policy", "documented_waiver"}: problems.append(f"{name}.consent_applicability: resolve from applicable policy")
        if ethics == "not_required_by_applicable_policy" and (not row.get("applicability_reason") or
                (not public_secondary and not any(r.get("kind")=="institutional" for r in valid))):
            problems.append(f"{name}: nonpublic/identifiable/vulnerable/biospecimen research needs documented institutional determination, not AI exemption")
        institutional = row.get("institutional_evidence")
        if ethics == "institutional_review" or consent in {"required", "documented_waiver"}:
            if not institutional or not any(r.get("kind") == "institutional" for r in valid):
                problems.append(f"{name}: only missing actual approval/consent/waiver documentation needs author confirmation")
            elif str(institutional) not in "\n".join(r["excerpt"] for r in valid if r.get("kind")=="institutional"):
                problems.append(f"{name}: institutional statement must be present in the documented institutional evidence")
        redistribution = row.get("redistribution")
        if redistribution == "permitted" and row.get("identifiability") == "anonymous" and valid:
            statement = f"{name}: available from {row.get('access')}; redistribution only within the documented licence."
        elif redistribution in {"prohibited", "restricted"}:
            statement = f"{name}: obtained via {row.get('access')}; underlying records cannot be redistributed by the authors."
        else: statement = f"{name}: availability terms remain unresolved; no promise of sharing or reasonable-request access is made."
        availability.append(statement); questions.extend(problems)
        sources.append({"name":name,"ethics":ethics,"consent":consent,"basis":valid,
                        "institutional_evidence":institutional,"rationale":row.get("applicability_reason")})
    return {"context_sha256":_sha256(project/CONTEXT),"sources":sources,
            "data_availability":" ".join(availability),"unresolved":questions,
            "meaning":"Applicability assessment; not an IRB decision, approval, exemption or consent waiver"}


def save(project: Path):
    result = assess(project); atomic_json(project/REPORT,result); return result


def declarations(project: Path) -> dict:
    result=assess(project)
    if result["unresolved"]: raise ValueError("; ".join(result["unresolved"]))
    ethics=[]; consent=[]
    for row in result["sources"]:
        name=row["name"]
        if row["ethics"]=="not_required_by_applicable_policy":
            ethics.append(f"For {name}, additional review was not required under the applicable documented policy. {row['rationale']}")
        else: ethics.append(f"{name}: {row['institutional_evidence']}")
        if row["consent"]=="not_required_by_applicable_policy":
            consent.append(f"For {name}, consent for this use was not required under the applicable documented policy. {row['rationale']}")
        else: consent.append(f"{name}: {row['institutional_evidence']}")
    return {"ethics_approval":" ".join(ethics),"informed_consent":" ".join(consent),"data_availability":result["data_availability"]}
