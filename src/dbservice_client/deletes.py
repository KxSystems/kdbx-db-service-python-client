from __future__ import annotations

from datetime import date as _date, datetime as _datetime
from typing import Any, List, Optional

from .endpoints import assembly_params, rest_path
from .errors import DbServiceError

REST_ACCEPT_JSON = "application/json"
REST_ACCEPT_BINARY = "application/octet-stream, application/json"


def _rest_accept(session) -> str:
    return REST_ACCEPT_BINARY if bool(getattr(session, "pykx_licensed", False)) else REST_ACCEPT_JSON


def delete_rows(
    session,
    *,
    table: str,
    filter: List[Any],
    startTS: Optional[Any] = None,
    endTS: Optional[Any] = None,
    assembly: Optional[str] = None,
) -> Any:
    params = assembly_params(session, assembly)
    _check_filter(filter)

    body: dict = {"table": table, "filter": _check_filter_values(filter)}
    if startTS is not None:
        body["startTS"] = _to_delete_timestamp(startTS, "startTS")
    if endTS is not None:
        body["endTS"] = _to_delete_timestamp(endTS, "endTS")

    if session.mode == "rest":
        return session._rest.request(
            "POST",
            rest_path(session.options, "delete_rows"),
            json_body=body,
            params=params,
            accept=_rest_accept(session),
        )
    return _qipc_call(session, "delete_rows", args=body)


def get_delete(session, *, job_id: str, assembly: Optional[str] = None) -> Any:
    params = assembly_params(session, assembly)
    if session.mode == "rest":
        path = rest_path(session.options, "get_delete", jobId=job_id)
        return session._rest.request("GET", path, params=params, accept=_rest_accept(session))
    return _qipc_call(session, "get_delete", args={"sessionId": job_id})


def cancel_delete(session, *, job_id: str, assembly: Optional[str] = None) -> Any:
    params = assembly_params(session, assembly)
    if session.mode == "rest":
        path = rest_path(session.options, "cancel_delete", jobId=job_id)
        return session._rest.request("DELETE", path, params=params, accept=_rest_accept(session))
    return _qipc_call(session, "cancel_delete", args={"sessionId": job_id})


def _check_filter(filter: Any) -> None:
    """Check the filter is a list of clauses.

    The service requires `filter`, treating an explicit empty list as "every row" so that
    a filter left off by accident can never widen a delete. Each clause is a list whose
    first element is the operator - a leaf triple like ["=", "sym", "AAPL"], or a nested
    boolean like ["and", clause, clause].

    The slip worth naming is a single bare triple passed as the whole filter, which makes
    the clauses bare strings. The service rejects that as `badFilter` without saying why.
    """
    if filter is None:
        raise DbServiceError(
            "filter is required. Pass filter=[] to delete every row in the time window."
        )
    if not isinstance(filter, (list, tuple)):
        raise DbServiceError(
            f"filter must be a list of clauses, got {type(filter).__name__}. "
            "Pass filter=[] to delete every row in the time window."
        )
    for i, clause in enumerate(filter):
        if not isinstance(clause, (list, tuple)) or not clause:
            raise DbServiceError(
                f"filter[{i}] must be a non-empty list, got {type(clause).__name__}. "
                "filter takes a list OF clauses, so a single triple must be wrapped: "
                'filter=[["=", "sym", "AAPL"]], not filter=["=", "sym", "AAPL"].'
            )
        if not isinstance(clause[0], str):
            raise DbServiceError(
                f"filter[{i}][0] must be the operator as a string, got "
                f"{type(clause[0]).__name__}."
            )


def _check_filter_values(filter: Any, _path: str = "filter") -> Any:
    """Copy a filter, refusing any timezone-aware datetime found in it.

    The rule the deletion window is held to, applied to filter values too. A value is cast
    server-side to its column's type, which carries no offset, so an aware datetime would
    either null out and match nothing or be read as wall-clock and match rows other than
    the ones named.
    """
    out = []
    for i, item in enumerate(filter):
        where = f"{_path}[{i}]"
        if isinstance(item, (list, tuple)):
            out.append(_check_filter_values(item, where))
        elif _is_aware(item):
            raise DbServiceError(
                f"{where} must be a timezone-naive datetime. A filter value is matched as "
                "wall-clock time, so the offset cannot be honoured. Convert explicitly "
                "first, for example value.astimezone(timezone.utc).replace(tzinfo=None) "
                "to match on a UTC instant, or value.replace(tzinfo=None) to keep the "
                "local reading."
            )
        else:
            out.append(item)
    return out


def _to_delete_timestamp(value: Any, field: str) -> Any:
    """Render a deletion-window bound as a full-precision q timestamp literal.

    Deliberately stricter than the query-side conversion in query.py. A delete cannot be
    undone, so a bound this cannot represent exactly is refused rather than approximated:

      - An aware datetime is refused. DeleteRequest has no `inputTZ` field, so the service
        reads the literal as wall-clock; dropping the offset would silently shift the
        window and delete rows the caller never named.
      - The whole microsecond field is kept, zero-padded to nanoseconds. Truncating to
        milliseconds - as the query path does - would round an inclusive `startTS` down
        and widen the window.
    """
    if isinstance(value, _datetime):
        if _is_aware(value):
            raise DbServiceError(
                f"{field} must be a timezone-naive datetime. The delete API reads the "
                "window as wall-clock time and has no inputTZ field, so the offset "
                "cannot be honoured. Convert explicitly first, for example "
                f"{field}.astimezone(timezone.utc).replace(tzinfo=None) to delete on a "
                f"UTC window, or {field}.replace(tzinfo=None) to keep the local reading."
            )
        return f"{value.strftime('%Y.%m.%dD%H:%M:%S.%f')}000"
    if isinstance(value, _date):
        return value.strftime("%Y.%m.%d")
    return value


def _is_aware(value: Any) -> bool:
    return (
        isinstance(value, _datetime)
        and value.tzinfo is not None
        and value.tzinfo.utcoffset(value) is not None
    )


def _qipc_call(session, name: str, args: Optional[dict] = None) -> Any:
    api = _lookup_qipc_api(session, name)
    return session._qipc.request(api, args=args or {})


def _lookup_qipc_api(session, name: str) -> str:
    apis = session.options.get("qipc_apis", {})
    api = apis.get(name)
    if not api:
        raise DbServiceError(f"qIPC is not supported for '{name}'. Use REST mode for this call.")
    return api
