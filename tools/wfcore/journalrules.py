"""Typed, article-specific requirements; never infer a cap from a number in guide prose."""
from __future__ import annotations

from .readiness import load


def limits(project):
    requirements = load(project,"08_submission/submission_requirements.json")
    article = requirements.get("article_type")
    if not isinstance(article,str) or not article.strip():
        raise ValueError("Set the chosen journal's actual article_type")
    word = requirements.get("word_count",{})
    if not word.get("source"):
        raise ValueError("word_count needs the official rule source; a silent guide uses explicit null caps")
    legacy = {"main":word.get("limit"),"abstract":word.get("abstract_limit"),"references":word.get("reference_limit")}
    parsed = {}
    for field, value in legacy.items():
        row = requirements.get("limits",{}).get(field)
        if row is None:
            row = {"status":"required" if value is not None else "unspecified", "value":value,
                   "source":word["source"],"article_type":article}
        if not isinstance(row,dict) or row.get("status") not in {"required","allowed","recommended","unspecified"}:
            raise ValueError(f"{field}: invalid structured requirement status")
        if row.get("article_type",article) != article or not row.get("source"):
            raise ValueError(f"{field}: wrong article type or missing official source")
        value = row.get("value")
        if row["status"] == "unspecified":
            if value is not None:
                raise ValueError(f"{field}: unspecified limit must be null")
        elif isinstance(value,bool) or not isinstance(value,int) or value <= 0:
            raise ValueError(f"{field}: limit must be a positive integer, not an inferred prose number")
        parsed[field] = row
    return requirements,parsed


def compare(counts, rules):
    return [f"{field}: {counts[field]} exceeds explicit {row['value']} limit"
            for field,row in rules.items() if row["status"] == "required" and row["value"] is not None
            and counts.get(field) is not None and counts[field] > row["value"]]


def display_limits(project):
    requirements = load(project, "08_submission/submission_requirements.json")
    article = requirements.get("article_type")
    parsed = {}
    for field, row in requirements.get("display_limits", {}).items():
        if field not in {"main_figures", "main_tables", "main_display_items", "supp_figures", "supp_tables"}:
            raise ValueError(f"Unknown journal display-limit field: {field}")
        if (not isinstance(row, dict) or row.get("status") not in {"required", "allowed", "recommended", "unspecified"}
                or not row.get("source") or not article or row.get("article_type", article) != article):
            raise ValueError(f"{field}: source/status/selected article type required")
        value = row.get("value")
        if row["status"] == "unspecified":
            if value is not None: raise ValueError(f"{field}: unspecified cap must be null")
        elif type(value) is not int or value < 0:
            raise ValueError(f"{field}: explicit nonnegative integer cap required")
        parsed[field] = row
    return parsed
