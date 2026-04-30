from __future__ import annotations

import re
from datetime import date as _date, datetime as _datetime, time as _time
from typing import Any


def parse_timestamp_like(x: Any) -> _datetime:
    """Parse common timestamp inputs into a Python datetime."""
    if isinstance(x, _datetime):
        return x
    if isinstance(x, _date):
        return _datetime.combine(x, _time.min)

    if isinstance(x, str):
        s = x.strip()

        # Date-only: YYYY.MM.DD
        if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", s):
            y, m, d = (int(p) for p in s.split("."))
            return _datetime(y, m, d)

        # Normalize q-style D separator to ISO T
        s = s.replace("D", "T")

        # If it has a T, normalize date part dots to hyphens
        if "T" in s:
            date_part, time_part = s.split("T", 1)
            date_part = date_part.replace(".", "-")
            s = date_part + "T" + time_part
        else:
            s = s.replace(".", "-")

        if s.endswith("Z"):
            s = s[:-1]

        return _datetime.fromisoformat(s)

    raise ValueError(f"Unsupported timestamp type: {type(x)}")


def json_to_dataframe(pd, payload_part):
    """Convert REST JSON payload to a pandas DataFrame."""
    if isinstance(payload_part, list):
        return pd.DataFrame(payload_part)

    if isinstance(payload_part, dict):
        if "data" in payload_part and isinstance(payload_part["data"], list):
            return pd.DataFrame(payload_part["data"])
        return pd.DataFrame.from_dict(payload_part)

    return pd.DataFrame([payload_part])
