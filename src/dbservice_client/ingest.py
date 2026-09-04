from __future__ import annotations

import datetime as _dt
import math
import re
from typing import Any, Optional, List

from .endpoints import assembly_params, rest_path
from .errors import DbServiceError

REST_ACCEPT_JSON = "application/json"
REST_ACCEPT_BINARY = "application/octet-stream, application/json"


def _rest_accept(session) -> str:
    return REST_ACCEPT_BINARY if bool(getattr(session, "pykx_licensed", False)) else REST_ACCEPT_JSON

try:
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - optional at runtime
    _np = None

try:
    import pandas as _pd  # type: ignore
except Exception:  # pragma: no cover - optional at runtime
    _pd = None


def import_files(
    session,
    *,
    table: str,
    path: str,
    format: Optional[str] = None,
    delimiter: Optional[str] = None,
    decimal: Optional[str] = None,
    createTable: Optional[bool] = None,
    header: Optional[List[str]] = None,
    headerRowIndex: Optional[int] = None,
    include: Optional[List[str]] = None,
    types: Optional[str] = None,
    postparse: Optional[dict[str, str]] = None,
    assembly: Optional[str] = None,
) -> Any:
    params = assembly_params(session, assembly)
    body = {"table": table, "path": path}
    if format is not None:
        body["format"] = format
    if delimiter is not None:
        body["delimiter"] = delimiter
    if decimal is not None:
        body["decimal"] = decimal
    if createTable is not None:
        body["createTable"] = createTable
    if header is not None:
        body["header"] = header
    if headerRowIndex is not None:
        body["headerRowIndex"] = headerRowIndex
    if include is not None:
        body["include"] = include
    if types is not None:
        body["types"] = types
    if postparse is not None:
        body["postparse"] = postparse
    if session.mode == "rest":
        return session._rest.request(
            "POST",
            rest_path(session.options, "import_files"),
            json_body=body,
            params=params,
            accept=_rest_accept(session),
        )
    return _qipc_call(session, "import_files", args=body)


def import_data(
    session,
    *,
    table: str,
    data: Any,
    createTable: Optional[bool] = None,
    columnNames: Optional[List[str]] = None,
    types: Optional[str] = None,
    insert_as: str = "auto",
    transport: str = "auto",
    assembly: Optional[str] = None,
) -> Any:
    params = assembly_params(session, assembly)
    if transport not in ("auto", "json", "binary"):
        raise DbServiceError("transport must be one of: 'auto', 'json', 'binary'")
    if transport == "auto":
        transport = "binary" if _is_table_like(data) else "json"

    if session.mode == "rest" and transport == "binary":
        try:
            body = _build_binary_import_data_payload(
                table=table,
                data=data,
                createTable=createTable,
                columnNames=columnNames,
                types=types,
                insert_as=insert_as,
            )
            raw = _encode_binary_payload(body)
            return session._rest.request(
                "POST",
                rest_path(session.options, "import_data"),
                body=raw,
                params=params,
                content_type="application/octet-stream",
                accept=_rest_accept(session),
            )
        except DbServiceError:
            # Best-effort fallback so default binary mode does not break
            # unlicensed/non-PyKX environments.
            transport = "json"

    normalized_data, normalized_column_names = _normalize_insert_data(data, columnNames, insert_as)
    final_column_names = columnNames or normalized_column_names
    if final_column_names is None and normalized_data and isinstance(normalized_data[0], dict):
        # For object-shaped payloads, infer column order from first record when not provided.
        final_column_names = list(normalized_data[0].keys())
    body = {"table": table, "data": normalized_data}
    inferred_column_types = None
    if createTable:
        if not types:
            if final_column_names:
                inferred_column_types = _infer_column_types(
                    source_data=data,
                    column_names=final_column_names,
                    normalized_data=normalized_data,
                )

    if createTable is not None:
        body["createTable"] = createTable
    if final_column_names is not None:
        body["columnNames"] = final_column_names
    if types is not None:
        body["types"] = types
    elif inferred_column_types is not None:
        body["types"] = inferred_column_types
    if session.mode == "rest":
        return session._rest.request(
            "POST",
            rest_path(session.options, "import_data"),
            json_body=body,
            params=params,
            accept=_rest_accept(session),
        )
    return _qipc_call(session, "import_data", args=body)


def import_database(
    session,
    *,
    path: str,
    table: Optional[str] = None,
    assembly: Optional[str] = None,
) -> Any:
    params = assembly_params(session, assembly)
    body = {"path": path}
    if table is not None:
        body["table"] = table
    if session.mode == "rest":
        return session._rest.request(
            "POST",
            rest_path(session.options, "import_database"),
            json_body=body,
            params=params,
            accept=_rest_accept(session),
        )
    return _qipc_call(session, "import_database", args=body)


