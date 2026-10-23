"""Standalone HTML preview of bilingual cards (review shape before a full run)."""

from __future__ import annotations

import html
from typing import Sequence

from .dsl import Card


def render(cards: Sequence[Card], title: str = "preview") -> str:
    """Render cards as a single self-contained HTML page."""
    blocks = []
    for card in cards:
        parts = []
        if card.pos:
            parts.append(f'<p class="pos">{html.escape(card.pos)}</p>')
        for i, sense in enumerate(card.senses, 1):
            parts.append(
                f'<p class="sense"><b>{i}.</b> {html.escape(", ".join(sense.equivalents))}</p>'
            )
            if sense.definition:
                parts.append(f'<p class="rdef">{html.escape(sense.definition)}</p>')
            if sense.synonyms:
                parts.append(
                    f'<p class="syn">syn. {html.escape(", ".join(sense.synonyms))}</p>'
                )
            if sense.example is not None:
                en, ru = sense.example
                parts.append(
                    f"<p class='ex'>ex. {html.escape(en)} — {html.escape(ru)}</p>"
                )
        for en, ru in card.pairs:
            parts.append(f"<p class='ex'>{html.escape(en)} — {html.escape(ru)}</p>")
        blocks.append(f'<div class="card"><h2>{html.escape(card.headword)}</h2>{"".join(parts)}</div>')
    return (
        "<html><head><meta charset=\"utf-8\"><style>"
        "body{font-family:sans-serif;max-width:800px;margin:auto}"
        ".card{border-top:2px solid #888;margin-top:1em}"
        ".pos{color:#888;font-style:italic;margin-bottom:0}"
        ".sense{margin:.5em 0 0}.trn{color:#a0a;margin:.2em 0 0 1em}"
        ".rdef{color:#060;font-style:italic;margin:.2em 0 0 1em}"
        ".syn{color:#555;margin:.1em 0 0 1em;font-size:90%}"
        ".ex{color:#060;margin:.2em 0 0 1em;font-size:90%}"
        "</style></head><body><h1>"
        + html.escape(title)
        + "</h1>"
        + "".join(blocks)
        + "</body></html>"
    )
