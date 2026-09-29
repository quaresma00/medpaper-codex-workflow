"""Renewable evidence is not an authored scientific deliverable."""


def renewable(rel: str) -> bool:
    # Exact namespaces only: a user file named cache inside a manuscript is not exempt.
    rel = rel.replace("\\", "/")
    return (rel == "06_refs/verified.json" or rel.startswith((
        "06_refs/cache/", "08_submission/cache/", "08_submission/evidence/")))
