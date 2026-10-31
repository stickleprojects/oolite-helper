"""helper.platform: one module per system, behind the same names (#140)."""

import importlib
import sys

import pytest

import helper.platform


def test_linux_uses_the_x11_module(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    platform = importlib.reload(helper.platform)
    assert platform.list_monitors.__module__ == "helper.platform.linux_x11.monitors"


def test_it_provides_every_name_it_promises():
    assert all(hasattr(helper.platform, name) for name in helper.platform.__all__)


def test_another_system_is_told_what_to_provide(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    try:
        with pytest.raises(ImportError, match="game_config_dir"):
            importlib.reload(helper.platform)
    finally:
        monkeypatch.undo()
        importlib.reload(helper.platform)
