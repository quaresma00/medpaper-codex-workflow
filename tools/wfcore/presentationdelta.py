"""Prove post-freeze presentation amendments without rewriting scientific approval."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from .readiness import atomic_json
from .packagefreeze import _sha256, _safe_path

LEDGER = ".wf/presentation_deltas.json"
PROTECTED = ("02_data/", "03_analysis/", "06_refs/")


def text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        from .buildproof import content_parts
        return "\n".join(content_parts(path))
    if path.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook
        workbook = load_workbook(path, read_only=True, data_only=False)
        try:
            return json.dumps([(sheet.title, [[cell.coordinate, cell.value, cell.number_format] for row in sheet for cell in row if cell.value is not None])
                               for sheet in workbook], default=str, ensure_ascii=False)
        finally: workbook.close()
    return path.read_text(encoding="utf-8")


def canonical(value: str, project: Path) -> str:
    from .journalspec import spelling, aliases, load
    from .displayrefs import normalize
    value=normalize(value,load(project))
    for original, label in aliases(load(project)).items():
        value = re.sub(r"(?mi)^(#{1,6}\s+)" + re.escape(label) + r"\s*$", r"\g<1>" + original, value)
    value = spelling(value, "american").replace("\u2212", "-")
    value = re.sub(r"(?<=\d)\s*–\s*(?=[+\-]?\d)", " to ", value)
    value = re.sub(r"(?<=\d)[,\u2009\u202f\u00a0](?=\d{3}(?:\D|$))", "", value)
    value = re.sub(r"(?<![\w.])0\.(\d+)", r".\1", value)
    # Formatting/punctuation only. Keep word order, signs, units, identifiers and negation.
    return " ".join(re.findall(r"[@\w]+(?:[.\-/][\w]+)*|[+\-<>≤≥%]", value.casefold()))


def without_adjacent_duplicates(value):
    # Comparison only, never rewrite prose. Only identical adjacent whole sentences or
    # paragraphs: nonadjacent numbers/clauses and changed qualifiers remain protected.
    paragraphs=[]
    for paragraph in re.split(r"\n\s*\n",value):
        sentences=re.split(r"(?<=[.!?])\s+(?=[A-Z])",paragraph.strip())
        compact=[]
        for sentence in sentences:
            if not compact or sentence!=compact[-1]: compact.append(sentence)
        paragraph=" ".join(compact)
        if not paragraphs or paragraph!=paragraphs[-1]: paragraphs.append(paragraph)
    return "\n\n".join(paragraphs)


def snapshot(project: Path, files: dict) -> dict:
    output = {}
    for rel, digest in files.items():
        path = project / rel
        if rel.startswith(("04_tables/", "05_figures/", "07_manuscript/", "08_submission/integration/", "08_submission/bundle/")) and path.is_file():
            row = {"sha256": digest}
            if path.suffix.lower() in {".md", ".txt", ".xlsx", ".docx"}:
                row["text"] = text(path)
            from .determinism import content_sha256
            row["container"] = content_sha256(path)
            output[rel] = row
    return output


def classify(project: Path, revision: dict) -> dict:
    before = revision.get("presentation_baseline", {})
    baseline = revision.get("baseline", {})
    from .revision import snapshot as current_files
    current = current_files(project)
    changed = sorted(rel for rel in set(baseline) | set(current) if baseline.get(rel) != current.get(rel))
    reasons, uncertain = [], []
    from .determinism import content_sha256
    for rel in changed:
        if rel.startswith(PROTECTED) or rel in {"01_protocol/protocol_v1.md", "01_protocol/protocol_final.md", "01_protocol/analysis_contract.json", "01_protocol/study_facts.json"}:
            reasons.append(f"{rel}: scientific input/analysis/reference identity changed"); continue
        old = before.get(rel); path = project / rel
        if not old:
            if rel.startswith(("04_tables/", "05_figures/out/", "07_manuscript/")):
                reasons.append(f"{rel}: newly added scientific source needs owner review")
            continue
        if not path.is_file():
            reasons.append(f"{rel}: removal requires explicit inventory/migration proof"); continue
        if old["container"] == content_sha256(path): continue
        if "text" not in old:
            uncertain.append(rel); continue
        new = text(path)
        if canonical(old["text"], project) == canonical(new, project): continue
        if path.suffix.lower() in {".md",".txt"} and canonical(without_adjacent_duplicates(old["text"]),project)==canonical(without_adjacent_duplicates(new),project): continue
        if path.suffix.lower() == ".docx":
            # A digest cannot determine scientific equivalence of rewritten Word text.
            uncertain.append(rel); continue
        if path.suffix.lower() == ".xlsx":
            reasons.append(f"{rel}: cell identities, values, units or number formats changed"); continue
        from .checks.numbers import NUM_RE
        from collections import Counter
        from .displayrefs import scrub
        nums = lambda value: NUM_RE.findall(scrub(re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", value)))
        cites = lambda value: re.findall(r"@[\w:./-]+", value)
        def clinical_qualifiers(value):
            mapping = {"higher":"UP", "increased":"UP", "elevated":"UP", "lower":"DOWN", "decreased":"DOWN", "reduced":"DOWN", "not":"NEGATION", "no":"NEGATION", "without":"NEGATION"}
            words = re.findall(r"\b(?:higher|increased|elevated|lower|decreased|reduced|not|no|without|causal|causally|prospective|retrospective|randomized|observational)\b", value.casefold())
            return Counter(mapping.get(word, word) for word in words)
        if nums(old["text"]) != nums(new) or cites(old["text"]) != cites(new) or clinical_qualifiers(old["text"]) != clinical_qualifiers(new):
            reasons.append(f"{rel}: numerical/citation context, direction, negation or study-design claim changed")
        else: uncertain.append(rel)
    review = revision.get("meaning_review", {})
    if uncertain and not reasons:
        hashes = {rel: _sha256(project / rel) for rel in uncertain}
        sections = ("population_comparison", "endpoints_time_units", "direction_negation_uncertainty", "methods_claims", "rendered_displays")
        if (review.get("files") == hashes and review.get("baseline") == {rel: before[rel]["sha256"] for rel in uncertain}
                and review.get("verdict") == "UNCHANGED_SCIENCE"
                and all(len(str(review.get(key, "")).strip()) >= 40 for key in sections)):
            uncertain = []
    return {"class": "scientific" if reasons else "needs_executor_meaning_review" if uncertain else "presentation",
            "reasons": reasons, "needs_review": uncertain, "changed": changed}


def entries(project: Path) -> list:
    path = project / LEDGER
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def covered(project: Path, rel: str, old: str, new: str) -> bool:
    if old == new: return True
    digest = old.casefold()
    for entry in entries(project):
        row = entry.get("files", {}).get(rel)
        if not row or row["old"].casefold() != digest: continue
        proof = project / ".wf/revisions" / f"{entry['round']}.json"
        if not proof.is_file(): return False
        record = json.loads(proof.read_text(encoding="utf-8"))
        if record.get("status") != "complete" or not record.get("validation", {}).get("ok"): return False
        digest = row["new"].casefold()
        if digest == new.casefold(): return True
    if digest == new.casefold(): return True
    from .revision import active
    record = active(project)
    return bool(record and record.get("presentation_candidate") and record.get("content_classification", {}).get("class") == "presentation"
                and record.get("baseline", {}).get(rel, "").casefold() == digest and (project / rel).is_file() and _sha256(project / rel).casefold() == new.casefold())


def commit(project: Path, revision: dict, summary: str) -> None:
    result = classify(project, revision)
    if result["class"] != "presentation": raise ValueError("cannot inherit approval for changed/unreviewed science")
    rows = {rel: {"old": revision["baseline"][rel], "new": _sha256(project / rel)}
            for rel in result["changed"] if rel in revision["baseline"] and (project / rel).is_file()}
    ledger = entries(project)
    ledger.append({"round": revision["round_id"], "summary": summary, "files": rows,
                   "basis": "actual scoped validation and unchanged-science comparison; not a new independent audit"})
    atomic_json(project / LEDGER, ledger)
    from .packagefreeze import FREEZE_REL, write_freeze, sync_evidence
    freeze_path = project / FREEZE_REL
    if freeze_path.is_file():
        parent = json.loads(freeze_path.read_text(encoding="utf-8"))
        evidence_path = project / "08_submission/evidence/evidence_manifest.json"
        context = json.loads(evidence_path.read_text(encoding="utf-8")).get("audit_context_id") if evidence_path.is_file() else None
        # New bytes get a new exact read-only release. Never overwrite the old approval.
        write_freeze(project)
        payload = json.loads(freeze_path.read_text(encoding="utf-8"))
        if payload["freeze_id"] != parent["freeze_id"]:
            payload["presentation_approval"] = {"round": revision["round_id"], "parent": parent["freeze_id"],
                "ancestors": [*parent.get("presentation_approval", {}).get("ancestors", []), parent["freeze_id"]],
                "prior_audit_context": parent.get("presentation_approval", {}).get("prior_audit_context") or context,
                "current_audit_context": sync_evidence(project)["audit_context_id"],
                "basis": "closed source-owned presentation revision; prior independent review is not relabelled"}
            atomic_json(freeze_path, payload)
