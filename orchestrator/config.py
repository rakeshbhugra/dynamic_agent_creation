"""
Agent config: Pydantic models, YAML loader, in-memory cache, and watchfiles watcher.

The cache is invalidated whenever agents.yaml changes on disk. The watcher
runs as a background asyncio task started in the FastAPI lifespan.
"""

from pathlib import Path

import structlog
import yaml
from pydantic import BaseModel, ValidationError

log = structlog.get_logger(__name__)

CONFIG_PATH = Path("config/agents.yaml")

_cache: "AgentsConfig | None" = None


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MCPServerConfig(BaseModel):
    url: str
    tools: list[str]


class AgentConfig(BaseModel):
    name: str
    system_prompt: str
    servers: list[MCPServerConfig]


class AgentsConfig(BaseModel):
    agents: dict[str, AgentConfig]


# ---------------------------------------------------------------------------
# Loader + cache
# ---------------------------------------------------------------------------

def _load() -> AgentsConfig:
    log.debug("config_reading_file", path=str(CONFIG_PATH))
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    try:
        config = AgentsConfig.model_validate(raw)
    except ValidationError as exc:
        log.error("config_validation_failed", errors=exc.errors())
        raise
    log.info(
        "config_loaded",
        agents=list(config.agents.keys()),
        path=str(CONFIG_PATH),
    )
    return config


def get_config(fresh: bool = False) -> AgentsConfig:
    """Return config. Pass fresh=True to always read from disk."""
    global _cache
    if fresh or _cache is None:
        _cache = _load()
    return _cache


def _invalidate() -> None:
    global _cache
    _cache = None
    log.info("config_cache_invalidated")


# ---------------------------------------------------------------------------
# File watcher (runs as background asyncio task)
# ---------------------------------------------------------------------------

async def watch_config() -> None:
    """Watch agents.yaml for changes and reload the cache automatically."""
    from watchfiles import awatch

    log.info("config_watcher_started", path=str(CONFIG_PATH))
    async for changes in awatch(CONFIG_PATH):
        log.info("config_file_changed", changes=[(str(c), str(p)) for c, p in changes])
        _invalidate()
        try:
            get_config()  # eagerly validate new config and warm the cache
        except Exception as exc:
            log.error("config_reload_failed", error=str(exc))
            # Cache stays None — next request will retry the load
