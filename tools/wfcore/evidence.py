"""Renewable evidence is not an authored scientific deliverable."""

from pathlib import Path
import re


def reference_evidence(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return rel == "06_refs/verified.json" or rel.startswith("06_refs/cache/")


def renewable(rel: str) -> bool:
    # Exact namespaces only: a user file named cache inside a manuscript is not exempt.
    rel = rel.replace("\\", "/")
    return (rel == "06_refs/verified.json" or rel.startswith((
        "06_refs/cache/", "08_submission/cache/", "08_submission/evidence/")))


def reference_renewal_problems(project: Path, baseline: dict, current: dict) -> list[str]:
    """Separate new retrieval events from changed reference science.

    Namespace membership alone never proves safe renewal. New EFetch XML must
    describe only unchanged, source-proven library records. The current verifier
    receipt is reparsed/hash-checked by the existing provenance implementation.
    This comparison does not grant network provenance or extend proof freshness;
    actual live/local gates still run at their ordinary checkpoints.
    """
    changed = sorted(rel for rel in set(baseline) | set(current)
                     if reference_evidence(rel) and baseline.get(rel) != current.get(rel))
    if not changed:
        return []
    from .packagefreeze import _safe_path, _sha256
    from . import refproof
    import json
    from xml.etree import ElementTree as ET

    library_rel = "06_refs/library.json"
    library = project / library_rel
    if (not baseline.get(library_rel) or not library.is_file()
            or baseline[library_rel].casefold() != _sha256(library).casefold()):
        return ["reference evidence renewal requires the unchanged baseline library; use a source-owned reference revision"]
    try:
        ok, failures, _ = refproof.validate_local_proof(project)
        if not ok:
            return ["reference evidence renewal has invalid current provenance: " + "; ".join(failures[:4])]
        entries = json.loads(library.read_text(encoding="utf-8"))["entries"]
        by_pmid = {str(row.get("pmid", "")): row for row in entries}
        if len(by_pmid) != len(entries):
            return ["reference evidence renewal has duplicate library PMIDs"]
        def identity(row):
            result = refproof.canonical_source(row)
            result["abstract"] = refproof.normalized_abstract(result["abstract"])
            return result
        expected = {pmid: identity(row) for pmid, row in by_pmid.items()}
        problems = []
        for rel in changed:
            if rel == "06_refs/verified.json":
                # validate_local_proof above validates this exact current receipt.
                continue
            if rel in baseline:
                problems.append(f"{rel}: existing source cache changed or disappeared; renewal must preserve prior raw evidence")
                continue
            if not re.fullmatch(r"06_refs/cache/(?:gate|verify)_efetch_pubmed_[A-Za-z0-9_.-]+\.xml", rel):
                problems.append(f"{rel}: not a new managed PubMed verification event; retain source-owned review")
                continue
            _, path = _safe_path(project, rel)
            if not path.is_file():
                problems.append(f"{rel}: renewal payload is missing")
                continue
            raw = path.read_bytes()
            records = refproof.parse_pubmed_payload(raw)
            root = ET.fromstring(raw)
            count = sum(1 for node in root.iter()
                        if node.tag in {"PubmedArticle", "PubmedBookArticle"})
            if not records or count != len(records):
                problems.append(f"{rel}: empty/duplicate/unidentified article records in renewal payload")
                continue
            for pmid, row in records.items():
                if pmid not in expected or identity(row) != expected[pmid]:
                    problems.append(f"{rel}: PMID {pmid} identity or consumed source metadata/content changed")
        return problems
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ET.ParseError) as exc:
        return [f"cannot establish unchanged reference evidence: {exc}"]
