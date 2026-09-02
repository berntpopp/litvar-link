"""Regression guards for the Compose files Strato actually deploys."""

from __future__ import annotations

import json
import re
import shlex
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]  # tests/unit/<file> -> repository root
DEPLOY_COMPOSE_FILES = (
    "docker/docker-compose.yml",
    "docker/docker-compose.npm.yml",
)
NUMERIC_NON_ROOT_USER = re.compile(r"^[1-9][0-9]*:[1-9][0-9]*$")


class ComposeLoader(yaml.SafeLoader):
    """Safe YAML loader that preserves Compose extension-tag values."""


def _construct_compose_tag(loader: ComposeLoader, _tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_scalar(node)


ComposeLoader.add_multi_constructor("!", _construct_compose_tag)


def _load_compose(relative_path: str) -> dict[str, Any]:
    content = (ROOT / relative_path).read_text(encoding="utf-8")
    return yaml.load(content, Loader=ComposeLoader)  # noqa: S506 - local Compose config


def _is_hardened_tmpfs(entry: object) -> bool:
    if not isinstance(entry, str) or not entry.startswith("/tmp:"):  # noqa: S108
        return False
    options = entry.removeprefix("/tmp:").split(",")  # noqa: S108 - container mount path
    return "noexec" in options and any(
        re.fullmatch(r"size=[1-9]\d*(?:[kmgt]b?|b)?", option, re.IGNORECASE) for option in options
    )


@pytest.mark.parametrize("compose_file", DEPLOY_COMPOSE_FILES)
def test_deployed_compose_declares_runtime_hardening(compose_file: str) -> None:
    service = _load_compose(compose_file)["services"]["litvar-link"]

    assert service.get("read_only") is True
    assert service.get("init") is True

    tmpfs = service.get("tmpfs") or []
    assert any(_is_hardened_tmpfs(entry) for entry in tmpfs), (
        "litvar-link must mount a positive-size, noexec tmpfs at /tmp"
    )

    assert "no-new-privileges:true" in (service.get("security_opt") or [])
    assert "ALL" in (service.get("cap_drop") or [])


def test_production_compose_uses_an_approved_service_restart_policy() -> None:
    service = _load_compose("docker/docker-compose.prod.yml")["services"]["litvar-link"]
    assert service.get("restart") == "unless-stopped"


def test_docker_npm_config_renders_only_the_files_strato_deploys() -> None:
    lines = (ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
    target_index = next(
        index for index, line in enumerate(lines) if line.startswith("docker-npm-config:")
    )
    recipe_lines = []
    for line in lines[target_index + 1 :]:
        if line.startswith("\t"):
            recipe_lines.append(line)
        elif recipe_lines:
            break
    recipe = "\n".join(recipe_lines)
    tokens = shlex.split(recipe)
    compose_files = [operand for argument, operand in pairwise(tokens) if argument == "-f"]

    assert compose_files == [
        "docker/docker-compose.yml",
        "docker/docker-compose.npm.yml",
    ]


def test_npm_compose_declares_expose_for_the_container_port() -> None:
    """The fleet controller's validate-deployed-overlay gate refuses a rendered model
    with no `expose` entry naming the image's container port: an undeclared port reads
    as 'exposed ports differ from Compose'. docker-compose.npm.yml resets `ports` to
    empty (NPM handles routing), so it must declare `expose: ["8000"]` itself."""
    service = _load_compose("docker/docker-compose.npm.yml")["services"]["litvar-link"]
    assert [str(port) for port in service.get("expose") or []] == ["8000"]


def test_npm_compose_declares_a_numeric_non_root_user() -> None:
    """The GeneFoundry fleet deploy contract wants a numeric non-root `user:` in the
    deployed overlay so the controller's runtime observer can prove the effective uid from /proc."""
    services = _load_compose("docker/docker-compose.npm.yml")["services"]
    for name, service in services.items():
        user = service.get("user")
        assert user is not None and NUMERIC_NON_ROOT_USER.fullmatch(str(user)), (
            f"{name} must declare a numeric non-root user (e.g. '10001:10001') "
            f"in docker/docker-compose.npm.yml, got {user!r}"
        )


@pytest.mark.parametrize("compose_file", DEPLOY_COMPOSE_FILES)
def test_no_service_declares_deploy_restart_policy(compose_file: str) -> None:
    """Compose applies `deploy.restart_policy` instead of `restart` whenever both are
    present, so a `deploy.restart_policy` block would silently swap the deployed
    container onto Swarm's `on-failure` semantics -- it would not come back after a
    host reboot or a Docker upgrade, and the fleet controller's runtime observer would
    refuse to deploy it. Every service must rely solely on the top-level `restart:` key.
    """
    services = _load_compose(compose_file)["services"]
    for name, service in services.items():
        deploy = service.get("deploy") or {}
        assert "restart_policy" not in deploy, (
            f"{name} must not declare deploy.restart_policy in {compose_file}; "
            "use restart: unless-stopped instead"
        )


def test_release_compose_files_do_not_declare_user() -> None:
    """The shared release gate (container_release.py validate-compose /
    ALLOWED_SERVICE_KEYS) forbids `user` in the Compose files it builds and releases."""
    release_config = json.loads((ROOT / "container-release.json").read_text(encoding="utf-8"))
    for compose_file in release_config["service"]["compose_files"]:
        services = _load_compose(compose_file)["services"]
        for name, service in services.items():
            assert "user" not in service, (
                f"{name} must not declare user in release file {compose_file}"
            )
