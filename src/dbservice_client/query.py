from __future__ import annotations

from datetime import date as _date, datetime as _datetime

from typing import Any, Dict, Optional

from .endpoints import rest_path
from .errors import DbServiceError
from .utils import json_to_dataframe, parse_timestamp_like

ReturnAs = str  # "pykx" | "pandas" | "json"


def query_simple(
    session,
    *,
    table: str,
    startTS: Optional[Any] = None,
    endTS: Optional[Any] = None,
    inputTZ: Optional[str] = None,
    outputTZ: Optional[str] = None,
    outputTZCols: Optional[Any] = None,
    filter: Optional[Any] = None,
    groupBy: Optional[Any] = None,
    agg: Optional[Any] = None,
    fill: Optional[Any] = None,
    temporality: Optional[Any] = None,
    sortCols: Optional[Any] = None,
    limit: Optional[int] = None,
    return_as: Optional[ReturnAs] = None,
    unwrap: bool = True,
) -> Any:
    if return_as is None:
        if session.mode == "rest":
            return_as = "pykx" if bool(getattr(session, "pykx_licensed", False)) else "json"
        else:
            return_as = "pykx"
    if return_as not in ("pykx", "pandas", "json"):
        raise ValueError("return_as must be one of: 'pykx', 'pandas', 'json'")

    payload = {"table": table}
    if startTS is not None:
        payload["startTS"] = startTS
    if endTS is not None:
        payload["endTS"] = endTS
    if inputTZ is not None:
        payload["inputTZ"] = inputTZ
    if outputTZ is not None:
        payload["outputTZ"] = outputTZ
    if outputTZCols is not None:
        payload["outputTZCols"] = outputTZCols
    if filter is not None:
        payload["filter"] = filter
    if groupBy is not None:
        payload["groupBy"] = groupBy
    if agg is not None:
        payload["agg"] = agg
    if fill is not None:
        payload["fill"] = fill
    if temporality is not None:
        payload["temporality"] = temporality
    if sortCols is not None:
        payload["sortCols"] = sortCols
    if limit is not None:
        payload["limit"] = limit

    if session.mode == "rest":
        if "startTS" in payload:
            payload["startTS"] = _to_rest_timestamp(payload["startTS"])
        if "endTS" in payload:
            payload["endTS"] = _to_rest_timestamp(payload["endTS"])
        path = rest_path(session.options, "query_simple")
        if return_as == "pykx":
            return _rest_query_binary(session, path=path, payload=payload, unwrap=unwrap)
        resp = session._rest.request("POST", path, json_body=payload, accept="application/json")
        if not unwrap:
            return resp

        payload_part = resp.get("payload") if isinstance(resp, dict) else resp

        if return_as == "json":
            return payload_part
        if return_as == "pandas":
            try:
                import pandas as pd
            except Exception as e:
                raise DbServiceError("pandas is required for return_as='pandas'") from e
            return json_to_dataframe(pd, payload_part)
        raise DbServiceError("Unexpected return_as value")

    # qIPC
    try:
        import pykx as kx
    except Exception as e:
        raise DbServiceError("pykx is required for qipc mode. Install it to use qIPC.") from e

    args: Dict[str, Any] = dict(payload)
    args["table"] = kx.SymbolAtom(table)
    if startTS is not None:
        args["startTS"] = kx.toq(parse_timestamp_like(startTS))
    if endTS is not None:
        args["endTS"] = kx.toq(parse_timestamp_like(endTS))

    api = _lookup_qipc_api(session, "query_simple")
    res = session._qipc.request(api, args=args)
    header, table_obj = _split_qipc_response(res)
    converted = _convert_result(table_obj, return_as)

    if unwrap:
        return converted
    return {"header": header, "payload": converted}


