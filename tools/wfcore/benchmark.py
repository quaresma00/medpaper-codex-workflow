"""Source-bound project benchmarks and executor acceptance, not universal quotas."""
from __future__ import annotations

from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from statistics import median

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


def _supplementary_texts(project, row, entry):
    """Read only hash-bound supplements linked by this article's own JATS metadata."""
    import xml.etree.ElementTree as ET
    from zipfile import ZipFile
    texts = []
    for source in row.get("supplementary_sources", []):
        rel, path = _safe_path(project, source.get("file", ""))
        xml_rel, xml = _safe_path(project, source.get("article_xml", ""))
        if (not rel.startswith("06_refs/fulltext/supplements/" + row["citekey"] + "/")
                or path.suffix.lower() not in {".docx", ".pdf"}
                or not path.is_file() or str(source.get("sha256", "")).upper() != _sha256(path)
                or not xml_rel.startswith("06_refs/fulltext/") or xml.suffix.lower() != ".xml"
                or not xml.is_file() or str(source.get("article_xml_sha256", "")).upper() != _sha256(xml)):
            raise ValueError("Supplementary source/own-article XML is absent, changed or outside its declared article directory")
        article = ET.fromstring(xml.read_text(encoding="utf-8"))
        ids = {a.get("pub-id-type"): (a.text or "").strip()
               for a in article.findall("./front/article-meta/article-id")}
        if (ids.get("pmid") != str(entry.get("pmid", ""))
                or ids.get("pmcid") != entry.get("pmcid")
                or ids.get("doi", "").casefold() != str(entry.get("doi", "")).casefold()):
            raise ValueError("Supplementary XML own PMID/PMCID/DOI does not match the verified article")
        href = "{http://www.w3.org/1999/xlink}href"
        linked = {Path(a.get(href, "")).name
                  for parent in article.findall(".//supplementary-material") for a in parent.iter()
                  if a.get(href)}
        expected_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/" + str(entry["pmcid"]) + "/supplementaryFiles"
        if path.name not in linked or source.get("source_url") != expected_url:
            raise ValueError("Supplement is not linked by this article's own metadata and its exact public OA source")
        if path.suffix.lower() == ".docx":
            with ZipFile(path) as archive:
                document = ET.fromstring(archive.read("word/document.xml"))
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            text = "\n".join("".join(t.text or "" for t in p.iter(ns + "t"))
                             for p in document.iter(ns + "p"))
        else:
            text = text_of(path)
        if not text.strip(): raise ValueError("Supplement is not text-readable; inspect/resolve the actual source")
        texts.append(_norm(text))
    return texts


def _display_present(actual, supplements, display):
    match = re.fullmatch(r"(?i)(?:figure|fig\.?|table)\s+(S?\d+)", str(display.get("id", "")))
    if not match: return False
    kind = r"(?:figure|fig\.?)" if str(display.get("kind", "")).endswith("figure") else "table"
    if re.search(r"\b" + kind + r"\s*" + re.escape(match[1]) + r"\b", actual, re.I): return True
    if not str(display.get("kind", "")).startswith("supp_") or not match[1].upper().startswith("S"):
        return False
    number = re.escape(match[1][1:])
    # Publishers use both 'Supplementary Figure 1' and 'Figure S1'.
    caption = r"\b(?:(?:supplementary|supplemental)\s+" + kind + r"s?\s+S?" + number + r"\b|" + kind + r"\s+S" + number + r"\b)"
    return any(re.search(caption, text, re.I) for text in supplements)


