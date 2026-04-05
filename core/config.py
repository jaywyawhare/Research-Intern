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
    if os.environ.get("TESTING") == "1":
        logger.info("load_dotenv: skipped (TESTING=1, e.g. pytest)")
        return
    repo_root = Path(__file__).resolve().parent.parent
    seen_resolved: set[Path] = set()
    loaded_paths: list[Path] = []
    for path in (Path.cwd() / ".env", repo_root / ".env"):
        try:
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen_resolved:
                continue
            seen_resolved.add(resolved)
            loaded_paths.append(resolved)
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if not k:
                    continue
                # ``MONGODB_URI=`` in an earlier file sets the key to ""; a later file with a real URI
                # must still win, or the API never sees Mongo and stays on MemorySessionStore.
                if k not in os.environ:
                    os.environ[k] = v
                elif not str(os.environ.get(k, "")).strip() and v.strip():
                    os.environ[k] = v
        except OSError as e:
            logger.warning("Could not read %s: %s", path, e)

    mongo = bool(os.environ.get("MONGODB_URI", "").strip())
    hydra_key = bool(os.environ.get("HYDRADB_API_KEY", "").strip())
    logger.info(
        "Environment: cwd=%s repo_root=%s .env files merged=%s | MONGODB_URI set=%s HYDRADB_API_KEY set=%s",
        str(Path.cwd()),
        str(repo_root),
        [str(p) for p in loaded_paths] if loaded_paths else "(none found)",
        mongo,
        hydra_key,
    )


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
