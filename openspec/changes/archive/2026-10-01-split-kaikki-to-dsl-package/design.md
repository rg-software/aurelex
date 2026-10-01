## Context

The file is already organized in sections separated by comment rules, so the
split follows seams that exist rather than inventing new ones. A dependency pass
over the AST says which module imports what; the graph is a DAG once three
helpers move.

## Decisions

### D1: One module per existing section

The cut lines are the file's own section separators. Module sizes land at
30-830 lines (`prefetch.py` is the largest), and each module keeps the comment
block that introduced its section as its docstring.

### D2: `kaikki` is a flat facade that propagates writes

Splitting one namespace into modules turns each shared global into one binding
per module. The tests (and the tool's own callers) patch names on the module
object — `kaikki.download_cached = stub` — and with plain modules that would
patch only the facade while every call site still resolved its own import.

Two options were weighed: rewriting call sites to go through a module
(`snapshot.download_cached(...)`), or keeping the flat facade and making an
attribute write propagate. The facade wins because it preserves the existing
calling convention for tests and future scripts, and because call sites stay
readable.

The propagation deliberately does **not** compare the old value: a module global
that a function rebinds (`_throttle` updates its clock) leaves the facade
holding a stale copy, so an identity check would stop propagating exactly where
it is needed. A check confirmed no name is bound to two different objects across
the modules, so the broad write only ever replaces bindings of the same thing.

### D3: The script stays a launcher

Every command in `docs/` spells `python scripts/kaikki-to-dsl.py ...`. Keeping a
launcher (and `python -m kaikki` from `scripts/`) means no doc or muscle-memory
change.

### D4: Three helpers move to break the cycle

- `_SCRIPT_DIR` → `constants` (it is the scripts dir, the package's parent, and
  both `dictzip` and `dsltext` need it for `__file__`-relative paths).
- `TabularLog` → `snapshot` (cache-state logging belongs with the cache).
- `_resolve_inputs` → `inputs`, a new module above both `audio` and `snapshot`.

Without the last one, `build` (which wanted `TabularLog` from `prefetch`) and
`prefetch` (which wanted `_resolve_inputs` from `build`) formed a cycle.

## Risks / Trade-offs

- **Import-binding semantics changed for anything not patched through the
  facade.** The propagation covers the four names the suite patches
  (`download_cached`, `_open_with_retries`, `iter_candidate_records`,
  `_last_request_time`); a new monkeypatch of a name that exists in two modules
  would need the same treatment.
- **`__file__`-relative paths** (`make-example-dicts.py`, the icon assets) moved
  one directory down with the package; `constants._SCRIPT_DIR` and
  `dsltext._ICON_ASSET_DIR` were corrected to point back at `scripts/`.
