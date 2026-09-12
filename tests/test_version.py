"""Version single-source test.

`engine_version` in every run record comes from `falsify.__version__`, and the
installed distribution version comes from the same string via
`[tool.setuptools.dynamic]` in pyproject.toml. This test pins the two together:
bump `src/falsify/__init__.py` and both follow; there is no second place to forget.
"""

from __future__ import annotations

from importlib.metadata import version

from falsify import __version__


def test_version_single_source():
    assert version("falsify-backtest") == __version__
