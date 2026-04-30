# Python client for DB Service

The DB Service Python client provides a thin wrapper over the DB Service APIs, making it easier to connect to a running service and perform client operations from Python.

Use this client to create a session, run queries, manage tables, and interact with DB Service from Python.

Examples of using the client are included below. For a comprehensive list of parameters and their meanings, refer to the [KDB-X DB Service API spec](https://code.kx.com/kdb-x/services/db-service/api/dbservice.html).

### Requirements

- Python 3.x
- A running DB Service instance


### Install

```bash
# Install the client
pip install --pre --index https://portal.dl.kx.com/assets/pypi kdbx-db-service-client
```

For KDB-X Python installation and environment setup, see the [KDB-X Python install guide](https://code.kx.com/kdb-x/get_started/kdb-x-python-install.html).

### Connect

Create a session to connect to DB Service:

```python
import dbservice_client as dbs
import pandas as pd  # Query examples return dataframes
from datetime import datetime as dt, timezone, timedelta

# Default endpoint: localhost:8080
session = dbs.Session()

# Optional explicit endpoint
rest_session = dbs.Session(endpoint="localhost:8080")
```

### Examples

This section shows common DB Service Python client workflows, including table management, data import, querying, and deleting tables.

#### Managing Tables
Use these calls to define and inspect table schemas in DB Service. 

```python
# List tables (empty to begin with)
session.list_tables()

# Create partitioned table ('fxquote')
session.create_table(
    table="fxquote",
    type="partitioned",
    prtnCol="ts",
    sortColsDisk=["sym"],
    sortColsOrd=["sym"],
    columns=[
        {"name": "trddate", "type": "date"},
        {"name": "ts", "type": "timestamp"},
        {"name": "sym", "type": "symbol", "attrMem": "grouped", "attrDisk": "parted", "attrOrd": "parted"},
        {"name": "bid", "type": "float"},
        {"name": "ask", "type": "float"},
    ]
)

# List tables ('fxquote' table returned)
session.list_tables()

# Describe the 'fxquote' table
session.describe_table(table="fxquote")
```

#### Importing Data
DB Service supports both `file-based` and `in-memory` ingest. Any file you want to import must first be copied into the DB Service `imports` staging directory, for example: `~/.kx/db-service/data/imports/`

###### Import CSV
```python
# Import a CSV file into the existing 'fxquote' table
job = session.import_files(table="fxquote", path="fxquote.csv.gz")

# Check the status of the above import job
session.get_import(job_id=job["name"])

# Import a parquet file into the existing 'fxquote' table
session.import_files(table='fxquote', path='fxquote.parquet')

# Import a CSV file and create the 'instruments' table automatically if it does not exist
session.import_files(table="instruments", path="instruments.csv", createTable=True)
```

###### Import Kdb database
```python
# Import the 'fxquote' HDB table from the root kdb+ database directory 'fxquote-hdb'
session.import_database(table="fxquote", path="fxquote-hdb")
```

###### Import JSON

Users can import data directly from Python without file staging

```python
# Objects payload imported to 'instruments' table
job = session.import_data(
    table="instruments",
    data=[
        {"instrumentid": 77, "sym": "USDBRL", "category": "EM", "decimals": 4, "pipdecimals": 4},
        {"instrumentid": 78, "sym": "USDKRW", "category": "EM", "decimals": 2, "pipdecimals": 2},
    ],
    insert_as="objects",
)

# Rows payload imported to the 'fxquote' table
session.import_data(
    table="fxquote",
    data=[
        ["2026-01-21", "2026-01-21T10:00:00.000", "EURUSD", 901.2, 901.3],
        ["2026-01-21", "2026-01-21T10:00:00.000", "EURUSD", 901.2, 901.3],
    ],
    columnNames=["trddate", "ts", "sym", "bid", "ask"],
    insert_as="rows",
)
# Note: for rows payload, columnNames are required.
```

#### Querying Tables
Run structured, SQL, or q queries against DB Service.

```python
# Structured query
session.query_simple(
    table="fxquote",
    startTS="2026.03.02D00:00:00.000",
    endTS="2026.03.03D00:00:00.000",
    sortCols=["ts"],
    limit=5,
    return_as="json",
)

# SQL query
session.query_sql(
    query="SELECT * FROM instruments WHERE category LIKE 'EM'",
    return_as="pandas",
)

# QSQL query
session.query_q(
    query='select o:first bid,h:max bid,l:min bid,c:last bid by trddate,sym from fxquote',
    return_as="pandas",
)
```

> **Return format:** `return_as` may be `json`, `pandas`, or `pykx`. If omitted, it defaults to `json`.
#### Deleting Tables
```python
# List tables (expected: 'fxquote' and 'instruments')
session.list_tables()

# Drop the 'fxquote' table
session.drop_table(table="fxquote")

# Drop the 'instruments' table
session.drop_table(table="instruments")

# List tables (expected: no tables)
session.list_tables()
```
