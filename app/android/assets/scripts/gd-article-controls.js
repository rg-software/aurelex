// Article-side controls for the Aurelex article WebView.
//
// Upstream goldendict-ng defines gdExpandOptPart in scripts/gd-builtin.js, but
// that file is the desktop link/active-article bridge and is stripped from every
// article by EngineController::rewriteArticleUrls. Without a definition the
// engine's `[*]...[/opt]` expander (<img class="hidden_expand_opt"
// onclick="gdExpandOptPart('O..._expand','gd-<dictId>')">) is inert, so the
// content the dictionary marked optional stays hidden with no way to reach it.
// This is the only definition the WebView sees, so it keeps upstream's
// semantics: the `alt` text is the [+] / [-] state flag, the icon swaps with
// it, and the toggle covers the hidden zones of the named dictionary section.

(function () {
  // Icons are swapped at click time, when document.currentScript is already
  // null, so capture the asset origin now: this script is served from
  // <base>/scripts/gd-article-controls.js, so dropping the trailing
  // "/scripts/<file>" leaves <base> (the loopback ArticleServer root). The
  // engine's own initial qrc:///icons/expand_opt.svg is rewritten to that same
  // base by rewriteArticleUrls; only the swapped-in src needs this. Deriving it
  // here keeps the asset self-contained — it keeps working if the port changes.
  var base = "";
  var self = document.currentScript;
  if (self && self.src) {
    base = self.src.replace(/\/scripts\/[^/]*$/, "");
  }
  if (!base && /^https?:$/.test(document.location.protocol)) {
    base = document.location.origin;
  }

  // Called from an inline onclick attribute, so it must be a plain global (not
  // module-scoped) and must never throw: a missing expander or section id
  // leaves the page exactly as it is rather than breaking the click.
  window.gdExpandOptPart = function (expanderId, optionalId) {
    var expander = document.getElementById(expanderId);
    if (!expander) {
      return;
    }
    var isExpanded = expander.alt === "[+]";
    expander.alt = isExpanded ? "[-]" : "[+]";
    if (base) {
      expander.src =
        base + "/icons/" + (isExpanded ? "collapse_opt.svg" : "expand_opt.svg");
    }
    var section = document.getElementById(optionalId);
    if (!section) {
      return;
    }
    // Per-dictionary scope, matching upstream: one expander is emitted per
    // article, so revealing one entry's hidden notes leaves another's alone.
    var zones = section.querySelectorAll(".dsl_opt");
    for (var i = 0; i < zones.length; ++i) {
      zones[i].style.display = isExpanded ? "inline" : "none";
    }
  };
})();
