"""kaikki-to-dsl as a package.

The tool outgrew one file, so it is split by concern: :mod:`profiles` holds the
per-language data, :mod:`dsltext` and :mod:`render` the article text,
:mod:`snapshot`, :mod:`source` and :mod:`inputs` the snapshot and record
filtering, :mod:`audio` and :mod:`prefetch` the recordings and their back-fill,
and :mod:`build` and :mod:`cli` drive it.

Two things here are deliberate:

* This module is a **flat facade**. Everything the single-file tool exposed at
  the top level is re-exported, so ``kaikki.<name>`` and
  ``import kaikki; kaikki.build(...)`` keep working and ``scripts/kaikki-to-dsl.py``
  stays a thin launcher.
* Writing an attribute here **propagates to the submodules that bound the same
  object**. Splitting one namespace into modules turns each shared global into
  one binding per module, so a caller doing ``kaikki.download_cached = stub``
  would patch only this facade and no call site. :class:`_Facade` restores the
  single-namespace behaviour for that pattern (the test suite relies on it).
"""

from __future__ import annotations

import sys
import types

from . import (
    audio,
    build,
    cli,
    constants,
    dictzip,
    dsltext,
    inputs,
    prefetch,
    preview,
    profiles,
    render,
    snapshot,
    source,
)

# The submodules in dependency order; also the set a propagated write visits.
_SUBMODULES = (
    constants,
    profiles,
    dictzip,
    dsltext,
    snapshot,
    source,
    audio,
    render,
    preview,
    inputs,
    build,
    prefetch,
    cli,
)

for _module in _SUBMODULES:
    for _name, _value in vars(_module).items():
        if not _name.startswith("__"):
            globals().setdefault(_name, _value)

# ``from . import build`` above bound the submodule, but the tool's public name
# ``build`` is the pipeline function; put the function back.
from .build import build  # noqa: E402,F811


class _Facade(types.ModuleType):
    """A module whose attribute writes also reach the submodules.

    The package keeps one flat namespace (see the module docstring). A patch such
    as ``kaikki.download_cached = stub`` must reach every module that imported the
    old value, because that is where the name is looked up when it is called;
    nothing calls through the package.

    The write goes to *every* submodule holding the name, without comparing the
    old value: a module-level global that a function rebinds (``_throttle``
    updates its clock) leaves this facade holding a stale copy, so an identity
    check would silently stop propagating exactly where it is needed. Every name
    the modules share currently addresses one object, so the broad write only
    ever reaches bindings of the thing being replaced.
    """

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        for module in _SUBMODULES:
            if hasattr(module, name):
                setattr(module, name, value)


sys.modules[__name__].__class__ = _Facade