def query_preview(
    session,
    *,
    table: str,
    startTS: Optional[Any] = None,
    endTS: Optional[Any] = None,
    limit: Optional[int] = None,
    return_as: Optional[ReturnAs] = None,
    unwrap: bool = True,
) -> Any:
    if return_as is None:
        if session.mode == "rest":
            return_as = "pykx" if bool(getattr(session, "pykx_licensed", False)) else "json"
        else:
            return_as = "pykx"
    if return_as not in ("pykx", "pandas", "json"):
        raise ValueError("return_as must be one of: 'pykx', 'pandas', 'json'")

    payload = {"table": table}
    if startTS is not None:
        payload["startTS"] = startTS
    if endTS is not None:
        payload["endTS"] = endTS
    if limit is not None:
        payload["limit"] = limit

    if session.mode == "rest":
        if "startTS" in payload:
            payload["startTS"] = _to_rest_timestamp(payload["startTS"])
        if "endTS" in payload:
            payload["endTS"] = _to_rest_timestamp(payload["endTS"])
        path = rest_path(session.options, "query_preview")
        if return_as == "pykx":
            return _rest_query_binary(session, path=path, payload=payload, unwrap=unwrap)
        resp = session._rest.request("POST", path, json_body=payload, accept="application/json")
        if not unwrap:
            return resp

        payload_part = resp.get("payload") if isinstance(resp, dict) else resp

        if return_as == "json":
            return payload_part
        if return_as == "pandas":
            try:
                import pandas as pd
            except Exception as e:
                raise DbServiceError("pandas is required for return_as='pandas'") from e
            return json_to_dataframe(pd, payload_part)
        raise DbServiceError("Unexpected return_as value")

    # qIPC
    try:
        import pykx as kx
    except Exception as e:
        raise DbServiceError("pykx is required for qipc mode. Install it to use qIPC.") from e

    args: Dict[str, Any] = dict(payload)
    args["table"] = kx.SymbolAtom(table)
    if startTS is not None:
        args["startTS"] = kx.toq(parse_timestamp_like(startTS))
    if endTS is not None:
        args["endTS"] = kx.toq(parse_timestamp_like(endTS))

    api = _lookup_qipc_api(session, "query_preview")
    res = session._qipc.request(api, args=args)
    header, table_obj = _split_qipc_response(res)
    converted = _convert_result(table_obj, return_as)

    if unwrap:
        return converted
    return {"header": header, "payload": converted}


def query_sql(
    session,
    query: str,
    return_as: Optional[ReturnAs] = None,
    unwrap: bool = True,
) -> Any:
    if return_as is None:
        if session.mode == "rest":
            return_as = "pykx" if bool(getattr(session, "pykx_licensed", False)) else "json"
        else:
            return_as = "pykx"
    if return_as not in ("pykx", "pandas", "json"):
        raise ValueError("return_as must be one of: 'pykx', 'pandas', 'json'")

    payload: Dict[str, Any] = {"query": query}

    if session.mode == "rest":
        path = rest_path(session.options, "query_sql")
        if return_as == "pykx":
            return _rest_query_binary(session, path=path, payload=payload, unwrap=unwrap)
        resp = session._rest.request("POST", path, json_body=payload, accept="application/json")

        if not unwrap:
            return resp

        payload_part = resp.get("payload") if isinstance(resp, dict) else resp

        if return_as == "json":
            return payload_part
        if return_as == "pandas":
            try:
                import pandas as pd
            except Exception as e:
                raise DbServiceError("pandas is required for return_as='pandas'") from e
            return json_to_dataframe(pd, payload_part)
        raise DbServiceError("Unexpected return_as value")

    api = _lookup_qipc_api(session, "query_sql")
    res = session._qipc.request(api, args=payload)
    header, table_obj = _split_qipc_response(res)
    converted = _convert_result(table_obj, return_as)

    if unwrap:
        return converted
    return {"header": header, "payload": converted}


