from pathlib import Path

import pytest

from app.config import TLS_VARS, ConfigError, load_settings

BASE = {"LLM_PROVIDER": "openai_compat", "LLM_MODEL": "m"}
HTTPS = "https://model:8743/v1"


def _files(tmp_path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for var, name in zip(TLS_VARS, ("tls.crt", "tls.key", "ca.crt"), strict=True):
        path = tmp_path / name
        path.write_text("dummy")
        env[var] = str(path)
    return env


@pytest.mark.ac("AC1")
def test_tls_paths_load_when_all_three_exist(tmp_path: Path) -> None:
    env = _files(tmp_path)
    s = load_settings({**BASE, "LLM_BASE_URL": HTTPS, **env})
    assert s.llm_tls_cert_file == Path(env["LLM_TLS_CERT_FILE"])
    assert s.llm_tls_key_file == Path(env["LLM_TLS_KEY_FILE"])
    assert s.llm_tls_ca_file == Path(env["LLM_TLS_CA_FILE"])


def test_tls_paths_default_to_none() -> None:
    s = load_settings({})
    assert (s.llm_tls_cert_file, s.llm_tls_key_file, s.llm_tls_ca_file) == (None, None, None)


@pytest.mark.ac("AC2")
@pytest.mark.control("T3")
def test_cert_without_key_names_the_pair(tmp_path: Path) -> None:
    env = _files(tmp_path)
    with pytest.raises(ConfigError, match="LLM_TLS_CERT_FILE and LLM_TLS_KEY_FILE"):
        load_settings({**BASE, "LLM_TLS_CERT_FILE": env["LLM_TLS_CERT_FILE"]})


@pytest.mark.ac("AC2")
@pytest.mark.control("T3")
def test_key_without_cert_names_the_pair(tmp_path: Path) -> None:
    env = _files(tmp_path)
    with pytest.raises(ConfigError, match="LLM_TLS_CERT_FILE and LLM_TLS_KEY_FILE"):
        load_settings({**BASE, "LLM_TLS_KEY_FILE": env["LLM_TLS_KEY_FILE"]})


@pytest.mark.ac("AC2")
@pytest.mark.control("T3")
@pytest.mark.parametrize("var", TLS_VARS)
def test_missing_path_names_the_variable(tmp_path: Path, var: str) -> None:
    env = _files(tmp_path)
    missing = str(tmp_path / "nowhere" / "secret-name.pem")
    with pytest.raises(ConfigError) as err:
        load_settings({**BASE, "LLM_BASE_URL": HTTPS, **env, var: missing})
    assert str(err.value) == f"{var} must name a readable file"
    assert "secret-name" not in str(err.value)
    assert str(tmp_path) not in str(err.value)


@pytest.mark.control("T3")
def test_directory_is_not_a_readable_file(tmp_path: Path) -> None:
    env = _files(tmp_path)
    with pytest.raises(ConfigError, match="LLM_TLS_CA_FILE must name a readable file"):
        load_settings({**BASE, "LLM_BASE_URL": HTTPS, **env, "LLM_TLS_CA_FILE": str(tmp_path)})


@pytest.mark.control("T3")
@pytest.mark.control("T4")
def test_error_never_contains_file_content(tmp_path: Path) -> None:
    cert = tmp_path / "tls.crt"
    cert.write_text("-----BEGIN PRIVATE KEY-----secret")
    with pytest.raises(ConfigError) as err:
        load_settings({**BASE, "LLM_TLS_CERT_FILE": str(cert)})
    assert "BEGIN" not in str(err.value)
    assert "secret" not in str(err.value)


@pytest.mark.control("T1")
def test_http_base_url_refused_with_tls(tmp_path: Path) -> None:
    env = _files(tmp_path)
    with pytest.raises(ConfigError, match="LLM_BASE_URL must use https"):
        load_settings({**BASE, "LLM_BASE_URL": "http://model:8743/v1", **env})
    assert load_settings({**BASE, "LLM_BASE_URL": HTTPS, **env}).llm_base_url == HTTPS


@pytest.mark.control("T1")
def test_http_base_url_refused_with_ca_alone(tmp_path: Path) -> None:
    ca = _files(tmp_path)["LLM_TLS_CA_FILE"]
    with pytest.raises(ConfigError, match="LLM_BASE_URL must use https"):
        load_settings({**BASE, "LLM_BASE_URL": "http://model:8743/v1", "LLM_TLS_CA_FILE": ca})


@pytest.mark.control("T1")
def test_http_base_url_still_allowed_without_tls() -> None:
    s = load_settings({**BASE, "LLM_BASE_URL": "http://model:8743/v1"})
    assert s.llm_base_url == "http://model:8743/v1"


@pytest.mark.control("T3")
def test_ca_alone_is_allowed(tmp_path: Path) -> None:
    ca = _files(tmp_path)["LLM_TLS_CA_FILE"]
    s = load_settings({**BASE, "LLM_BASE_URL": HTTPS, "LLM_TLS_CA_FILE": ca})
    assert s.llm_tls_ca_file == Path(ca)
    assert s.llm_tls_cert_file is None


def test_empty_tls_var_counts_as_unset() -> None:
    s = load_settings({**BASE, "LLM_BASE_URL": "http://model:8743/v1", "LLM_TLS_CA_FILE": ""})
    assert s.llm_tls_ca_file is None


@pytest.mark.control("T4")
def test_settings_repr_hides_api_key(tmp_path: Path) -> None:
    env = _files(tmp_path)
    s = load_settings({**BASE, "LLM_BASE_URL": HTTPS, "LLM_API_KEY": "sk-test", **env})
    assert "sk-test" not in repr(s)
