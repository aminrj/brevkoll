from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict

SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"en", "sv", "ar", "uk"})


class ConfigError(ValueError):
    pass


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    llm_provider: str
    app_env: str
    app_data_dir: Path
    rate_limit_per_minute: int
    daily_model_call_budget: int
    ocr_concurrency: int
    trusted_proxies: tuple[str, ...]
    fake_llm_log: Path | None
    fake_llm_response: str | None
    llm_base_url: str | None
    llm_model: str | None


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{key} must be an integer") from None


def load_settings(env: Mapping[str, str]) -> Settings:
    log = env.get("FAKE_LLM_LOG")
    proxies = tuple(p.strip() for p in env.get("TRUSTED_PROXIES", "").split(",") if p.strip())
    return Settings(
        llm_provider=env.get("LLM_PROVIDER", "fake"),
        app_env=env.get("APP_ENV", "dev"),
        app_data_dir=Path(env.get("APP_DATA_DIR", "data")),
        rate_limit_per_minute=_int(env, "RATE_LIMIT_PER_MINUTE", 10),
        daily_model_call_budget=_int(env, "DAILY_MODEL_CALL_BUDGET", 200),
        ocr_concurrency=_int(env, "OCR_CONCURRENCY", 2),
        trusted_proxies=proxies,
        fake_llm_log=Path(log) if log else None,
        fake_llm_response=env.get("FAKE_LLM_RESPONSE"),
        llm_base_url=env.get("LLM_BASE_URL"),
        llm_model=env.get("LLM_MODEL"),
    )
