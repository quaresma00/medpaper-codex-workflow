"""Opt-in local third-party reading snapshot; never a default archive or upload."""
import shutil
import stat
from . import reviewrounds
from .packagefreeze import _sha256

def export(project,scope,words):
    current=reviewrounds.inputs(project,scope)
    if scope=="package":
        from .packagefreeze import expected_files
        uploads=expected_files(project)
        current={rel:digest for rel,digest in current.items() if rel in uploads}
    else:
        from .readiness import load
        plan=load(project,"01_protocol/artifact_plan.json")
        human={"07_manuscript/full_manuscript.md","07_manuscript/supplementary_methods.md",
               "05_figures/legends.md","04_tables/table_captions.md","06_refs/refs.bib","06_refs/refs.ris"}
        human.update(e["file"] for group in ("main_figures","supp_figures","main_tables","supp_tables") for e in plan.get(group,[]))
        current={rel:digest for rel,digest in current.items() if rel in human}
    record=reviewrounds.latest(project,scope) or {}
    folder=project/".wf"/"external_review"/f"{scope}-{reviewrounds.now().replace(':','').replace('.','')}"
    folder.mkdir(parents=True,exist_ok=False)
    try:
        for rel,digest in current.items():
            destination=folder/rel; destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(project/rel,destination)
            if _sha256(destination)!=digest or _sha256(project/rel)!=digest: raise ValueError("Reading snapshot drifted while copying")
            destination.chmod(destination.stat().st_mode & ~stat.S_IWUSR)
        changes=record.get("changes",[])
        detail="\n".join(f"- {rel}: {why}" for rel,why in changes)
        if len(detail)>2500: detail="Changes are recorded in the workflow round; ask for the specific affected section.\n"+"\n".join(f"- {r}" for r,_ in changes)
        summary=folder/"变更说明.md"
        summary.write_text(f"# 第三方只读审阅版本\n\n用户请求：{words}\n\n轮次：{record.get('id','current')}；范围：{scope}。\n\n{detail or '本次为初始只读版本，无此前修订。'}\n\n此副本不是新的审阅通过或投稿确认。\n",encoding="utf-8")
        summary.chmod(summary.stat().st_mode & ~stat.S_IWUSR)
    except Exception:
        # Preserve partial evidence for diagnosis rather than deleting user material.
        raise
    return folder
