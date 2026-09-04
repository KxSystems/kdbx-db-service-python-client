from __future__ import annotations

from typing import Any, Optional

from .endpoints import assembly_params, rest_path
from .errors import DbServiceError

REST_ACCEPT_YAML = "application/yaml"


def export_assembly(session, *, filename: Optional[str] = None, assembly: Optional[str] = None) -> Any:
    params = assembly_params(session, assembly)
    if session.mode == "rest":
        path = rest_path(session.options, "export_assembly")
        yaml_text = session._rest.request(
            "GET",
            path,
            params=params,
            accept=REST_ACCEPT_YAML,
            expect_json=False,
        )
    else:
        api = _lookup_qipc_api(session, "export_assembly")
        yaml_text = session._qipc.request(api, args={})
        if hasattr(yaml_text, "py"):
            yaml_text = yaml_text.py()

    if isinstance(yaml_text, bytes):
        yaml_text = yaml_text.decode("utf-8")

    if filename is not None:
        with open(filename, "w") as f:
            f.write(yaml_text)

    return yaml_text


def _lookup_qipc_api(session, name: str) -> str:
    apis = session.options.get("qipc_apis", {})
    api = apis.get(name)
    if not api:
        raise DbServiceError(f"qIPC is not supported for '{name}'. Use REST mode for this call.")
    return api
