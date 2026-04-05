from __future__ import annotations


def format_stored_session_error(exc: BaseException, *, max_len: int = 1000) -> str:
    """
    Turn an exception into a string safe to show in the UI and API.

    Cloudflare / Hydra often attach full HTML error pages to ``str(exc)``; those are replaced
    with a concise explanation and a tiny hint.
    """
    raw = (str(exc) or "").strip() or repr(exc)
    low = raw.lower()
    head = raw.lstrip()[:800]

    if raw.lstrip().startswith("<!") or "<html" in head.lower():
        return (
            "Hydra API returned an HTML error page (usually Cloudflare 524 = origin timeout, or 5xx). "
            "The Hydra host did not finish in time. Retry later, or increase HYDRADB_HTTP_TIMEOUT on this server."
        )

    if "524" in raw or "error code 524" in low:
        return (
            "Hydra API timeout (HTTP 524): api.hydradb.com did not respond before Cloudflare’s limit. "
            "Retry in a few minutes; if this persists, contact Hydra or raise HYDRADB_HTTP_TIMEOUT."
        )

    if "cloudflare" in low and ("timeout" in low or "524" in raw):
        return (
            "Hydra API request timed out at the edge (Cloudflare). Retry later or increase HYDRADB_HTTP_TIMEOUT."
        )

    if len(raw) > max_len:
        return raw[: max_len - 1] + "…"
    return raw
