# Tests for config.py: settings come from environment variables when set, and fall back
# to the project's usual folders otherwise. monkeypatch sets/clears variables for one
# test only, so the real environment is never changed.

from pathlib import Path

from config import path_from_env

DEFAULT = Path("data/macros.db")


def test_uses_the_environment_variable_when_set(monkeypatch):
    monkeypatch.setenv("MACROS_TEST_PATH", "/data/macros.db")
    assert path_from_env("MACROS_TEST_PATH", DEFAULT) == Path("/data/macros.db")


def test_falls_back_to_the_default_when_unset(monkeypatch):
    monkeypatch.delenv("MACROS_TEST_PATH", raising=False)
    assert path_from_env("MACROS_TEST_PATH", DEFAULT) == DEFAULT


def test_an_empty_value_counts_as_unset(monkeypatch):
    monkeypatch.setenv("MACROS_TEST_PATH", "  ")
    assert path_from_env("MACROS_TEST_PATH", DEFAULT) == DEFAULT