def get_import(session, *, job_id: str, assembly: Optional[str] = None) -> Any:
    params = assembly_params(session, assembly)
    if session.mode == "rest":
        path = rest_path(session.options, "get_import", jobId=job_id)
        return session._rest.request("GET", path, params=params, accept=_rest_accept(session))
    return _qipc_call(session, "get_import", args={"sessionId": job_id})


def cancel_import(session, *, job_id: str, assembly: Optional[str] = None) -> Any:
    params = assembly_params(session, assembly)
    if session.mode == "rest":
        path = rest_path(session.options, "cancel_import", jobId=job_id)
        return session._rest.request("DELETE", path, params=params, accept=_rest_accept(session))
    return _qipc_call(session, "cancel_import", args={"sessionId": job_id})


def _qipc_call(session, name: str, args: Optional[dict] = None) -> Any:
    api = _lookup_qipc_api(session, name)
    return session._qipc.request(api, args=args or {})


def _lookup_qipc_api(session, name: str) -> str:
    apis = session.options.get("qipc_apis", {})
    api = apis.get(name)
    if not api:
        raise DbServiceError(f"qIPC is not supported for '{name}'. Use REST mode for this call.")
    return api


def _encode_binary_payload(payload: dict) -> bytes:
    try:
        import pykx as kx
    except Exception as e:
        raise DbServiceError("pykx is required for transport='binary'.") from e

    try:
        kobj = kx.toq(payload, strings_as_char=True)
        raw = kx.serialize(kobj)
        return bytes(raw)
    except Exception as e:
        raise DbServiceError("Failed to serialize import_data payload as binary.") from e


def _build_binary_import_data_payload(
    *,
    table: str,
    data: Any,
    createTable: Optional[bool],
    columnNames: Optional[List[str]],
    types: Optional[str],
    insert_as: str,
) -> dict:
    body = {"table": table}

    # For binary transport, keep table-like inputs in columnar form when possible.
    # This avoids forcing table inputs through row-oriented Python normalization first.
    if _is_pandas_like(data):
        # Keep pandas table-like inputs in native form for binary transport.
        # This avoids forcing an intermediate columnar-dict shape.
        data_payload = data
    elif _is_pykx_table_like(data):
        # Keep PyKX table-like inputs in native form for binary transport.
        # This avoids an unnecessary PyKX -> pandas conversion.
        data_payload = data
    else:
        # Non-table-like payloads keep existing behavior.
        normalized_data, normalized_column_names = _normalize_insert_data(data, columnNames, insert_as)
        data_payload = normalized_data
        if columnNames is None and normalized_column_names is not None:
            columnNames = normalized_column_names

    body["data"] = data_payload

    if createTable is not None:
        body["createTable"] = createTable
    if columnNames is not None:
        body["columnNames"] = columnNames
    if types is not None:
        body["types"] = types
    return body


def _is_table_like(data: Any) -> bool:
    return _is_pandas_like(data) or _is_pykx_table_like(data)


def _is_pandas_like(data: Any) -> bool:
    return _pd is not None and isinstance(data, _pd.DataFrame)


def _is_pykx_table_like(data: Any) -> bool:
    pykx_table_names = {"Table", "KeyedTable", "SplayedTable", "PartitionedTable"}
    return any(
        base.__module__.startswith("pykx.") and base.__name__ in pykx_table_names
        for base in type(data).__mro__
    )


def _infer_column_types(source_data: Any, column_names: List[str], normalized_data: list) -> str:
    # Prefer native pandas dtype inference when available.
    if hasattr(source_data, "columns") and hasattr(source_data, "dtypes"):
        try:
            return "".join(_infer_from_pandas_column(source_data[col]) for col in column_names)
        except Exception:
            pass

    # PyKX table fallback via pandas conversion.
    if hasattr(source_data, "pd") and callable(getattr(source_data, "pd")):
        try:
            pdf = source_data.pd()
            return "".join(_infer_from_pandas_column(pdf[col]) for col in column_names)
        except Exception:
            pass

    # Generic object/row fallback using observed values.
    return "".join(_infer_col_type_from_values(_extract_values_for_col(source_data, normalized_data, column_names, c)) for c in column_names)


def _infer_from_pandas_column(series: Any) -> str:
    dtype = getattr(series, "dtype", None)
    kind = getattr(dtype, "kind", None)
    if kind == "b":
        return "b"
    if kind in ("i", "u"):
        return "j"
    if kind == "f":
        return "f"
    if kind == "M":
        return "p"
    if kind == "m":
        return "n"

    # Object dtype: inspect values.
    try:
        values = series.tolist()
    except Exception:
        values = []
    return _infer_col_type_from_values(values)