def query_q(
    session,
    query: str,
    agg: Optional[str] = None,
    return_as: Optional[ReturnAs] = None,
    unwrap: bool = True,
) -> Any:
    if return_as is None:
        if session.mode == "rest":
            return_as = "pykx" if bool(getattr(session, "pykx_licensed", False)) else "json"
        else:
            return_as = "pykx"
    if return_as not in ("pykx", "pandas", "json"):
        raise ValueError("return_as must be one of: 'pykx', 'pandas', 'json'")

    payload: Dict[str, Any] = {"query": query}
    if agg is not None:
        payload["agg"] = agg

    if session.mode == "rest":
        path = rest_path(session.options, "query_q")
        if return_as == "pykx":
            return _rest_query_binary(session, path=path, payload=payload, unwrap=unwrap)
        resp = session._rest.request("POST", path, json_body=payload, accept="application/json")

        if not unwrap:
            return resp

        payload_part = resp.get("payload") if isinstance(resp, dict) else resp

        if return_as == "json":
            return payload_part
        if return_as == "pandas":
            try:
                import pandas as pd
            except Exception as e:
                raise DbServiceError("pandas is required for return_as='pandas'") from e
            return json_to_dataframe(pd, payload_part)
        raise DbServiceError("Unexpected return_as value")

    api = _lookup_qipc_api(session, "query_q")
    res = session._qipc.request(api, args=payload)
    header, table_obj = _split_qipc_response(res)
    converted = _convert_result(table_obj, return_as)

    if unwrap:
        return converted
    return {"header": header, "payload": converted}


def _split_qipc_response(res: Any) -> tuple[Any, Any]:
    # Deterministic unwrap for qIPC query shape: [header; payload].
    # If response does not match, return raw object as payload.
    try:
        return res[0], res[1]
    except Exception:
        return None, res


def _lookup_qipc_api(session, name: str) -> str:
    apis = session.options.get("qipc_apis", {})
    api = apis.get(name)
    if not api:
        raise DbServiceError(f"qIPC is not supported for '{name}'. Use REST mode for this call.")
    return api


def _convert_result(table_obj: Any, return_as: ReturnAs) -> Any:
    if return_as == "pykx":
        return table_obj
    try:
        pd_obj = table_obj.pd()
    except Exception as e:
        if return_as == "pandas":
            raise DbServiceError("Failed to convert result to pandas object") from e
        raise DbServiceError("Failed to convert result to JSON (pandas conversion failed)") from e

    # Some qIPC responses can arrive as a 2-element series: [header, payload].
    # In that case, use payload for downstream conversion.
    try:
        if hasattr(pd_obj, "iloc") and hasattr(pd_obj, "index") and len(pd_obj) >= 2:
            first = pd_obj.iloc[0]
            if isinstance(first, dict) and ("rc" in first or "api" in first):
                pd_obj = pd_obj.iloc[1]
    except Exception:
        pass

    if return_as == "pandas":
        return pd_obj

    # JSON conversion path: support both DataFrame and Series outputs from .pd()
    if hasattr(pd_obj, "to_dict"):
        if hasattr(pd_obj, "columns"):
            return _to_json_safe(pd_obj.to_dict(orient="records"))
        return _to_json_safe(pd_obj.to_dict())
    raise DbServiceError("Failed to convert result to JSON (unsupported pandas object)")


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception:
            return str(value)
    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return _to_json_safe(value.item())
        except Exception:
            pass
    return str(value)


def _rest_query_binary(session, *, path: str, payload: Dict[str, Any], unwrap: bool) -> Any:
    raw = session._rest.request(
        "POST",
        path,
        json_body=payload,
        accept="application/octet-stream",
        expect_json=False,
    )
    obj = _decode_octet_stream(raw)
    header, payload_obj = _split_qipc_response(obj)
    if unwrap:
        return payload_obj
    return {"header": header, "payload": payload_obj}


def _decode_octet_stream(raw: Any) -> Any:
    try:
        import pykx as kx
    except Exception as e:
        raise DbServiceError("pykx is required to decode application/octet-stream responses.") from e

    if not isinstance(raw, (bytes, bytearray)):
        raise DbServiceError("Expected binary response bytes for application/octet-stream.")

    if hasattr(kx, "deserialize"):
        try:
            return kx.deserialize(bytes(raw))
        except Exception:
            pass

    try:
        return kx.q("{-9!x}", bytes(raw))
    except Exception as e:
        raise DbServiceError("Failed to decode binary query response from REST.") from e


def _to_rest_timestamp(x: Any) -> Any:
    if isinstance(x, _datetime):
        return x.strftime("%Y.%m.%dD%H:%M:%S.%f")[:-3]
    if isinstance(x, _date):
        return x.strftime("%Y.%m.%d")
    return x
