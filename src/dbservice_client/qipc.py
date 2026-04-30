from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .errors import DbServiceConnectionError, DbServiceError


class QipcClient:
    def __init__(self, host: str, port: int, options: dict) -> None:
        self.host = host
        self.port = port
        self.options = options
        self.q = None
        self._connect()

    @classmethod
    def from_endpoint(
        cls,
        *,
        endpoint: Optional[str],
        options: dict,
    ) -> "QipcClient":
        if endpoint:
            ep = endpoint
            if "://" not in ep:
                ep = "http://" + ep
            u = urlparse(ep)
            host = u.hostname
            port = u.port
        else:
            host = None
            port = None

        if host is None or port is None:
            raise ValueError("qIPC mode requires endpoint='host:port'")
        return cls(host=host, port=port, options=options)

    def close(self) -> None:
        if self.q is not None:
            self.q.close()
            self.q = None

    def request(
        self,
        api_name: str,
        *,
        args: Optional[Dict[str, Any]] = None,
        callback: str = "",
        opts: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if self.q is None:
            raise DbServiceError("qIPC request attempted on a closed session")

        try:
            import pykx as kx
        except Exception as e:
            raise DbServiceConnectionError("pykx is required for qipc mode. Install it to use qIPC.") from e

        api_sym = kx.SymbolAtom(api_name)
        cb_sym = kx.SymbolAtom(callback)
        args_dict = args or {}
        opts_dict = opts or {}

        call_style = (self.options.get("qipc_api_styles") or {}).get(api_name, "gateway")

        try:
            args_q = kx.toq(args_dict, strings_as_char=True)
            opts_q = kx.toq(opts_dict, strings_as_char=True)
            if call_style == "simple":
                msg = kx.toq([api_sym, args_q])
            else:
                msg = kx.toq([api_sym, args_q, cb_sym, opts_q])
            return self.q(msg)
        except Exception as e:
            raise DbServiceError(
                "qIPC call failed",
                payload={"api": api_name, "args": args_dict},
                api=api_name,
                detail=str(e),
            ) from e

    def _connect(self) -> None:
        try:
            import pykx as kx
        except Exception as e:
            raise DbServiceConnectionError("pykx is required for qipc mode. Install it to use qIPC.") from e

        qipc_opts = dict(self.options.get("qipc", {}))
        qipc_opts.setdefault("no_ctx", True)

        try:
            self.q = kx.SyncQConnection(host=self.host, port=self.port, **qipc_opts)
        except Exception as e:
            raise DbServiceConnectionError(f"Failed to connect to qIPC at {self.host}:{self.port}") from e