def _extract_values_for_col(source_data: Any, normalized_data: list, column_names: List[str], col: str) -> list:
    col_idx = column_names.index(col)

    # list[dict]
    if isinstance(source_data, list) and source_data and isinstance(source_data[0], dict):
        return [row.get(col) for row in source_data]

    # list[list/tuple]
    if isinstance(source_data, list) and source_data and isinstance(source_data[0], (list, tuple)):
        return [row[col_idx] if len(row) > col_idx else None for row in source_data]

    # Fallback to normalized payload shape
    if normalized_data and isinstance(normalized_data[0], dict):
        return [row.get(col) for row in normalized_data]
    if normalized_data and isinstance(normalized_data[0], list):
        return [row[col_idx] if len(row) > col_idx else None for row in normalized_data]
    return []


def _infer_col_type_from_values(values: list) -> str:
    for v in values:
        if v is None or _is_null_like(v):
            continue
        return _infer_scalar_type(v)
    # If no non-null sample exists, default to string-like.
    return "C"


def _infer_scalar_type(v: Any) -> str:
    if isinstance(v, bool):
        return "b"
    if isinstance(v, int) and not isinstance(v, bool):
        return "j"
    if isinstance(v, float):
        return "f"
    if isinstance(v, _dt.datetime):
        return "p"
    if isinstance(v, _dt.date):
        return "d"
    if isinstance(v, _dt.time):
        return "t"
    if isinstance(v, _dt.timedelta):
        return "n"

    if _pd is not None:
        if isinstance(v, _pd.Timestamp):
            return "p"
        if isinstance(v, _pd.Timedelta):
            return "n"

    if _np is not None:
        if isinstance(v, _np.datetime64):
            return "p"
        if isinstance(v, _np.timedelta64):
            return "n"
        if isinstance(v, (_np.integer,)):
            return "j"
        if isinstance(v, (_np.floating,)):
            return "f"
        if isinstance(v, (_np.bool_,)):
            return "b"

    if isinstance(v, str):
        # Heuristic for common temporal text patterns.
        if re.fullmatch(r"\d{4}[-.]\d{2}[-.]\d{2}", v):
            return "d"
        if re.fullmatch(r"\d{2}:\d{2}:\d{2}(?:\.\d+)?", v):
            return "t"
        if re.fullmatch(r"\d{4}[-.]\d{2}[-.]\d{2}[T D]\d{2}:\d{2}:\d{2}(?:\.\d+)?", v):
            return "p"
        if re.fullmatch(r"-?\d+D\d{2}:\d{2}:\d{2}\.\d{1,9}", v):
            return "n"
        return "C"

    return "C"


def _normalize_insert_data(
    data: Any,
    column_names: Optional[List[str]],
    insert_as: str,
) -> tuple[list, Optional[List[str]]]:
    if insert_as not in ("auto", "rows", "objects"):
        raise DbServiceError("insert_as must be one of: 'auto', 'rows', or 'objects'")

    # pandas DataFrame
    if hasattr(data, "to_dict") and hasattr(data, "columns"):
        try:
            if insert_as == "objects":
                records = data.to_dict(orient="records")
                return _normalize_records(records), column_names
            cols = list(data.columns)
            rows = data.values.tolist()
            return _normalize_rows(rows), column_names or cols
        except Exception as e:
            raise DbServiceError("Failed to normalize pandas input for import_data") from e

    # PyKX table (or compatible object with .pd())
    if hasattr(data, "pd") and callable(getattr(data, "pd")):
        try:
            records, cols = _pykx_to_records(data)
            if insert_as == "objects":
                return _normalize_records(records), (column_names or cols)
            rows = [[row.get(col) for col in cols] for row in records]
            return _normalize_rows(rows), (column_names or cols)
        except Exception as e:
            raise DbServiceError("Failed to normalize PyKX input for import_data") from e

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        raise DbServiceError("data must be a list, pandas DataFrame, PyKX table, or row dict")

    if not data:
        return data, column_names

    first = data[0]
    is_objects = isinstance(first, dict)

    if insert_as == "auto":
        if is_objects:
            return _normalize_records(data), (column_names or list(first.keys()))
        return _normalize_rows(data), column_names

    if insert_as == "objects":
        if is_objects:
            return _normalize_records(data), column_names
        cols = column_names
        if not cols:
            raise DbServiceError("columnNames is required when insert_as='objects' and data is row arrays")
        records = [dict(zip(cols, row)) for row in data]
        return _normalize_records(records), cols

    # insert_as == "rows"
    if not is_objects:
        return _normalize_rows(data), column_names

    cols = column_names or list(first.keys())
    rows = [[row.get(col) for col in cols] for row in data]
    return _normalize_rows(rows), cols


