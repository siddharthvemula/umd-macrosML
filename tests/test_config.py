# Tests for config.py: settings come from environment variables when set, and fall back
# to the project's usual folders otherwise. monkeypatch sets/clears variables for one
# test only, so the real environment is never changed.

from pathlib import Path

from config import path_from_env, prefer_docker_data

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


def test_tools_prefer_docker_data_when_it_exists(monkeypatch, tmp_path):
    monkeypatch.delenv("MACROS_TEST_PATH", raising=False)
    docker_db = tmp_path / "macros.db"
    docker_db.touch()
    assert prefer_docker_data("MACROS_TEST_PATH", docker_db, DEFAULT) == docker_db


def test_tools_fall_back_to_local_without_docker_data(monkeypatch, tmp_path):
    monkeypatch.delenv("MACROS_TEST_PATH", raising=False)
    assert prefer_docker_data("MACROS_TEST_PATH", tmp_path / "missing.db", DEFAULT) == DEFAULT


def test_env_var_beats_docker_data(monkeypatch, tmp_path):
    docker_db = tmp_path / "macros.db"
    docker_db.touch()
    monkeypatch.setenv("MACROS_TEST_PATH", "/data/macros.db")
    assert prefer_docker_data("MACROS_TEST_PATH", docker_db, DEFAULT) == Path("/data/macros.db")
