import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, SecretStr

SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"en", "sv", "ar", "uk"})
TLS_VARS: tuple[str, str, str] = ("LLM_TLS_CERT_FILE", "LLM_TLS_KEY_FILE", "LLM_TLS_CA_FILE")


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
    llm_api_key: SecretStr | None
    model_timeout_s: float
    model_max_tokens: int
    llm_tls_cert_file: Path | None
    llm_tls_key_file: Path | None
    llm_tls_ca_file: Path | None


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{key} must be an integer") from None


def _bounded_float(
    env: Mapping[str, str], key: str, default: float, low: float, high: float
) -> float:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{key} must be a number") from None
    if not low <= value <= high:
        raise ConfigError(f"{key} must be between {low:g} and {high:g}")
    return value


def _bounded_int(env: Mapping[str, str], key: str, default: int, low: int, high: int) -> int:
    value = _int(env, key, default)
    if not low <= value <= high:
        raise ConfigError(f"{key} must be between {low} and {high}")
    return value


def _readable_file(env: Mapping[str, str], key: str) -> Path | None:
    raw = env.get(key)
    if not raw:
        return None
    if not (Path(raw).is_file() and os.access(raw, os.R_OK)):
        raise ConfigError(f"{key} must name a readable file")
    return Path(raw)


def _check_tls(env: Mapping[str, str], base_url: str | None) -> None:
    cert, key, ca = (bool(env.get(v)) for v in TLS_VARS)
    if cert != key:
        raise ConfigError("LLM_TLS_CERT_FILE and LLM_TLS_KEY_FILE must be set together")
    if (cert or ca) and base_url and urlsplit(base_url).scheme != "https":
        raise ConfigError("LLM_BASE_URL must use https when LLM_TLS_* is set")


def load_settings(env: Mapping[str, str]) -> Settings:
    _check_tls(env, env.get("LLM_BASE_URL"))
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
        llm_api_key=SecretStr(key) if (key := env.get("LLM_API_KEY")) else None,
        model_timeout_s=_bounded_float(env, "MODEL_TIMEOUT_S", 30.0, 1.0, 600.0),
        model_max_tokens=_bounded_int(env, "MODEL_MAX_TOKENS", 600, 50, 8000),
        llm_tls_cert_file=_readable_file(env, "LLM_TLS_CERT_FILE"),
        llm_tls_key_file=_readable_file(env, "LLM_TLS_KEY_FILE"),
        llm_tls_ca_file=_readable_file(env, "LLM_TLS_CA_FILE"),
    )
