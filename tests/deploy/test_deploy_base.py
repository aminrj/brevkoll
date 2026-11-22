"""Checks on the public, host-free deploy/base manifests (#19 Phase 3)."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"
BASE = DEPLOY / "base"
MOUNT = "/etc/brevkoll/tls"
DOTTED_ALLOW = {"networking.k8s.io", "kustomize.config.k8s.io"}
DOTTED_SUFFIX_ALLOW = (".yaml", ".crt", ".key")


def _load() -> dict[str, list[dict[str, Any]]]:
    files = sorted(BASE.glob("*.yaml"))
    assert files, "deploy/base has no manifests"
    return {f.name: [d for d in yaml.safe_load_all(f.read_text()) if d] for f in files}


def _docs() -> list[dict[str, Any]]:
    return [d for docs in _load().values() for d in docs]


def _kind(kind: str) -> dict[str, Any]:
    found = [d for d in _docs() if d.get("kind") == kind]
    assert len(found) == 1, f"expected one {kind}, found {len(found)}"
    return found[0]


def _pod() -> dict[str, Any]:
    return _kind("Deployment")["spec"]["template"]["spec"]


def _container() -> dict[str, Any]:
    containers = _pod()["containers"]
    assert len(containers) == 1
    return containers[0]


def _keys(node: Any) -> list[str]:
    if isinstance(node, dict):
        return [str(k) for k in node] + [k for v in node.values() for k in _keys(v)]
    if isinstance(node, list):
        return [k for v in node for k in _keys(v)]
    return []


def _mebibytes(quantity: str) -> int:
    match = re.fullmatch(r"(\d+)(Mi|Gi)", quantity)
    assert match, f"unexpected memory quantity {quantity!r}"
    return int(match[1]) * (1024 if match[2] == "Gi" else 1)


def _ports(rule: dict[str, Any]) -> set[tuple[str, int]]:
    return {(p.get("protocol", "TCP"), p["port"]) for p in rule["ports"]}


@pytest.mark.ac("AC4")
def test_kustomization_lists_every_manifest() -> None:
    kustomization = _load()["kustomization.yaml"][0]
    assert kustomization["kind"] == "Kustomization"
    others = {f.name for f in BASE.glob("*.yaml")} - {"kustomization.yaml"}
    assert set(kustomization["resources"]) == others
    assert "images" not in kustomization


@pytest.mark.ac("AC4")
@pytest.mark.control("T13")
def test_deployment_single_replica_recreate_no_hpa() -> None:
    spec = _kind("Deployment")["spec"]
    assert spec["replicas"] == 1
    assert spec["strategy"] == {"type": "Recreate"}
    assert all(d["kind"] != "HorizontalPodAutoscaler" for d in _docs())


@pytest.mark.ac("AC4")
@pytest.mark.control("T9")
def test_container_is_locked_down() -> None:
    pod = _pod()
    assert pod["automountServiceAccountToken"] is False
    for ctx in (pod["securityContext"], _container()["securityContext"]):
        assert ctx["runAsNonRoot"] is True
        assert ctx["runAsUser"] == 10001
        assert ctx["runAsGroup"] == 10001
        assert ctx["seccompProfile"] == {"type": "RuntimeDefault"}
    assert pod["securityContext"]["fsGroup"] == 10001
    ctx = _container()["securityContext"]
    assert ctx["readOnlyRootFilesystem"] is True
    assert ctx["allowPrivilegeEscalation"] is False
    assert ctx["capabilities"] == {"drop": ["ALL"]}


@pytest.mark.ac("AC4")
@pytest.mark.control("T10")
def test_tmp_and_data_are_memory_emptydirs_with_limits() -> None:
    volumes = {v["name"]: v for v in _pod()["volumes"]}
    writable = {
        m["mountPath"]: m["name"] for m in _container()["volumeMounts"] if not m.get("readOnly")
    }
    assert {Path(p).name for p in writable} == {"tmp", "data"}
    assert all(Path(p).parent == Path("/") for p in writable)
    env = {e["name"]: e.get("value") for e in _container()["env"]}
    assert env["APP_DATA_DIR"] in writable
    for name in writable.values():
        empty_dir = volumes[name]["emptyDir"]
        assert empty_dir["medium"] == "Memory"
        assert _mebibytes(empty_dir["sizeLimit"]) > 0
    for volume in volumes.values():
        assert "hostPath" not in volume
        assert "persistentVolumeClaim" not in volume


@pytest.mark.ac("AC4")
def test_port_and_probes() -> None:
    container = _container()
    assert [p["containerPort"] for p in container["ports"]] == [8000]
    for probe in ("livenessProbe", "readinessProbe"):
        assert container[probe]["httpGet"] == {"path": "/healthz", "port": 8000}


@pytest.mark.control("T11")
def test_resources_cover_memory_volumes() -> None:
    resources = _container()["resources"]
    assert resources["limits"]["cpu"]
    assert resources["requests"]["cpu"]
    assert resources["requests"]["memory"]
    limit = _mebibytes(resources["limits"]["memory"])
    volumes = [v["emptyDir"] for v in _pod()["volumes"] if "emptyDir" in v]
    assert limit > sum(_mebibytes(v["sizeLimit"]) for v in volumes)


@pytest.mark.ac("AC5")
def test_service_targets_8000() -> None:
    spec = _kind("Service")["spec"]
    assert spec.get("type", "ClusterIP") == "ClusterIP"
    assert spec["selector"] == {"app": "brevkoll"}
    assert [(p["port"], p["targetPort"]) for p in spec["ports"]] == [(8000, 8000)]


@pytest.mark.ac("AC5")
@pytest.mark.control("T12")
def test_network_policy_ports() -> None:
    spec = _kind("NetworkPolicy")["spec"]
    assert spec["podSelector"] == {"matchLabels": {"app": "brevkoll"}}
    assert set(spec["policyTypes"]) == {"Ingress", "Egress"}
    egress = set().union(*(_ports(r) for r in spec["egress"]))
    ingress = set().union(*(_ports(r) for r in spec["ingress"]))
    assert egress == {("UDP", 53), ("TCP", 53), ("TCP", 8743)}
    assert ingress == {("TCP", 8000)}


@pytest.mark.ac("AC6")
@pytest.mark.control("T8")
def test_secrets_by_reference_only() -> None:
    env = {e["name"]: e for e in _container()["env"]}
    ref = env["LLM_API_KEY"]["valueFrom"]["secretKeyRef"]
    assert (ref["name"], ref["key"]) == ("brevkoll-llm", "api-key")
    for e in env.values():
        key_ref = e.get("valueFrom", {}).get("secretKeyRef", {})
        assert key_ref.get("key") != "tls.key"
    volume = next(v for v in _pod()["volumes"] if "secret" in v)
    secret = volume["secret"]
    assert secret["secretName"] == "brevkoll-llm"
    assert {i["key"] for i in secret["items"]} == {"tls.crt", "tls.key", "ca.crt"}
    assert secret["defaultMode"] & ~0o440 == 0
    mount = next(m for m in _container()["volumeMounts"] if m["name"] == volume["name"])
    assert mount["readOnly"] is True
    assert mount["mountPath"] == MOUNT
    for name in ("LLM_TLS_CERT_FILE", "LLM_TLS_KEY_FILE", "LLM_TLS_CA_FILE"):
        assert env[name]["value"].startswith(MOUNT + "/")


@pytest.mark.ac("AC6")
@pytest.mark.control("T7")
def test_no_secret_ingress_or_network_specifics() -> None:
    for doc in _docs():
        assert not (doc["kind"] == "Secret" and ({"data", "stringData"} & set(doc)))
        assert doc["kind"] != "Ingress"
        keys = set(_keys(doc))
        assert not {"ipBlock", "host", "namespace"} & keys


@pytest.mark.ac("AC6")
@pytest.mark.control("T7")
def test_no_addresses_or_host_names_in_raw_text() -> None:
    files = [f for f in DEPLOY.rglob("*") if f.is_file()]
    assert files
    for f in files:
        text = f.read_text().lower()
        assert not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", text), f.name
        for match in re.finditer(r"[a-z0-9-]+(\.[a-z0-9-]+)+", text):
            token = match[0]
            assert token in DOTTED_ALLOW or token.endswith(DOTTED_SUFFIX_ALLOW), (f.name, token)


@pytest.mark.control("T14")
def test_image_has_no_latest_tag() -> None:
    image = _container()["image"]
    assert ":" not in image
    assert "@" not in image
