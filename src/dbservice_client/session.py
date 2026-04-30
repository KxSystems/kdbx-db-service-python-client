# session.py

from __future__ import annotations

import socket
from typing import Any, Optional, Literal

from .endpoints import rest_path
from .errors import DbServiceClosedError, DbServiceConnectionError, DbServiceError
from .ingest import cancel_import, get_import, import_data, import_database, import_files
from .qipc import QipcClient
from .query import query_simple, query_q, query_sql
from .rest import RestClient
from .tables import create_table, describe_table, drop_table, list_tables

Mode = Literal["qipc", "rest"]


class Session:
    """A connected session to the Kdb-X DB Service.

    Args:
        mode: "rest" or "qipc". Defaults to "rest".
        endpoint: Endpoint override. Defaults are used if omitted.
        api_key: API key for authentication.

    Defaults (local dev):
      - mode defaults to 'rest'
      - rest default endpoint: http://localhost:8080
      - qipc default endpoint: localhost:5040
    """

    def __init__(
        self,
        *,
        mode: Optional[Mode] = None,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """Create a DB Service session.

        Args:
            mode: "rest" or "qipc". Defaults to "rest".
            endpoint: Endpoint override. Defaults are used if omitted.
            api_key: API key for authentication.
        """
        self.pykx_licensed = self._pykx_is_licensed()
        if mode is None:
            mode = "rest"
        if mode not in ("qipc", "rest"):
            raise ValueError("mode must be 'qipc' or 'rest'")

        if endpoint is None:
            endpoint = "http://localhost:8080" if mode == "rest" else "localhost:5040"

        self.mode: Mode = mode
        self.api_key = api_key
        if mode == "rest" and endpoint is not None and "://" not in endpoint:
            endpoint = f"http://{endpoint}"
        self.endpoint = endpoint
        self.options: dict = {}
        qipc_apis = self.options.setdefault("qipc_apis", {})
        self.options.setdefault("qipc_api_styles", {})
        qipc_apis.setdefault("query_simple", ".query.simple")
        qipc_apis.setdefault("query_sql", ".query.sql")
        qipc_apis.setdefault("query_q", ".query.q")

        self._closed = False

        self._rest: Optional[RestClient] = None
        self._qipc: Optional[QipcClient] = None

        self._connect()
        self._verify_on_connect()

    @classmethod
    def rest(
        cls,
        *,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> "Session":
        return cls(
            api_key=api_key,
            endpoint=endpoint,
            mode="rest",
        )

    @classmethod
    def qipc(
        cls,
        *,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> "Session":
        return cls(
            api_key=api_key,
            endpoint=endpoint,
            mode="qipc",
        )

    def info(self) -> dict:
        return {
            "mode": self.mode,
            "api_key_set": self.api_key is not None,
            "endpoint": self.endpoint,
            "pykx_licensed": self.pykx_licensed,
            "rest_base_url": self._rest.base_url if self._rest else None,
            "http_connected": self._rest is not None,
            "qipc_connected": self._qipc is not None,
            "closed": self._closed,
        }

    def close(self) -> None:
        if self._closed:
            return

        if self._rest is not None:
            try:
                self._rest.close()
            finally:
                self._rest = None

        if self._qipc is not None:
            try:
                self._qipc.close()
            finally:
                self._qipc = None

        self._closed = True

    def rest_request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict] = None,
        body: Optional[bytes] = None,
        content_type: Optional[str] = None,
        accept: str = "application/json",
        expect_json: bool = True,
    ) -> Any:
        """Low-level REST request helper.

        Use this for advanced payloads, including binary (`application/octet-stream`).
        """
        self._ensure_open()
        if self.mode != "rest" or self._rest is None:
            raise DbServiceClosedError("REST client is not available. Create a REST Session to continue.")
        return self._rest.request(
            method=method,
            path=path,
            json_body=json_body,
            body=body,
            content_type=content_type,
            accept=accept,
            expect_json=expect_json,
        )

    def __enter__(self) -> "Session":
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---------- Tables ----------

    def create_table(
        self,
        *,
        table: str,
        description: Optional[str] = None,
        type: Optional[str] = None,
        blockSize: Optional[int] = None,
        prtnCol: Optional[str] = None,
        sortColsMem: Optional[list[str]] = None,
        sortColsOrd: Optional[list[str]] = None,
        sortColsDisk: Optional[list[str]] = None,
        primaryKeys: Optional[list[str]] = None,
        columns: list[dict],
    ) -> Any:
        """Create a table.

        Args:
            table: Table name. Required.
            description: Table description.
            type: Table type (partitioned, splayed, splayed_mem, basic).
            blockSize: Block size for table storage.
            prtnCol: Partition column.
            sortColsMem: RDB sort columns (in-memory).
            sortColsOrd: IDB sort columns (on-disk, today).
            sortColsDisk: HDB sort columns (on-disk, historical).
            primaryKeys: Primary key columns.
            columns: Column definitions. Required.
        """
        self._ensure_open()
        self._ensure_mode_ready()
        return create_table(
            self,
            table=table,
            description=description,
            type=type,
            blockSize=blockSize,
            prtnCol=prtnCol,
            sortColsMem=sortColsMem,
            sortColsOrd=sortColsOrd,
            sortColsDisk=sortColsDisk,
            primaryKeys=primaryKeys,
            columns=columns,
        )

    def list_tables(self) -> Any:
        """List all tables.
        """
        self._ensure_open()
        self._ensure_mode_ready()
        return list_tables(self)

    def describe_table(self, table: str) -> Any:
        """Return a single table definition.

        Args:
            table: Table name. Required.
        """
        self._ensure_open()
        self._ensure_mode_ready()
        return describe_table(self, table=table)

    def drop_table(self, table: str) -> Any:
        """Drop a table.

        Args:
            table: Table name. Required.
        """
        self._ensure_open()
        self._ensure_mode_ready()
        return drop_table(self, table=table)

    # ---------- Ingestion ----------

    def import_files(
        self,
        *,
        table: str,
        path: str,
        format: Optional[str] = None,
        delimiter: Optional[str] = None,
        decimal: Optional[str] = None,
        createTable: Optional[bool] = None,
        header: Optional[list[str]] = None,
        headerRowIndex: Optional[int] = None,
        include: Optional[list[str]] = None,
        types: Optional[str] = None,
        postparse: Optional[dict[str, str]] = None,
    ) -> Any:
        """Import data from files.

        Args:
            table: Target table name. Required.
            path: File path on the server. Required.
            format: File format (csv, parquet, ...).
            delimiter: CSV delimiter.
            decimal: Decimal separator.
            createTable: Create table if it doesn't exist.
            header: Explicit header list.
            headerRowIndex: Header row index (0-based).
            include: Columns to include.
            types: Optional type overrides per column.
            postparse: A dictionary of data transforms, made up of column names as keys and q expression strings as values.
        """
        self._ensure_open()
        self._ensure_mode_ready()
        return import_files(
            self,
            table=table,
            path=path,
            format=format,
            delimiter=delimiter,
            decimal=decimal,
            createTable=createTable,
            header=header,
            headerRowIndex=headerRowIndex,
            include=include,
            types=types,
            postparse=postparse,
        )

    def import_data(
        self,
        *,
        table: str,
        data: Any,
        createTable: Optional[bool] = None,
        columnNames: Optional[list[str]] = None,
        columnTypes: Optional[str] = None,
        insert_as: str = "auto",
        transport: str = "json",
    ) -> Any:
        """Import row data directly.

        Args:
            table: Target table name. Required.
            data: Row data. Required.
            createTable: Create table if it doesn't exist.
            columnNames: Column names for data.
            columnTypes: Column types for data. If omitted with createTable=True, inferred from input data.
            insert_as: Wire shape for data payload: "auto", "rows", or "objects".
            transport: REST request encoding: "json" or "binary".
        """
        self._ensure_open()
        self._ensure_mode_ready()
        return import_data(
            self,
            table=table,
            data=data,
            createTable=createTable,
            columnNames=columnNames,
            columnTypes=columnTypes,
            insert_as=insert_as,
            transport=transport,
        )

    def import_database(
        self,
        *,
        table: str,
        path: str,
    ) -> Any:
        """Start a batch ingest for a database path or session.

        Args:
            table: Target table name. Required.
            path: HDB path. Required.
        """
        self._ensure_open()
        self._ensure_mode_ready()
        return import_database(self, table=table, path=path)

    def get_import(self, job_id: str) -> Any:
        """Get status of an import job.

        Args:
            job_id: Import job identifier. Required.
        """
        self._ensure_open()
        self._ensure_mode_ready()
        return get_import(self, job_id=job_id)

    def cancel_import(self, job_id: str) -> Any:
        """Cancel an in-flight import job.

        Args:
            job_id: Import job identifier. Required.
        """
        self._ensure_open()
        self._ensure_mode_ready()
        return cancel_import(self, job_id=job_id)

    # ---------- Query ----------

    def query_simple(
        self,
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
        return_as: Optional[str] = None,
        unwrap: bool = True,
    ) -> Any:
        """Run a structured query.

        Args:
            table: Table name. Required.
            startTS: Inclusive start time.
            endTS: Exclusive end time.
            inputTZ: Input timezone.
            outputTZ: Output timezone.
            outputTZCols: Columns to apply outputTZ to.
            filter: Filter expression list.
            groupBy: Group-by columns.
            agg: Aggregations or column list.
            fill: Fill strategy.
            temporality: Continuous or slice mode.
            sortCols: Sort columns.
            limit: Max rows.
            return_as: Output format: "pykx", "pandas", or "json". Defaults to "json" (REST) or "pykx" (qIPC).
            unwrap: If False, return envelope with header/payload. Defaults to True.
        """
        self._ensure_open()
        self._ensure_mode_ready()
        return query_simple(
            self,
            table=table,
            startTS=startTS,
            endTS=endTS,
            inputTZ=inputTZ,
            outputTZ=outputTZ,
            outputTZCols=outputTZCols,
            filter=filter,
            groupBy=groupBy,
            agg=agg,
            fill=fill,
            temporality=temporality,
            sortCols=sortCols,
            limit=limit,
            return_as=return_as,
            unwrap=unwrap,
        )

    def query_sql(
        self,
        query: str,
        return_as: Optional[str] = None,
        unwrap: bool = True,
    ) -> Any:
        """Run a SQL query.

        Args:
            query: SQL string. Required.
            return_as: Output format: "pykx", "pandas", or "json". Defaults to "json" (REST) or "pykx" (qIPC).
            unwrap: If False, return envelope with header/payload. Defaults to True.
        """
        self._ensure_open()
        self._ensure_mode_ready()
        return query_sql(self, query=query, return_as=return_as, unwrap=unwrap)

    def query_q(
        self,
        query: str,
        agg: Optional[str] = None,
        return_as: Optional[str] = None,
        unwrap: bool = True,
    ) -> Any:
        """Run a qSQL query.

        Args:
            query: qSQL string. Required.
            agg: Optional aggregation function/lambda.
            return_as: Output format: "pykx", "pandas", or "json". Defaults to "json" (REST) or "pykx" (qIPC).
            unwrap: If False, return envelope with header/payload. Defaults to True.
        """
        self._ensure_open()
        self._ensure_mode_ready()
        return query_q(
            self,
            query=query,
            agg=agg,
            return_as=return_as,
            unwrap=unwrap,
        )

    # ---------- internal helpers ----------

    def _ensure_open(self) -> None:
        if self._closed:
            raise DbServiceClosedError("This Session is closed. Create a new Session to continue.")

    def _connect(self) -> None:
        if self.mode == "rest":
            self._connect_rest()
        else:
            self._connect_qipc()

    def _connect_rest(self) -> None:
        self._rest = RestClient.from_endpoint(
            endpoint=self.endpoint,
            api_key=self.api_key,
            options=self.options,
        )

    def _connect_qipc(self) -> None:
        self._qipc = QipcClient.from_endpoint(
            endpoint=self.endpoint,
            options=self.options,
        )

    def _verify_on_connect(self) -> None:
        if self.mode == "rest":
            self._verify_rest_connectivity()
        else:
            self._verify_qipc_connectivity()

    def _verify_rest_connectivity(self) -> None:
        if self._rest is None:
            raise DbServiceConnectionError("REST client is not available.")
        probe_path = rest_path(self.options, "list_tables")
        try:
            # Probe a DB Service API route so we fail fast on wrong endpoints.
            self._rest.request("GET", probe_path, accept="application/json", expect_json=False, timeout=3)
        except DbServiceConnectionError as e:
            raise DbServiceConnectionError(
                f"Unable to connect to DB Service at {self.endpoint}. Is the service running?"
            ) from e
        except DbServiceError as e:
            # Auth/authorization errors still prove DB Service is reachable.
            if e.status_code in (401, 403):
                return
            raise DbServiceConnectionError(
                f"Endpoint {self.endpoint} is reachable but not serving DB Service API at {probe_path}."
            ) from e

    def _verify_qipc_connectivity(self) -> None:
        if self._qipc is None or self._qipc.q is None:
            raise DbServiceConnectionError("qIPC client is not available.")
        try:
            # Check that the qIPC port is reachable without sending a q expression.
            # Some gateway listeners can close connections on raw q probes like "::".
            with socket.create_connection((self._qipc.host, self._qipc.port), timeout=3):
                pass
        except Exception as e:
            raise DbServiceConnectionError(
                f"Unable to connect to DB Service qIPC at {self.endpoint}. Is the service running?"
            ) from e

    @staticmethod
    def _pykx_is_licensed() -> bool:
        try:
            import pykx as kx
        except Exception:
            return False
        return bool(getattr(kx, "licensed", False))

    def _ensure_mode_ready(self) -> None:
        if self.mode == "rest" and self._rest is None:
            raise DbServiceClosedError("REST client is not available. Create a new Session to continue.")
        if self.mode == "qipc" and self._qipc is None:
            raise DbServiceClosedError("qIPC client is not available. Create a new Session to continue.")
