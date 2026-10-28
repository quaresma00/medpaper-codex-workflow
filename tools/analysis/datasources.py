"""Read an authorized data reference without copying, extraction or writable links."""
from wfcore.paths import project_dir
from wfcore.datasources import resolve,open_readonly


def source_path(reference):
    """For readers requiring a filename. Read-only contract; not an OS sandbox."""
    return resolve(project_dir(),reference)


def open_data(reference,mode="rb",**kwargs):
    return open_readonly(project_dir(),reference,mode,**kwargs)
