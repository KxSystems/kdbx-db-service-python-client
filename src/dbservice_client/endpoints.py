from __future__ import annotations

from typing import Dict, Optional

from .errors import DbServiceError


DEFAULT_REST_PATHS: Dict[str, str] = {
    # Query
    "query_simple": "/api/v0/query/simple",
    "query_sql": "/api/v0/query/sql",
    "query_q": "/api/v0/query/q",
    "query_preview": "/api/v0/query/preview",
    # Tables
    "list_tables": "/api/v0/tables",
    "describe_table": "/api/v0/tables/{table}",
    "create_table": "/api/v0/tables/{table}",
    "drop_table": "/api/v0/tables/{table}",
    # Imports
    "import_files": "/api/v0/imports/files",
    "import_data": "/api/v0/imports/data",
    "import_database": "/api/v0/imports/kdb",
    "get_import": "/api/v0/imports/{jobId}",
    "cancel_import": "/api/v0/imports/{jobId}",
    # Deletes
    "delete_rows": "/api/v0/deletes",
    "get_delete": "/api/v0/deletes/{jobId}",
    "cancel_delete": "/api/v0/deletes/{jobId}",
    # Configuration
    "export_assembly": "/api/v0/config/assembly",
}


def rest_path(options: dict, key: str, **kwargs: str) -> str:
    override = options.get("rest_paths", {}).get(key)
    path = override or DEFAULT_REST_PATHS[key]
    return path.format(**kwargs)


def assembly_params(session, assembly: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Build the query parameters that route a request to an assembly.

    The per-call `assembly` takes precedence over the session default. Returns None when
    neither is set, in which case the service routes to its sole configured assembly.
    """
    target = assembly if assembly is not None else getattr(session, "assembly", None)
    if target is None:
        return None
    if session.mode != "rest":
        raise DbServiceError("assembly is only supported in REST mode.")
    return {"assembly": target}
