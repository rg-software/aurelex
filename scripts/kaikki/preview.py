"""Preview"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .dsltext import _ICON_FILES, _icon_data_uri


_PREVIEW_TAGS = {
    "p": ("span", {"class": "pos"}),
    "m": ("div", {"class": "sense"}),
    "ex": ("div", {"class": "example"}),
    "com": ("div", {"class": "note"}),
    "b": ("b", {}),
    "i": ("i", {}),
    "u": ("u", {}),
    "ref": ("a", {"href": "#"}),
}

def dsl_to_html(text: str) -> str:
    """Render the DSL subset this tool emits as HTML (for preview only).

    Opening and closing tags are tracked together: a closing tag closes the
    element its opening counterpart produced, so the preview nests exactly as
    the DSL does instead of leaving every block element open.
    """
    from html import escape as _h

    out: List[str] = []
    stack: List[str] = []   # HTML element names, outermost first
    i = 0

    def closing_element(name: str) -> str:
        base = re.match(r"m\d*", name)
        if base and base.group(0):
            return "span"
        if name == "*" or name == "opt":
            return "div"
        if name in _PREVIEW_TAGS:
            return _PREVIEW_TAGS[name][0]
        return ""

    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            out.append(_h(text[i + 1]))
            i += 2
            continue
        if ch == "[":
            close = text.find("]", i)
            if close == -1:
                out.append(_h(ch))
                i += 1
                continue
            inner = text[i + 1:close]
            if inner.startswith("/"):
                # closing tag: close its element if it is the innermost open one
                name = inner[1:].strip()
                element = closing_element(name)
                if element and stack and stack[-1] == element:
                    stack.pop()
                    out.append(f"</{element}>")
                elif element and element in stack:
                    # unbalanced input: close everything above it too
                    while stack:
                        top = stack.pop()
                        out.append(f"</{top}>")
                        if top == element:
                            break
                i = close + 1
                continue
            # opening tag
            base = re.match(r"m\d*", inner)
            key = base.group(0) if base else inner
            if key.startswith("m"):
                out.append('<span class="sense">')
                stack.append("span")
            elif key == "*":
                out.append('<div class="optional"><span class="optlabel">[optional]</span> ')
                stack.append("div")
            elif key == "s":
                # the filename is the tag's own text; a bundled sense-marker
                # icon is inlined as a data URI so the standalone preview file
                # shows it, any other file stays the audio note glyph
                end = text.find("[/s]", close + 1)
                if end != -1:
                    name = text[close + 1:end]
                    if name in _ICON_FILES:
                        out.append(
                            f'<img class="senseicon" alt="{_h(name)}" '
                            f'src="{_icon_data_uri(name)}">'
                        )
                    else:
                        out.append(
                            '<span class="audio">&#9835; ' + _h(name) + "</span>"
                        )
                    i = end + 4
                    continue
            elif key in _PREVIEW_TAGS:
                tag, attrs = _PREVIEW_TAGS[key]
                attr = "".join(f' {k}="{_h(v)}"' for k, v in attrs.items())
                out.append(f"<{tag}{attr}>")
                stack.append(tag)
            i = close + 1
            continue
        out.append(_h(ch))
        i += 1

    # close anything the input left open, so no article can swallow the next
    while stack:
        out.append(f"</{stack.pop()}>")
    return "".join(out)

def render_preview(name: str, dsl_text: str, dest_html: str) -> None:
    """Write a human-readable HTML preview of the generated cards."""
    lines = dsl_text.splitlines()
    cards: List[Tuple[str, List[str]]] = []
    headword: Optional[str] = None
    body: List[str] = []
    for line in lines:
        if line.startswith("#"):
            continue
        if line and not line[0].isspace():
            if headword is not None:
                cards.append((headword, body))
            headword, body = line, []
        elif headword is not None:
            body.append(line)
    if headword is not None:
        cards.append((headword, body))

    parts = [
        "<!doctype html><meta charset='utf-8'>",
        f"<title>{name} preview</title>",
        "<style>body{font-family:sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem}"
        "h2{border-bottom:1px solid #ccc;margin-top:2rem}.pos{font-weight:bold;color:#0a6}"
        ".sense{margin:.2em 0 .2em 1em}.example{color:#555;margin-left:2em;font-style:italic}"
        ".note{color:#777;font-size:.9em}.audio{color:#a0a}"
        ".senseicon{height:1em;vertical-align:-.15em}"
        ".optional{border-left:3px solid #cc0;background:#ffd;padding:.4em .6em;margin:.6em 0}"
        ".optlabel{color:#880;font-size:.8em;text-transform:uppercase}</style>",
        f"<h1>{name} — preview</h1>",
    ]
    for headword, body in cards:
        parts.append(f"<h2>{dsl_to_html(headword)}</h2>")
        parts.append("<div>" + "<br>".join(dsl_to_html(b) for b in body) + "</div>")
    with open(dest_html, "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n")
