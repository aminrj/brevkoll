import ssl
from pathlib import Path

from app.config import ConfigError, Settings


def model_ssl_context(settings: Settings) -> ssl.SSLContext | None:
    """The only SSL context for the model: pinned CA (no system store when a CA is set),
    hostname check, TLS 1.2 minimum, client certificate when configured. None without LLM_TLS_*."""
    cert, key, ca = settings.llm_tls_cert_file, settings.llm_tls_key_file, settings.llm_tls_ca_file
    if cert is None and key is None and ca is None:
        return None
    ctx = ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    if cert is not None and key is not None:
        _load_client_cert(ctx, cert, key)
    return ctx


def _load_client_cert(ctx: ssl.SSLContext, cert: Path, key: Path) -> None:
    try:
        ctx.load_cert_chain(cert, key)
    except (ssl.SSLError, OSError):
        raise ConfigError("LLM_TLS_CERT_FILE / LLM_TLS_KEY_FILE could not be loaded") from None
