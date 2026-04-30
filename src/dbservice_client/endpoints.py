from __future__ import annotations

from typing import Dict


DEFAULT_REST_PATHS: Dict[str, str] = {
    # Query
    "query_simple": "/api/v0/query/simple",
    "query_sql": "/api/v0/query/sql",
    "query_q": "/api/v0/query/q",
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
}


def rest_path(options: dict, key: str, **kwargs: str) -> str:
    override = options.get("rest_paths", {}).get(key)
    path = override or DEFAULT_REST_PATHS[key]
    return path.format(**kwargs)