def _normalize_rows(rows: list) -> list:
    normalized = []
    for r_idx, row in enumerate(rows):
        if not isinstance(row, (list, tuple)):
            raise DbServiceError(f"rows payload must contain row arrays; got {type(row).__name__} at index {r_idx}")
        norm_row = [_normalize_cell_value(v, f"row {r_idx}, col {c_idx}") for c_idx, v in enumerate(row)]
        normalized.append(norm_row)
    return normalized


def _normalize_records(records: list) -> list:
    normalized = []
    for r_idx, row in enumerate(records):
        if not isinstance(row, dict):
            raise DbServiceError(f"objects payload must contain row objects; got {type(row).__name__} at index {r_idx}")
        norm_row = {k: _normalize_cell_value(v, f"row {r_idx}, field '{k}'") for k, v in row.items()}
        normalized.append(norm_row)
    return normalized


def _normalize_cell_value(value: Any, where: str) -> Any:
    # Null-like values
    if value is None:
        return None
    if _is_null_like(value):
        return None

    # Fail fast for nested containers / array cells to keep ingest shape explicit.
    if isinstance(value, (list, tuple, dict)):
        raise DbServiceError(f"Unsupported nested value at {where}. Use scalar values for ingest cells.")
    if _np is not None and isinstance(value, _np.ndarray):
        raise DbServiceError(f"Unsupported numpy array cell at {where}. Flatten or stringify before ingest.")

    # datetime / date / time / timedelta mappings
    if isinstance(value, _dt.datetime):
        return value.isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, _dt.time):
        return value.isoformat()
    if isinstance(value, _dt.timedelta):
        return _timedelta_to_timespan(value)

    # pandas datetime/timedelta scalars
    if _pd is not None:
        if isinstance(value, _pd.Timestamp):
            return value.isoformat()
        if isinstance(value, _pd.Timedelta):
            return _timedelta_to_timespan(value.to_pytimedelta())

    # numpy datetime/timedelta scalars
    if _np is not None:
        if isinstance(value, _np.datetime64):
            # Keep wire format as ISO-like datetime string.
            return str(value).replace("T", " ")
        if isinstance(value, _np.timedelta64):
            ns = int(value / _np.timedelta64(1, "ns"))
            return _ns_to_timespan(ns)

    return value


def _pykx_to_records(obj: Any) -> tuple[list[dict], list[str]]:
    # Prefer direct Python conversion from PyKX to avoid intermediate pandas objects.
    py_obj = obj.py() if hasattr(obj, "py") and callable(getattr(obj, "py")) else None
    if py_obj is None:
        raise DbServiceError("PyKX object does not expose a Python conversion method.")

    if isinstance(py_obj, dict):
        cols = [str(c) for c in py_obj.keys()]
        col_vals = [list(v) for v in py_obj.values()]
        row_count = len(col_vals[0]) if col_vals else 0
        rows = []
        for i in range(row_count):
            rows.append({cols[j]: col_vals[j][i] for j in range(len(cols))})
        return rows, cols

    if isinstance(py_obj, list):
        if not py_obj:
            return [], []
        if isinstance(py_obj[0], dict):
            cols = [str(c) for c in py_obj[0].keys()]
            return py_obj, cols
        raise DbServiceError("Unsupported PyKX list shape for table conversion.")

    raise DbServiceError("Unsupported PyKX conversion output for table normalization.")


def _is_null_like(value: Any) -> bool:
    if _pd is not None:
        try:
            if _pd.isna(value):
                return True
        except Exception:
            pass
    if isinstance(value, float):
        try:
            return math.isnan(value)
        except Exception:
            return False
    return False


def _timedelta_to_timespan(td: _dt.timedelta) -> str:
    # q-style timespan string: dDhh:mm:ss.nnnnnnnnn
    ns = int(td.total_seconds() * 1_000_000_000)
    return _ns_to_timespan(ns)


def _ns_to_timespan(total_ns: int) -> str:
    sign = "-" if total_ns < 0 else ""
    ns = abs(total_ns)
    day_ns = 86_400_000_000_000
    hour_ns = 3_600_000_000_000
    min_ns = 60_000_000_000
    sec_ns = 1_000_000_000

    days, rem = divmod(ns, day_ns)
    hours, rem = divmod(rem, hour_ns)
    minutes, rem = divmod(rem, min_ns)
    seconds, nanos = divmod(rem, sec_ns)
    return f"{sign}{days}D{hours:02}:{minutes:02}:{seconds:02}.{nanos:09}"
