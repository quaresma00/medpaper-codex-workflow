"""Source-bound project benchmarks and executor acceptance, not universal quotas."""
from __future__ import annotations

from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .packagefreeze import _safe_path, _sha256
from .readiness import atomic_json, load

SCIENCE = "01_protocol/artifact_benchmark.md"
JOURNAL = "08_submission/integration/journal_benchmark.md"
SECTIONS = ("introduction", "methods", "discussion", "supplementary")
DIMENSIONS = ("methods_logic", "literature_coverage", "display_completeness", "discussion_flow",
              "declarations", "legends_and_crossrefs", "reader_comprehension")
RETIRED_TARGETS = {"reflib_min", "reflib_max", "deepread_count", "intro_words_min", "intro_words_max",
                   "intro_refs_min", "intro_refs_max", "discussion_words_min", "discussion_words_max",
                   "discussion_refs_min", "discussion_refs_max", "main_figures_max", "main_tables_max"}


def substantive(value):
    return isinstance(value, str) and len(value.strip()) >= 20 and value.strip().casefold() not in {"todo", "pending"}


def dossier(project: Path, layer="science") -> dict:
    path = project / (SCIENCE if layer == "science" else JOURNAL)
    blocks = [json.loads(text) for text in re.findall(r"```json\s*\n(.*?)\n```", path.read_text(encoding="utf-8"), re.S)]
    selected = [row for row in blocks if isinstance(row, dict) and row.get("benchmark_version") == 1]
    if len(selected) != 1:
        raise ValueError(f"{path.name}: exactly one benchmark_version=1 object is required")
    return selected[0]


def text_of(path: Path) -> str:
    if path.suffix.lower() == ".xml":
        return " ".join(ET.fromstring(path.read_bytes()).itertext())
    if path.suffix.lower() in {".html", ".htm"}:
        class Text(HTMLParser):
            def __init__(self): super().__init__(); self.parts = []
            def handle_data(self, data): self.parts.append(data)
        parser = Text(); parser.feed(path.read_text(encoding="utf-8")); return " ".join(parser.parts)
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PDF comparator needs pypdf in the verified venv, or a registered XML/HTML full text; never substitute an abstract") from exc
        return " ".join(page.extract_text() or "" for page in PdfReader(path).pages)
    raise ValueError("Comparator must be registered XML/HTML/PDF full text, not notes or an abstract")


def _norm(text): return re.sub(r"\s+", " ", text).strip().casefold()


def protected_plan(doc):
    """Fix prewriting rationale/ranges; later evidence mappings may be completed without a reset."""
    adaptation = doc.get("adaptation", {})
    references = adaptation.get("references", {})
    return {"comparators": [{k: row.get(k) for k in ("citekey", "fulltext", "sha256", "relevance", "observations", "evidence")} for row in doc.get("comparators", [])],
            "structure": adaptation.get("structure"), "displays": adaptation.get("displays"),
            "references": {"ranges": references.get("ranges"), "basis": references.get("basis"),
                           "roles": [{k: row.get(k) for k in ("id", "section", "claim", "source_type", "required")} for row in references.get("roles", [])]}}


def plan_hash(doc): return hashlib.sha256(json.dumps(protected_plan(doc), sort_keys=True).encode()).hexdigest()


