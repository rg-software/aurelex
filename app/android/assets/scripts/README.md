# Vendored browser-side scripts

These files are served to the article WebView by the loopback article server
(`<base>/scripts/<file>`) and injected by `EngineController::rewriteArticleUrls`.

| File | Origin | Version | License |
|------|--------|---------|---------|
| `mark.min.js` | `engine/src/scripts/mark.min.js` (goldendict-ng, pinned release) | 9.0.0 | MIT (markjs.io) |
| `darkreader.js` | `engine/src/scripts/darkreader.js` (goldendict-ng, pinned release) | see upstream header | MIT |
| `gd-article-controls.js` | Aurelex (see file header) | - | - |
| `article-find.js` | Aurelex (see file header) | - | - |

`mark.min.js` is vendored rather than referenced from the engine's `qrc://` tag
because the engine builds `mark.min.js` into its qrc while the Android article
server serves APK assets; the copy here is byte-identical to the pinned engine's
file and is what `article-find.js` drives. When the engine submodule is bumped,
re-copy it if upstream changed and update this row.
