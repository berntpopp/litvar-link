"""Regression guards for the Compose files Strato actually deploys."""

from __future__ import annotations

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