def verify_benchmark(project: Path, layer="science", *, require_lock=True) -> list[str]:
    from pubmed.identity import errors
    from .refproof import validate_local_proof
    doc = dossier(project, layer); problems = []
    if layer == "science":
        ok, defects, _ = validate_local_proof(project)
        if not ok: return ["Benchmark reference identity: " + "; ".join(defects[:3])]
    entries = {e["citekey"]: e for e in load(project, "06_refs/library.json").get("entries", [])}
    records = {r["citekey"]: r for r in load(project, "06_refs/fulltext/retrieval_manifest.json").get("retrievals", [])}
    rows = doc.get("comparators", [])
    if len(rows) < 2 or len({row.get("citekey") for row in rows}) != len(rows):
        problems.append("Use multiple distinct close full-text comparators; duplicated records are not independent examples")
    if not substantive(doc.get("adequacy_rationale")): problems.append("Explain comparator fit and evidence/access limitations")
    for row in rows:
        key = row.get("citekey"); entry = entries.get(key); record = records.get(key, {})
        if not entry and layer == "journal":
            from pubmed.eutils import parse_pubmed_xml
            rel, metadata = _safe_path(project, record.get("metadata_cache", ""))
            if (not re.fullmatch(r"06_refs/cache/benchmark_efetch_pubmed_[A-Za-z0-9_.-]+\.xml", rel) or
                    not metadata.is_file() or str(record.get("metadata_sha256", "")).upper() != _sha256(metadata)):
                problems.append(f"{key}: comparator-only fresh PubMed payload missing/changed"); continue
            entry = next((e for e in parse_pubmed_xml(metadata.read_text(encoding="utf-8")) if e["pmid"] == record.get("pmid")), None)
        if entry and layer == "journal" and key in entries:
            ok, defects, _ = validate_local_proof(project, required_keys={key})
            if not ok: problems.append(f"{key}: formal reference proof invalid: " + "; ".join(defects[:2]))
        if not entry: problems.append(f"{key}: absent from genuine PubMed source records"); continue
        if any("RETRACT" in flag or "CONCERN" in flag for flag in entry.get("flags", [])):
            problems.append(f"{key}: retracted/concern-flagged paper is not a credible comparator")
        rel, path = _safe_path(project, row.get("fulltext", ""))
        if (not rel.startswith("06_refs/fulltext/") or not path.is_file() or record.get("fulltext") != rel or
                record.get("access") not in {"oa", "authorized"} or record.get("sha256", "").upper() != _sha256(path) or
                str(row.get("sha256", "")).upper() != _sha256(path)):
            problems.append(f"{key}: full-text retrieval/hash/access evidence missing or changed"); continue
        problems.extend(f"{key}: {error}" for error in errors(entry, path, record))
        relevance = row.get("relevance", {})
        for field in ("topic", "design", "analysis"):
            if not substantive(relevance.get(field)): problems.append(f"{key}: concrete {field} comparability needed")
        if layer == "journal":
            target = load(project, "08_submission/target_journal.json")
            same_issn = target.get("issn") and str(target["issn"]) in str(entry.get("issn", ""))
            if not same_issn and _norm(entry.get("journal", "")) != _norm(target.get("journal", "")):
                problems.append(f"{key}: comparator is not from the selected journal")
        observations = row.get("observations", {})
        for field in ("methods_outline", "discussion_structure", "reference_roles", "display_roles"):
            if not substantive(observations.get(field)): problems.append(f"{key}: substantive observations.{field} needed")
        for field in ("main_figures", "main_tables", "supp_figures", "supp_tables"):
            if type(observations.get(field)) is not int or observations[field] < 0: problems.append(f"{key}: observed {field} count needed")
        citations = observations.get("citations", {})
        if any(type(citations.get(section)) is not int or citations[section] < 0 for section in SECTIONS):
            problems.append(f"{key}: separate observed section/supplement citation counts needed")
        excerpts = row.get("evidence", [])
        if not {"methods", "discussion", "display"}.issubset({e.get("kind") for e in excerpts}):
            problems.append(f"{key}: methods/discussion/display full-text locators needed")
        actual = _norm(text_of(path))
        for evidence in excerpts:
            if not evidence.get("locator") or not substantive(evidence.get("quote")) or _norm(evidence["quote"]) not in actual:
                problems.append(f"{key}: excerpt not found in registered full text; never backfill quotations")
    adaptation = doc.get("adaptation", {}); structure = adaptation.get("structure", {})
    for field in ("methods", "discussion", "main_vs_supplement", "declarations"):
        if not substantive(structure.get(field)): problems.append(f"project structure.{field}: explain actual adaptation")
    refs = adaptation.get("references", {})
    if not substantive(refs.get("basis")): problems.append("Project reference range needs comparator/project basis, not a green-gate target")
    for section in (*SECTIONS, "library", "main_total"):
        value = refs.get("ranges", {}).get(section)
        if not isinstance(value, list) or len(value) != 2 or any(type(v) is not int or v < 0 for v in value) or value[0] > value[1]:
            problems.append(f"{section}: evidence-based expected range required (advisory, not a quota)")
    roles = refs.get("roles", [])
    if not roles or len({r.get("id") for r in roles}) != len(roles): problems.append("Unique project-specific literature argument roles required")
    for role in roles:
        if not role.get("id") or role.get("section") not in SECTIONS or type(role.get("required")) is not bool or not substantive(role.get("claim")) or not role.get("source_type"):
            problems.append("Invalid literature argument role")
    displays = adaptation.get("displays", {})
    for field in ("inventory_rationale", "essential_questions", "omissions"):
        if not substantive(displays.get(field)): problems.append(f"Display adaptation.{field} needs a study-specific account")
    if layer == "journal":
        expected = {rel: _sha256(project / rel) for rel in ("08_submission/target_journal.json", "08_submission/submission_requirements.json")}
        if doc.get("target_hashes") != expected: problems.append("Journal benchmark does not match selected journal/article-type requirements")
    if require_lock:
        lock = load(project, f".wf/benchmark_{layer}_lock.json")
        if lock.get("plan_hash") != plan_hash(doc): problems.append("Prewriting benchmark plan changed: do not lower ranges/reset evidence to pass; use scoped, justified replan")
    return problems


