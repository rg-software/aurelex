// Find-in-page controller for the Aurelex article WebView.
//
// Loaded alongside the vendored mark.js (see README.md). QML owns the find bar
// state and calls these globals through WebView.runJavaScript. Each returns a
// "total|index" string, where index is 1-based and 0 when there are no matches.
//
// mark.js with acrossElements splits one occurrence that spans inline markup
// (e.g. a phrase crossing a <b>/<a> boundary) into several <mark> elements. The
// helpers below merge adjacent, gap-free marks back into one logical match so
// the counter and prev/next behave per occurrence. The current logical match has
// data-gd-find-current set on all of its <mark> elements and is scrolled into
// view.
(function () {
  "use strict";

  var MARK_CLASS = "gd-find-mark";
  var groups = []; // array of arrays of <mark> elements
  var current = -1;

  function unmarkAll() {
    var marks = document.querySelectorAll("mark." + MARK_CLASS);
    var parents = [];
    for (var i = 0; i < marks.length; ++i) {
      var el = marks[i];
      var p = el.parentNode;
      if (!p) continue;
      if (parents.indexOf(p) === -1) parents.push(p);
      while (el.firstChild) p.insertBefore(el.firstChild, el);
      p.removeChild(el);
    }
    // Re-join the text nodes the marking split, so a later mark sees clean ones.
    for (var k = 0; k < parents.length; ++k) {
      if (parents[k].normalize) parents[k].normalize();
    }
    groups = [];
    current = -1;
  }

  function result() {
    return groups.length + "|" + (groups.length ? current + 1 : 0);
  }

  // Text strictly between two nodes in document order; a sentinel on failure so
  // unrelated marks are never merged.
  function textBetween(a, b) {
    try {
      var r = document.createRange();
      r.setStartAfter(a);
      r.setEndBefore(b);
      return r.toString();
    } catch (e) {
      return "\u0000";
    }
  }

  function buildGroups(query) {
    var raw = document.querySelectorAll("mark." + MARK_CLASS);
    var qlen = query.length;
    var out = [];
    var i = 0;
    while (i < raw.length) {
      var group = [raw[i]];
      var len = (raw[i].textContent || "").length;
      var j = i + 1;
      while (j < raw.length && len < qlen) {
        if (textBetween(raw[j - 1], raw[j]).length !== 0) break;
        group.push(raw[j]);
        len += (raw[j].textContent || "").length;
        ++j;
      }
      out.push(group);
      i = j;
    }
    return out;
  }

  function setCurrent(idx, scroll) {
    for (var g = 0; g < groups.length; ++g) {
      for (var k = 0; k < groups[g].length; ++k) {
        groups[g][k].removeAttribute("data-gd-find-current");
      }
    }
    current = idx;
    if (idx >= 0 && idx < groups.length) {
      var grp = groups[idx];
      for (var m = 0; m < grp.length; ++m) {
        grp[m].setAttribute("data-gd-find-current", "");
      }
      if (scroll && grp[0] && grp[0].scrollIntoView) {
        grp[0].scrollIntoView({ block: "center", inline: "nearest" });
      }
    }
    applyColors();
  }

  // Colors are set INLINE with !important rather than only in the injected
  // stylesheet: Dark Reader's override lives in an @layer, and a layered
  // !important outranks an unlayered one, so a <style> rule loses in dark mode
  // (the same reason the article canvas uses an inline !important). Dark mode
  // gets brighter values so the highlight reads strongly on a dark page.
  function applyColors() {
    var dark = !!window.__gdDarkMode;
    var otherBg = dark ? "#ffca28" : "#ffe082";
    var otherFg = "#202124";
    var curBg = dark ? "#ff6d00" : "#e65100";
    var curFg = dark ? "#1c1b1f" : "#ffffff";
    for (var g = 0; g < groups.length; ++g) {
      var isCurrent = (g === current);
      for (var k = 0; k < groups[g].length; ++k) {
        var st = groups[g][k].style;
        if (!st) continue;
        st.setProperty("background-color", isCurrent ? curBg : otherBg, "important");
        st.setProperty("color", isCurrent ? curFg : otherFg, "important");
        st.setProperty("font", "inherit", "important");
        st.setProperty("line-height", "inherit", "important");
        st.setProperty("padding", "0", "important");
        st.setProperty("border", "0", "important");
      }
    }
  }

  // Search only what the reader can see: collapsed optional content and any
  // candidate-overlay panel are not part of the article text. Optional content
  // becomes searchable once it is revealed, because the check reads live style.
  function visibleFilter(node) {
    var el = node.nodeType === 1 ? node : node.parentNode;
    while (el && el !== document.body) {
      if (el.id === "gd-sugg") return false;
      if (el.classList && el.classList.contains("dsl_opt")) {
        var st = window.getComputedStyle(el);
        if (st.display === "none" || st.visibility === "hidden") return false;
      }
      el = el.parentNode;
    }
    return true;
  }

  function mark(query) {
    unmarkAll();
    if (!query || !window.Mark || !document.body) return;
    var instance = new window.Mark(document.body);
    instance.mark(query, {
      element: "mark",
      className: MARK_CLASS,
      acrossElements: true,
      caseSensitive: false,
      separateWordSearch: false,
      iframes: false,
      filter: visibleFilter
    });
    groups = buildGroups(query);
    applyColors();
  }

  window.gdFindSet = function (query, idx) {
    var q = query == null ? "" : String(query);
    mark(q);
    if (groups.length) {
      var start = (typeof idx === "number" && idx >= 0 && idx < groups.length)
        ? idx : 0;
      setCurrent(start, true);
    }
    return result();
  };

  window.gdFindNext = function () {
    if (!groups.length) return result();
    setCurrent((current + 1) % groups.length, true);
    return result();
  };

  window.gdFindPrev = function () {
    if (!groups.length) return result();
    setCurrent((current - 1 + groups.length) % groups.length, true);
    return result();
  };

  window.gdFindClear = function () {
    unmarkAll();
    return result();
  };

  // Called by gdSetDarkMode on a live theme flip so open highlights re-color.
  window.gdFindRestyle = applyColors;
})();
