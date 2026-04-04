from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from core.hydra_research_bridge import HydraResearchBridge

logger = logging.getLogger(__name__)


def hydra_bridge_or_error(use_hydra: bool) -> HydraResearchBridge | None:
    if not use_hydra:
        return None
    try:
        from core.hydra_research_bridge import HydraResearchBridge
    except ModuleNotFoundError as e:
        if getattr(e, "name", None) == "hydra_db":
            logger.warning("hydra-db-python not installed: %s", e)
            raise HTTPException(
                status_code=503,
                detail=(
                    "Hydra is enabled but the Hydra client is not installed. "
                    "Run pip install hydra-db-python or set use_hydra=false."
                ),
            ) from e
        raise
    try:
        return HydraResearchBridge()
    except ValueError as e:
        logger.warning("Hydra unavailable: %s", e)
        raise HTTPException(
            status_code=503,
            detail=(
                "Hydra is enabled but credentials are missing or invalid. "
                "Set HYDRADB_* env vars or set use_hydra=false."
            ),
        ) from e


def try_hydra_bridge(use_hydra: bool):
    """
    Best-effort Hydra client for background jobs: returns ``None`` if disabled, not installed,
    or misconfigured (session still runs without recall/ingest).
    """
    if not use_hydra:
        return None
    try:
        from core.hydra_research_bridge import HydraResearchBridge

        return HydraResearchBridge()
    except (ModuleNotFoundError, ValueError) as e:
        logger.info("Hydra unavailable; continuing without bridge: %s", e)
        return None
