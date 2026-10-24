"""Only an explicit article-specific official rule makes a legend cap mandatory."""
import json

def check_limit(ctx):
    # A saved journal profile must not constrain a journal-independent master revision.
    return legend_limit(ctx.project) if ctx.stage.id.startswith(("S20_","S21_","S22_","S23_","S24_","S25_")) else None

def legend_limit(project):
    path=project/"08_submission/submission_requirements.json"
    if not path.is_file(): return None
    data=json.loads(path.read_text(encoding="utf-8")); row=data.get("figure_legend_words",{})
    if not row: return None
    if (row.get("status") not in {"required","recommended","allowed","unspecified"} or not row.get("source")
            or not data.get("article_type") or row.get("article_type",data["article_type"])!=data["article_type"]):
        raise ValueError("Legend rule needs official source/status/selected article type")
    if row["status"]=="unspecified":
        if row.get("value") is not None: raise ValueError("Unspecified legend cap must be null")
        return None
    if type(row.get("value")) is not int or row["value"]<1: raise ValueError("Legend cap must be positive")
    return row["value"] if row["status"]=="required" else None