def protected_plan(doc):
    """Fix prewriting rationale/ranges; later evidence mappings may be completed without a reset."""
    adaptation = doc.get("adaptation", {})
    references = adaptation.get("references", {})
    result = {"comparators": [{k: row.get(k) for k in ("citekey", "fulltext", "sha256", "relevance", "observations", "evidence")} for row in doc.get("comparators", [])],
            "structure": adaptation.get("structure"), "displays": adaptation.get("displays"),
            "references": {"ranges": references.get("ranges"), "basis": references.get("basis"),
                           "roles": [{k: row.get(k) for k in ("id", "section", "claim", "source_type", "required")} for row in references.get("roles", [])]}}
    # Preserve historical plan hashes byte-for-byte when the new fields were absent.
    if "comparator_selection" in doc: result["comparator_selection"] = doc["comparator_selection"]
    if "library_floor" in references: result["references"]["library_floor"] = references["library_floor"]
    for original, fixed in zip(doc.get("comparators", []), result["comparators"]):
        if "published_at" in original: fixed["published_at"] = original["published_at"]
        if "supplementary_sources" in original: fixed["supplementary_sources"] = original["supplementary_sources"]
    return result


def recent_benchmark_required(project, doc):
    """Engine refresh never rewrites older completed comparator selections."""
    if doc.get("comparator_selection", {}).get("version") == 1: return True
    from .state import State, version_tuple
    try: state = State(project).load()
    except (OSError, ValueError): return False
    return version_tuple(str(state.data.get("engine_pin", "0"))) >= (1, 28, 0)