def seal(project: Path, layer="science"):
    from .state import State
    from .revision import permits, guard_outputs
    owner = "S07_artifacts" if layer == "science" else "S20_journal"
    state = State(project).load()
    if state.current != owner and not permits(project, owner): raise ValueError(f"Benchmark plan belongs to {owner}; no late untracked reset")
    problems = verify_benchmark(project, layer, require_lock=False)
    if problems: raise ValueError("; ".join(problems[:8]))
    path = project / f".wf/benchmark_{layer}_lock.json"; doc = dossier(project, layer)
    if path.is_file() and load(project, path.relative_to(project).as_posix()).get("plan_hash") != plan_hash(doc):
        revision = __import__("wfcore.revision", fromlist=["active"]).active(project)
        if not revision or revision.get("status") != "active": raise ValueError("Changed sealed plan requires an explicit scoped feedback replan, never a pass-seeking reset")
    guard_outputs(project, [path]); atomic_json(path, {"plan_hash": plan_hash(doc), "owner": owner})


def citation_metrics(project):
    from .checks.refs import citekeys
    metrics = {}; union = set()
    for section in SECTIONS:
        rel = "07_manuscript/" + ("supplementary_methods" if section == "supplementary" else section) + ".md"
        path = project / rel; keys = set(citekeys(path.read_text(encoding="utf-8"))) if path.is_file() else set()
        metrics[section] = len(keys)
        if section != "supplementary": union.update(keys)
    # Results/abstract may also contain legitimate citations; they belong to main_total.
    for name in ("results", "abstract"):
        path = project / f"07_manuscript/{name}.md"
        if path.is_file(): union.update(citekeys(path.read_text(encoding="utf-8")))
    assembled = project / "07_manuscript/full_manuscript.md"
    if assembled.is_file(): union = set(citekeys(assembled.read_text(encoding="utf-8")))
    metrics["main_total"] = len(union); metrics["library"] = len(load(project, "06_refs/library.json").get("entries", []))
    return metrics


def coverage(project: Path, section=None, *, library_only=False, layer="science") -> list[str]:
    from .checks.refs import citekeys
    refs = dossier(project, layer)["adaptation"]["references"]
    keys = {e["citekey"] for e in load(project, "06_refs/library.json").get("entries", [])}; problems = []
    for role in refs["roles"]:
        if section and role["section"] != section: continue
        chosen = role.get("citekeys", [])
        if role["required"] and not chosen: problems.append(f"{role['id']}: missing literature basis for {role['claim']}")
        if any(key not in keys for key in chosen): problems.append(f"{role['id']}: selected source absent from library")
        if library_only or not chosen: continue
        name = "supplementary_methods" if role["section"] == "supplementary" else role["section"]
        rel = f"07_manuscript/{name}.md" if layer == "science" else "08_submission/integration/" + ("supplementary_methods.md" if name == "supplementary_methods" else "full_manuscript.md")
        path = project / rel; passage = role.get("passage", "")
        if not substantive(passage) or not path.is_file() or passage not in path.read_text(encoding="utf-8") or not set(chosen).issubset(set(citekeys(passage))):
            problems.append(f"{role['id']}: actual argument passage does not cite its declared supporting sources")
    return problems


def display_fit(project: Path, layer="science"):
    plan_rel = "01_protocol/artifact_plan.json" if layer == "science" else "08_submission/integration/artifact_plan.json"
    plan = load(project, plan_rel); problems = []; purposes = {}
    for group in ("main_figures", "main_tables", "supp_figures", "supp_tables"):
        for entry in plan.get(group, []):
            key = entry["id"]; contract = entry.get("reader_contract", {})
            for field in ("question", "placement_reason", "nonredundancy", "misinterpretation_risk"):
                if not substantive(contract.get(field)): problems.append(f"{key}: specific reader_contract.{field} needed")
            purpose = _norm(str(contract.get("question", "")) + " " + str(contract.get("placement_reason", "")))
            if purpose in purposes: problems.append(f"{key} and {purposes[purpose]} reuse the same purpose/placement; explain their actual distinct contribution")
            purposes[purpose] = key
    return problems


def acceptance_rel(layer, final=False):
    suffix = "science" if layer == "science" else "journal_final" if final else "journal_pre"
    return f".wf/executor_acceptance_{suffix}.json"


