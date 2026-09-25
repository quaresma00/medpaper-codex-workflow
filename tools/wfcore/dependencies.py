"""File dependency closure for targeted rebuilds, independent of stage numbering."""
from __future__ import annotations

import json
from pathlib import Path


def closure(project: Path, changed: list[str]) -> list[str]:
    edges: dict[str, set[str]] = {}

    def link(source, output):
        if isinstance(source, str) and isinstance(output, str) and source != output:
            edges.setdefault(source.replace("\\", "/"), set()).add(output.replace("\\", "/"))

    def read(rel):
        path = project / rel
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    changed = [x.replace("\\", "/") for x in changed]
    analysis_code = [p.relative_to(project).as_posix() for p in
                     (project / "03_analysis/code").rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    results = list((project / "03_analysis/results").glob("*.json"))
    # Legacy results may not declare precise data inputs. Missing provenance must widen
    # scientific revalidation, never incorrectly certify that no consumers changed.
    for source in changed:
        if (source.startswith("02_data/") or source in {
                "01_protocol/protocol_v1.md", "01_protocol/protocol_final.md",
                "01_protocol/analysis_contract.json"}):
            for output in [*analysis_code, *(p.relative_to(project).as_posix() for p in results)]:
                link(source, output)

    plan = read("01_protocol/artifact_plan.json")
    for group in ("main_figures", "supp_figures", "main_tables", "supp_tables"):
        for entry in plan.get(group, []):
            outputs = [entry.get(key) for key in ("file", "tiff", "pdf") if entry.get(key)]
            for source in [*entry.get("source_results", []), entry.get("script")]:
                for output in outputs:
                    link(source, output)
    producer_scripts = set()
    for path in results:
        rel = path.relative_to(project).as_posix()
        link(rel, "01_protocol/study_facts.json")
        for destination in ("07_manuscript/methods.md", "07_manuscript/results.md",
                            "07_manuscript/abstract.md", "07_manuscript/discussion.md"):
            link(rel, destination)
        info = read(rel)
        if not isinstance(info, dict):
            continue
        for key in ("script", "built_by"):
            link(info.get(key), rel)
            if isinstance(info.get(key), str):
                producer_scripts.add(info[key].replace("\\", "/"))
        for source in info.get("source_files", []):
            link(source, rel)
    for source in analysis_code:
        # Unmapped helper/library edits can affect any result. Declared producer paths
        # have narrower edges above; an unknown helper gets a conservative fallback.
        if source not in producer_scripts:
            for result in results:
                link(source, result.relative_to(project).as_posix())
    for rel in ("title", "abstract", "keywords", "methods", "results", "introduction", "discussion", "statements"):
        link(f"07_manuscript/{rel}.md", "07_manuscript/full_manuscript.md")
    link("05_figures/legends.md", "07_manuscript/full_manuscript.md")
    link("05_figures/legends.md", "08_submission/integration/figure_legends.md")
    link("04_tables/table_captions.md", "08_submission/integration/table_captions.md")
    link("07_manuscript/statements.md", "08_submission/integration/statements.md")
    for name in ("full_manuscript.md", "supplementary_methods.md"):
        link(f"07_manuscript/{name}", f"08_submission/integration/{name}")
    link("00_input/author_info.json", "08_submission/integration/title_page.md")
    link("00_input/author_info.json", "08_submission/integration/statements.md")
    link("00_input/author_info.json", "08_submission/cover_letter.md")
    link("08_submission/integration/statements.md", "08_submission/integration/full_manuscript.md")
    link("08_submission/integration/figure_legends.md", "08_submission/integration/full_manuscript.md")
    link("06_refs/library.json", "06_refs/refs.bib")
    link("06_refs/library.json", "06_refs/refs.ris")
    role_sources = {
        "manuscript": ["08_submission/integration/full_manuscript.md", "06_refs/refs.bib"],
        "title_page": ["08_submission/integration/title_page.md"],
        "cover_letter": ["08_submission/cover_letter.md"],
        "supplementary_methods": ["08_submission/integration/supplementary_methods.md", "06_refs/refs.bib"],
        "supplementary": ["08_submission/integration/supplementary_methods.md", "06_refs/refs.bib"],
        "statements": ["08_submission/integration/statements.md"],
        "figure_legends": ["08_submission/integration/figure_legends.md"],
    }
    for item in read("08_submission/bundle/manifest.json").get("items", []):
        sources = item.get("source_files", role_sources.get(item.get("role"), []))
        for source in sources:
            link(source, item.get("file"))
        if str(item.get("file", "")).endswith(".docx"):
            link("08_submission/docx_style.json", item["file"])
        if item.get("role") == "manuscript":
            link(item["file"], "08_submission/portal_fields.json")
    for source in ("00_input/author_info.json", "08_submission/submission_requirements.json",
                   "08_submission/bundle/manifest.json"):
        link(source, "08_submission/portal_fields.json")
    seen = set(x.replace("\\", "/") for x in changed)
    pending = list(seen)
    while pending:
        for dependent in edges.get(pending.pop(), set()):
            if dependent not in seen:
                seen.add(dependent)
                pending.append(dependent)
    return sorted(seen)


def guard_build(project: Path) -> None:
    state = project / ".wf/state.json"
    if not state.exists():
        return
    active = json.loads(state.read_text(encoding="utf-8")).get("active_revision_round")
    if active:
        payload = json.loads((state.parent / "revisions" / f"{active}.json").read_text(encoding="utf-8"))
        if payload.get("status") == "collecting":
            raise ValueError("feedback is still being collected; seal the batch before expensive builds")
