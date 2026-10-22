"""Bilingual dictionary builder as a package.

Mirrors the ``kaikki`` layout: this module is a flat facade over the
submodules so ``bilingual.<name>`` keeps working and
``scripts/bilingual-to-dsl.py`` stays a thin launcher. Writing an attribute
here propagates to the submodules that bound the same object (same
:class:`_Facade` mechanism as ``kaikki``; the test suite relies on it).
"""

from __future__ import annotations

import sys
import types

from . import (
    audio,
    build,
    cli,
    constants,
    dsl,
    equivalents,
    package,
    preview,
    provenance,
    sample,
    tatoeba,
)

_SUBMODULES = (
    audio,
    build,
    constants,
    dsl,
    equivalents,
    package,
    preview,
    provenance,
    sample,
    tatoeba,
    cli,
)

for _module in _SUBMODULES:
    for _name, _value in vars(_module).items():
        if not _name.startswith("__"):
            globals().setdefault(_name, _value)


class _Facade(types.ModuleType):
    """A module whose attribute writes also reach the submodules."""

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        for module in _SUBMODULES:
            if hasattr(module, name):
                setattr(module, name, value)


sys.modules[__name__].__class__ = _Facade