def contract_hash(entry):
    return hashlib.sha256(json.dumps(entry.get("reader_contract", {}), sort_keys=True).encode()).hexdigest()


def display_source(project, entry, layer, final):
    candidates = [entry.get("file")]
    if layer == "journal" and not final:
        candidates = [entry.get("preview"), entry.get("source_file"), entry.get("file")]
    for rel in candidates:
        if rel and _safe_path(project, rel)[1].is_file(): return rel
    raise ValueError(f"{entry['id']}: actual render or explicit preproduction preview/source_file required; no guessed role source")


def acceptance_inputs(project, layer="science", *, final=False):
    from .readiness import reader_inputs
    if layer == "science": files = set(reader_inputs(project)) | {SCIENCE}
    else:
        files = {JOURNAL, "08_submission/target_journal.json", "08_submission/submission_requirements.json"}
        files.update(p.relative_to(project).as_posix() for p in (project / "08_submission/integration").glob("*.md"))
        files.add("08_submission/integration/artifact_plan.json")
        for group in ("main_figures", "main_tables", "supp_figures", "supp_tables"):
            for entry in load(project, "08_submission/integration/artifact_plan.json").get(group, []):
                files.add(display_source(project, entry, layer, final))
        if final:
            manifest = load(project, "08_submission/bundle/manifest.json")
            files.add("08_submission/bundle/manifest.json"); files.update(item["file"] for item in manifest["items"])
    files.update({"06_refs/library.json", "06_refs/refs.bib"})
    files.update(row["fulltext"] for row in dossier(project, layer)["comparators"])
    return {rel: _sha256(_safe_path(project, rel)[1]) for rel in sorted(files)}


def verify_acceptance(project, layer="science", *, final=False, report=None):
    report = load(project, acceptance_rel(layer, final)) if report is None else report
    problems = []
    problems.extend(coverage(project, layer=layer))
    problems.extend(display_fit(project, layer))
    expected = acceptance_inputs(project, layer, final=final)
    if report.get("inputs") != expected or report.get("final_outputs") is not final: problems.append("Executor acceptance is missing/stale for actual current outputs")
    if not substantive(report.get("reviewer")): problems.append("Identify actual executor review; do not claim a human or independent reviewer")
    for dimension in DIMENSIONS:
        row = report.get("findings", {}).get(dimension, {})
        if row.get("verdict") != "PASS" or not substantive(row.get("observation")): problems.append(f"Executor must resolve and describe {dimension}, not merely label PASS")
    if report.get("unresolved") != []: problems.append("Unresolved routine defects prevent delivery")
    plan = load(project, "01_protocol/artifact_plan.json" if layer == "science" else "08_submission/integration/artifact_plan.json")
    if layer == "journal":
        from .journalrules import display_limits, compare
        counts = {group: len(plan.get(group, [])) for group in ("main_figures", "main_tables", "supp_figures", "supp_tables")}
        counts["main_display_items"] = counts["main_figures"] + counts["main_tables"]
        problems.extend(compare(counts, display_limits(project)))
    if load(project, f".wf/benchmark_{layer}_lock.json").get("plan_hash") != plan_hash(dossier(project, layer)):
        problems.append("Sealed project benchmark changed; acceptance cannot bless an untracked replan")
    displays = [entry for group in ("main_figures", "main_tables", "supp_figures", "supp_tables") for entry in plan.get(group, [])]
    findings = report.get("display_findings", {}); unique = set()
    if set(findings) != {entry["id"] for entry in displays}: problems.append("Executor findings must cover each actual figure/table once")
    for entry in displays:
        row = findings.get(entry["id"], {})
        if row.get("reviewed_file") != display_source(project, entry, layer, final):
            problems.append(f"{entry['id']}: finding must identify the actual inspected display file")
        if row.get("contract_hash") != contract_hash(entry): problems.append(f"{entry['id']}: reader finding does not bind its current specific contract")
        observation = row.get("observation", "")
        if not substantive(observation) or _norm(observation) in unique: problems.append(f"{entry['id']}: concrete non-copied rendered-display observation required")
        unique.add(_norm(observation))
    deviations = report.get("range_deviations", {})
    if layer == "science":
        metrics = citation_metrics(project); ranges = dossier(project)["adaptation"]["references"]["ranges"]
        for key, actual in metrics.items():
            if not ranges[key][0] <= actual <= ranges[key][1] and not substantive(deviations.get(key)):
                problems.append(f"{key} observed {actual}, benchmark range {ranges[key]}: justify coverage, never pad or lower the locked range")
    return problems
