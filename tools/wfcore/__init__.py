"""medpaper workflow engine. Stdlib only, no third-party imports anywhere in this package."""

__all__ = ["cli", "gates", "paths", "registry", "state", "xlsxlite", "checks"]

# Installed bundles carry their own byte identities. This guards managed entrypoints;
# unrestricted host tools still require the stated study/maintenance scope boundary.
def _installed_engine_check():
    import json,os,sys
    from pathlib import Path
    from .engineintegrity import verify_engine
    root=Path(__file__).resolve().parents[2]
    project=Path(os.environ.get("MEDPAPER_PROJECT",root/"project"))
    state=project/".wf/state.json"
    try:
        required=json.loads(state.read_text(encoding="utf-8")).get("engine_integrity_required",False) if state.is_file() else False
        verify_engine(root,required)
    except (OSError,ValueError,TypeError) as exc:
        print("Engine integrity stop: "+str(exc),file=sys.stderr)
        raise SystemExit(3)


_installed_engine_check()