def recent_comparator_problems(project, doc, entries, *, fresh=False):
    """Check current selection and actual display observations, not medical understanding."""
    if not recent_benchmark_required(project, doc): return []
    problems=[]; selection=doc.get("comparator_selection", {})
    try:
        searched=date.fromisoformat(selection["searched_at"])
        since=date.fromisoformat(selection["period_start"])
        today=datetime.now(timezone.utc).date()
        if searched>today or since>=searched or (fresh and (today-searched).days>90):
            raise ValueError("Search the current literature before sealing; future or stale search dates are not current evidence")
        if (searched-since).days>731:
            raise ValueError("Start with the latest 24 months; older relevant papers need article-specific scientific exceptions")
    except (KeyError, TypeError, ValueError) as exc:
        return ["Recent comparator search: "+str(exc)]
    if not substantive(selection.get("selection_basis")):
        problems.append("Explain how recent topic/design/method similarity determined comparator selection")
    searches=selection.get("searches", [])
    if not searches: problems.append("Bind the actual recent PubMed search query and raw search response, not a claimed search-complete boolean")
    for search in searches:
        try:
            rel,path=_safe_path(project,search.get("cache_file", ""))
            if (not rel.startswith("06_refs/cache/esearch_") or not path.is_file()
                    or search.get("sha256", "").upper()!=_sha256(path)):
                raise ValueError("Actual comparator search response is absent or changed")
            raw=json.loads(path.read_text(encoding="utf-8")).get("esearchresult")
            if (not isinstance(raw,dict) or not isinstance(raw.get("idlist"),list)
                    or not str(search.get("query", "")).strip() or not raw.get("querytranslation")
                    or search.get("translation")!=raw["querytranslation"]):
                raise ValueError("Keep the actual query/translation and raw ESearch results for the recent search")
        except (OSError, ValueError, TypeError, KeyError) as exc: problems.append(str(exc))
    rows=doc.get("comparators", [])
    if not 5<=len(rows)<=10:
        exception=selection.get("count_exception", {})
        if not substantive(exception.get("reason")) or len(str(exception.get("reason", "")))<80:
            problems.append("Read about 5–10 recent close full texts; a genuinely sparse/different field needs a concrete search-based count exception, never cost or convenience")
    exceptions=selection.get("older_article_exceptions", {})
    grouped={"main_figure":"main_figures","main_table":"main_tables","supp_figure":"supp_figures","supp_table":"supp_tables"}
    for row in rows:
        key=row.get("citekey"); entry=entries.get(key,{})
        try:
            published=date.fromisoformat(row.get("published_at", ""))
            if str(published.year)!=str(entry.get("year")):
                raise ValueError("publication date conflicts with genuine PubMed year")
            if published>searched: raise ValueError("comparator was published after the recorded search")
            if published<since and not substantive(exceptions.get(key)):
                raise ValueError("older comparator needs an article-specific scientific reason after the recent search")
        except (TypeError, ValueError) as exc: problems.append(f"{key}: actual publication date/recency: {exc}")
        obs=row.get("observations", {}); inventory=obs.get("display_inventory", [])
        if not isinstance(inventory,list): problems.append(f"{key}: read the actual figure/table inventory"); continue
        identifiers=[d.get("id") for d in inventory]
        if len(identifiers)!=len(set(identifiers)):
            problems.append(f"{key}: duplicate comparator display identifiers")
        for kind, field in grouped.items():
            if sum(d.get("kind")==kind for d in inventory)!=obs.get(field):
                problems.append(f"{key}: actual {field} display inventory must match the observed count")
        for display in inventory:
            if (display.get("kind") not in grouped or not display.get("id") or not display.get("locator")
                    or any(not substantive(display.get(field)) for field in ("type", "clinical_role", "analysis_shown"))):
                problems.append(f"{key}: every actual display needs type, clinical role, analysis shown and exact page/legend locator")
    displays=doc.get("adaptation", {}).get("displays", {})
    observed=[r.get("observations", {}).get("main_figures") for r in rows]
    if observed and all(type(n) is int for n in observed):
        plan=load(project,"01_protocol/artifact_plan.json")
        planned=len(plan.get("main_figures", [])); middle=median(observed)
        if planned<middle:
            comparison=displays.get("count_comparison", {})
            if (comparison.get("planned_main_figures")!=planned or comparison.get("comparator_median_main_figures")!=middle
                    or len(str(comparison.get("scientific_reason", "")).strip())<80):
                problems.append("Main figures are fewer than recent comparators: compare the actual counts and explain design/evidence differences while covering required reader tasks; compactness or cost is insufficient")
    return problems


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
    if layer=="science":
        problems.extend(recent_comparator_problems(project,doc,entries,fresh=not require_lock))
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
                record.get("access") not in {"oa", "authorized", "external"} or record.get("sha256", "").upper() != _sha256(path) or
                str(row.get("sha256", "")).upper() != _sha256(path)):
            problems.append(f"{key}: full-text retrieval/hash/access evidence missing or changed"); continue
        if record.get("access")=="external" and not substantive(record.get("authorization_note")):
            problems.append(f"{key}: preserve the actual user-selected external access basis; do not label it OA/institutional access")
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
        try:
            supplements = _supplementary_texts(project, row, entry)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            problems.append(f"{key}: {exc}"); supplements = []
        if layer=="science" and recent_benchmark_required(project,doc):
            for display in observations.get("display_inventory",[]):
                if not _display_present(actual, supplements, display):
                    problems.append(f"{key}: actual comparator display {display.get('id')} is absent from the registered full text; read its real caption/figure instead of inventing an inventory")
        for evidence in excerpts:
            if not evidence.get("locator") or not substantive(evidence.get("quote")) or _norm(evidence["quote"]) not in actual:
                problems.append(f"{key}: excerpt not found in registered full text; never backfill quotations")
    adaptation = doc.get("adaptation", {}); structure = adaptation.get("structure", {})
    for field in ("methods", "discussion", "main_vs_supplement", "declarations"):
        if not substantive(structure.get(field)): problems.append(f"project structure.{field}: explain actual adaptation")
    refs = adaptation.get("references", {})
    if layer=="science" and recent_benchmark_required(project,doc):
        floor=refs.get("library_floor",45)
        if type(floor) is not int or floor<45:
            problems.append("Keep the agreed literature-pool floor (normally45); do not autonomously reduce it to match the current library. A changed author requirement must be handled explicitly before resealing")
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
        if layer=="science" and recent_benchmark_required(project,doc):
            agreed=lock.get("library_floor")
            if type(agreed) is not int or agreed<45:
                problems.append("Seal the actual agreed literature-pool floor before writing; a later lower configuration is not an exception")
    return problems


