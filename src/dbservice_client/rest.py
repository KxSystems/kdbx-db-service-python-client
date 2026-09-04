from __future__ import annotations

from typing import Any, Dict, Optional, Union

import requests

from .errors import DbServiceConnectionError, DbServiceError
from .utils import to_json_serializable


class RestClient:
    def __init__(self, base_url: str, api_key: Optional[str], options: dict) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.options = options
        self.http = requests.Session()

    @classmethod
    def from_endpoint(
        cls,
        *,
        endpoint: Optional[str],
        api_key: Optional[str],
        options: dict,
    ) -> "RestClient":
        if endpoint:
            ep = endpoint
            if not ep.startswith("http://") and not ep.startswith("https://"):
                ep = "http://" + ep
            base_url = ep
        else:
            raise ValueError("REST mode requires endpoint='http://host:port'")
        return cls(base_url=base_url, api_key=api_key, options=options)

    def close(self) -> None:
        self.http.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict] = None,
        body: Optional[Union[str, bytes]] = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        content_type: Optional[str] = None,
        timeout: Optional[Union[int, float]] = None,
        accept: str = "application/json",
        expect_json: bool = True,
    ) -> Any:
        url = self.base_url + (path if path.startswith("/") else "/" + path)

        if json_body is not None and body is not None:
            raise ValueError("Pass either json_body or body, not both.")

        merged_headers: Dict[str, str] = {"Accept": accept}
        if json_body is not None:
            merged_headers["Content-Type"] = "application/json"
        elif body is not None and content_type:
            merged_headers["Content-Type"] = content_type
        if self.api_key:
            merged_headers["Authorization"] = f"Bearer {self.api_key}"
        if headers:
            merged_headers.update(headers)

        if timeout is None:
            timeout = self.options.get("rest_timeout", 30)

        try:
            resp = self.http.request(
                method=method.upper(),
                url=url,
                json=to_json_serializable(json_body),
                data=body if json_body is None else None,
                params=params,
                headers=merged_headers,
                timeout=timeout,
            )
        except requests.RequestException as e:
            raise DbServiceConnectionError(f"REST request failed: {method} {url}") from e

        if resp.status_code >= 400:
            payload = _safe_json(resp)
            raise DbServiceError(
                "REST call returned an error",
                status_code=resp.status_code,
                payload=payload,
                method=method,
                path=path,
            )

        if expect_json:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "application/octet-stream" in ctype:
                return _decode_octet(resp.content)
            return _safe_json(resp)
        return resp.content


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text


def _decode_octet(raw: bytes) -> Any:
    try:
        import pykx as kx
    except Exception as e:
        raise DbServiceError("pykx is required to decode application/octet-stream responses.") from e

    obj = None
    if hasattr(kx, "deserialize"):
        try:
            obj = kx.deserialize(raw)
        except Exception:
            obj = None
    if obj is None:
        try:
            obj = kx.q("{-9!x}", raw)
        except Exception as e:
            raise DbServiceError("Failed to decode binary REST response.") from e

    try:
        py_obj = obj.py()
        return _normalize_text(py_obj)
    except Exception:
        return obj


def _normalize_text(value: Any) -> Any:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception:
            return value
    if isinstance(value, list):
        return [_normalize_text(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_normalize_text(v) for v in value)
    if isinstance(value, dict):
        return {_normalize_text(k): _normalize_text(v) for k, v in value.items()}
    return value
