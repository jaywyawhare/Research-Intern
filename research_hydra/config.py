from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)
_dotenv_done = False


def load_dotenv() -> None:
    global _dotenv_done
    if _dotenv_done:
        return
    _dotenv_done = True
    for path in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
        except OSError as e:
            logger.warning("Could not read %s: %s", path, e)
        break


def http_timeout_seconds(explicit: float | None) -> float:
    if explicit is not None:
        return max(30.0, float(explicit))
    raw = os.environ.get("HYDRADB_HTTP_TIMEOUT", "").strip()
    if raw:
        try:
            return max(30.0, float(raw))
        except ValueError:
            pass
    return 180.0