def seal(project: Path, layer="science"):
    from .state import State
    from .revision import permits, guard_outputs
    owner = "S07_artifacts" if layer == "science" else "S20_journal"
    state = State(project).load()
    if state.current != owner and not permits(project, owner): raise ValueError(f"Benchmark plan belongs to {owner}; no late untracked reset")
    problems = verify_benchmark(project, layer, require_lock=False)
    if layer == "science" and not state.pin_excludes(owner,"1.22.0"):
        from .state import version_tuple
        if version_tuple(str(state.data.get("pipeline_version","0"))) >= (1,22,0):
            from .displayquality import story_problems
            problems += story_problems(load(project,"01_protocol/artifact_plan.json"),dossier(project))
    if problems: raise ValueError("; ".join(problems[:8]))
    path = project / f".wf/benchmark_{layer}_lock.json"; doc = dossier(project, layer)
    if path.is_file() and load(project, path.relative_to(project).as_posix()).get("plan_hash") != plan_hash(doc):
        revision = __import__("wfcore.revision", fromlist=["active"]).active(project)
        if not revision or revision.get("status") != "active": raise ValueError("Changed sealed plan requires an explicit scoped feedback replan, never a pass-seeking reset")
    payload={"plan_hash":plan_hash(doc),"owner":owner}
    if layer=="science" and recent_benchmark_required(project,doc):
        floor=doc["adaptation"]["references"].get("library_floor",45)
        explicit=state.config().get("targets",{}).get("reflib_min",0)
        if type(explicit) is int and explicit>floor: floor=explicit
        if path.is_file():
            previous=load(project,path.relative_to(project).as_posix()).get("library_floor",floor)
            if type(previous) is int and previous>floor:
                raise ValueError("Do not lower the sealed agreed literature-pool floor to fit current references; report an infeasible author requirement")
        payload["library_floor"]=floor
    guard_outputs(project, [path]); atomic_json(path,payload)


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
    doc=dossier(project, layer); refs = doc["adaptation"]["references"]
    keys = {e["citekey"] for e in load(project, "06_refs/library.json").get("entries", [])}; problems = []
    if layer=="science" and section is None and recent_benchmark_required(project,doc):
        from .state import State
        floor=refs.get("library_floor",45)
        explicit=State(project).load().config().get("targets",{}).get("reflib_min",0)
        if type(explicit) is int and explicit>floor: floor=explicit
        lock_path=project/".wf/benchmark_science_lock.json"
        agreed=load(project,".wf/benchmark_science_lock.json").get("library_floor",0) if lock_path.is_file() else 0
        if type(agreed) is int and agreed>floor: floor=agreed
        if len(keys)<floor:
            problems.append(f"Verified literature pool has {len(keys)} unique sources versus agreed minimum{floor}; complete relevant role coverage, do not lower the locked floor or pad unrelated citations. Report infeasible coverage to the author")
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
    from .clinicalpresentation import verify_plan
    problems.extend(verify_plan(project,layer=="journal"))
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


def acceptance_inputs(project, layer="science", *, final=False, report=None):
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
    result={rel: _sha256(_safe_path(project, rel)[1]) for rel in sorted(files)}
    if report is None and (project/acceptance_rel(layer,final)).is_file():
        report=load(project,acceptance_rel(layer,final))
    if report and final:
        from .medicalstyle import layout_inputs
        result.update(layout_inputs(project,report))
    from .medicalstyle import display_language_inputs
    result.update(display_language_inputs(project,layer,final,report))
    return result


def verify_acceptance(project, layer="science", *, final=False, report=None):
    report = load(project, acceptance_rel(layer, final)) if report is None else report
    problems = []
    problems.extend(coverage(project, layer=layer))
    problems.extend(display_fit(project, layer))
    expected = acceptance_inputs(project, layer, final=final,report=report)
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
    from .medicalstyle import verify as verify_medical_style
    problems.extend(verify_medical_style(project,report,layer,final))
    return problems
