from __future__ import annotations

from typing import Any, Optional, List

from .endpoints import rest_path
from .errors import DbServiceError

REST_ACCEPT_JSON = "application/json"
REST_ACCEPT_BINARY = "application/octet-stream, application/json"


def _rest_accept(session) -> str:
    return REST_ACCEPT_BINARY if bool(getattr(session, "pykx_licensed", False)) else REST_ACCEPT_JSON


def create_table(
    session,
    *,
    table: str,
    description: Optional[str] = None,
    type: Optional[str] = None,
    blockSize: Optional[int] = None,
    prtnCol: Optional[str] = None,
    sortColsMem: Optional[List[str]] = None,
    sortColsOrd: Optional[List[str]] = None,
    sortColsDisk: Optional[List[str]] = None,
    primaryKeys: Optional[List[str]] = None,
    columns: List[dict],
) -> Any:
    payload = {"table": table, "columns": columns}
    if description is not None:
        payload["description"] = description
    if type is not None:
        payload["type"] = type
    if blockSize is not None:
        payload["blockSize"] = blockSize
    if prtnCol is not None:
        payload["prtnCol"] = prtnCol
    if sortColsMem is not None:
        payload["sortColsMem"] = sortColsMem
    if sortColsOrd is not None:
        payload["sortColsOrd"] = sortColsOrd
    if sortColsDisk is not None:
        payload["sortColsDisk"] = sortColsDisk
    if primaryKeys is not None:
        payload["primaryKeys"] = primaryKeys

    if session.mode == "rest":
        path = rest_path(session.options, "create_table", table=table)
        body = dict(payload)
        if "{table}" in (session.options.get("rest_paths", {}).get("create_table") or ""):
            body.pop("table", None)
        elif path.endswith(f"/{table}"):
            body.pop("table", None)
        return session._rest.request(
            "POST",
            path,
            json_body=body,
            accept=_rest_accept(session),
        )
    api = _lookup_qipc_api(session, "create_table")
    return session._qipc.request(api, args=payload)


def list_tables(session) -> Any:
    if session.mode == "rest":
        return session._rest.request("GET", rest_path(session.options, "list_tables"), accept=_rest_accept(session))
    return _qipc_call(session, "list_tables")


def describe_table(session, *, table: str) -> Any:
    if session.mode == "rest":
        path = rest_path(session.options, "describe_table", table=table)
        return session._rest.request("GET", path, accept=_rest_accept(session))
    api = _lookup_qipc_api(session, "describe_table")
    return session._qipc.request(api, args={"table": table})


def drop_table(session, *, table: str) -> Any:
    if session.mode == "rest":
        path = rest_path(session.options, "drop_table", table=table)
        return session._rest.request("DELETE", path, accept=_rest_accept(session))
    api = _lookup_qipc_api(session, "drop_table")
    return session._qipc.request(api, args={"table": table})


def _qipc_call(session, name: str, args: Optional[dict] = None) -> Any:
    api = _lookup_qipc_api(session, name)
    return session._qipc.request(api, args=args or {})


def _lookup_qipc_api(session, name: str) -> str:
    apis = session.options.get("qipc_apis", {})
    api = apis.get(name)
    if not api:
        raise DbServiceError(f"qIPC is not supported for '{name}'. Use REST mode for this call.")
    return api
