"""Holdout: the hardened, host-free deploy/base (spec ACs 4-6)."""

import re
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parents[2] / "deploy" / "base"
PRIVATE = re.compile(
    r"\b(10\.\d+|192\.168|172\.(1[6-9]|2\d|3[01]))\.\d+\.\d+\b|\.lab\.|\.ts\.net|\.local\b"
)


def _docs() -> list[dict]:
    kust = yaml.safe_load((BASE / "kustomization.yaml").read_text())
    out: list[dict] = []
    for res in kust["resources"]:
        out += [d for d in yaml.safe_load_all((BASE / res).read_text()) if d]
    return out


def _kind(kind: str) -> list[dict]:
    return [d for d in _docs() if d.get("kind") == kind]


def _pod() -> dict:
    (dep,) = _kind("Deployment")
    return dep["spec"]["template"]["spec"]


def _container() -> dict:
    (c,) = _pod()["containers"]
    return c


def test_one_replica_non_root_read_only() -> None:  # AC4
    (dep,) = _kind("Deployment")
    assert dep["spec"]["replicas"] == 1
    sc = {**_pod().get("securityContext", {}), **_container().get("securityContext", {})}
    assert sc.get("runAsNonRoot") is True
    assert sc.get("readOnlyRootFilesystem") is True
    assert sc.get("allowPrivilegeEscalation") is False
    assert "ALL" in sc.get("capabilities", {}).get("drop", [])


def test_writable_mounts_are_in_memory() -> None:  # AC4
    vols = {v["name"]: v for v in _pod()["volumes"]}
    mounts = {m["mountPath"].strip("/"): m for m in _container()["volumeMounts"]}
    assert {"tmp", "data"} <= set(mounts)
    for path, m in mounts.items():  # every writable mount is in memory; secrets are read-only
        if "secret" in vols[m["name"]]:
            assert m.get("readOnly") is True, path
        else:
            assert vols[m["name"]].get("emptyDir", {}).get("medium") == "Memory", path


def test_port_and_probes() -> None:  # AC4
    c = _container()
    assert any(p["containerPort"] == 8000 for p in c["ports"])
    for probe in ("livenessProbe", "readinessProbe"):
        assert c[probe]["httpGet"]["path"] == "/healthz"


def test_service_and_egress() -> None:  # AC5
    (svc,) = _kind("Service")
    assert any(str(p.get("targetPort")) in ("8000", "http") for p in svc["spec"]["ports"])
    (pol,) = _kind("NetworkPolicy")
    assert "Egress" in pol["spec"]["policyTypes"]
    rules = pol["spec"]["egress"]
    assert all(rule.get("ports") for rule in rules)  # no rule that opens every port
    ports = {p["port"] for rule in rules for p in rule["ports"]}
    assert ports and ports <= {53, 8743}


def test_secrets_by_reference_only() -> None:  # AC6
    assert not [s for s in _kind("Secret") if s.get("data") or s.get("stringData")]
    assert not _kind("Ingress")
    env = {e["name"]: e for e in _container().get("env", [])}
    assert env["LLM_API_KEY"]["valueFrom"]["secretKeyRef"]["name"] == "brevkoll-llm"
    secret_vols = [v for v in _pod()["volumes"] if "secret" in v]
    assert any(v["secret"]["secretName"] == "brevkoll-llm" for v in secret_vols)


def test_no_host_names_or_private_addresses() -> None:  # AC6
    files = [f for f in BASE.rglob("*") if f.is_file()]
    assert files
    for f in files:
        assert not PRIVATE.search(f.read_text()), f.name
