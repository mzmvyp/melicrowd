"""Testes do extrator de JSON do qwen_client."""
from __future__ import annotations

import json

import pytest

from melicrowd.llm.qwen_client import _extract_json


def test_extract_json_direct() -> None:
    raw = '{"name": "Ana", "age": 30}'
    assert _extract_json(raw) == {"name": "Ana", "age": 30}


def test_extract_json_with_thinking_prefix() -> None:
    raw = '<thinking>vou criar uma persona...</thinking>\n{"name": "Bruno", "age": 25}'
    assert _extract_json(raw) == {"name": "Bruno", "age": 25}


def test_extract_json_with_markdown_fence() -> None:
    raw = '```json\n{"name": "Carla", "age": 40}\n```'
    assert _extract_json(raw) == {"name": "Carla", "age": 40}


def test_extract_json_with_trailing_explanation() -> None:
    raw = '{"name": "Diego", "age": 50}\n\nEspero que esta persona seja útil.'
    assert _extract_json(raw) == {"name": "Diego", "age": 50}


def test_extract_json_raises_when_no_object() -> None:
    with pytest.raises(json.JSONDecodeError):
        _extract_json("desculpe, não consegui gerar a persona.")


def test_extract_json_raises_when_array_only() -> None:
    with pytest.raises(json.JSONDecodeError):
        _extract_json('["a", "b"]')
