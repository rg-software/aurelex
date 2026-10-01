"""Per-language profiles

Anything specific to one language (its form-tag vocabulary, transcription fields, compact labels) lives in a profile rather than in the renderer, so adding a language is a data change. Tests assert the renderer stays generic."""

from __future__ import annotations

import re
import sys
from typing import Dict, List, Optional, Sequence, Set, Tuple


class LangProfile:
    """How to read one language's records into an article.

    ``form_tags``       - the grammatical tag vocabulary of this language. A
                          form is labelled from these and, when ``strict_tags``
                          is set, must consist only of them.
    ``form_noise_tags`` - tags that mean "raw inflection table" or a low-value
                          register/dialect variant; such forms are never shown.
    ``pron_fields``     - ``sounds[]`` keys that carry a transcription, shown in
                          this order and each at most once.
    ``short_tags``      - compact labels for the common grammatical tags.
    ``has_audio``       - whether the language has pronunciation recordings.
    ``strip_forms``     - whether article "Forms:" lines are meaningful.
    ``reading_tags``    - form tags that mark a *reading* rather than an
                          inflected form (Japanese's ``transliteration``); such a
                          form is shown on its own grouped line, not as a form.
    ``reading_marks``   - the mark each reading sub-tag prints under (``go-on``
                          and friends all being the on reading); a reading with
                          none prints under ``reading_default``.
    """

    def __init__(
        self,
        code: str,
        form_tags: Set[str],
        form_noise_tags: Set[str],
        pron_fields: Sequence[str],
        short_tags: Dict[str, str],
        has_audio: bool = True,
        strip_forms: bool = False,
        strict_tags: bool = False,
        sense_noise_tags: Optional[Set[str]] = None,
        sense_short_tags: Optional[Dict[str, str]] = None,
        pos_labels: Optional[Dict[str, str]] = None,
        reading_tags: Optional[Set[str]] = None,
        reading_marks: Optional[Dict[str, str]] = None,
        reading_default: str = "",
    ) -> None:
        self.code = code
        self.form_tags = form_tags
        self.form_noise_tags = form_noise_tags
        self.pron_fields = tuple(pron_fields)
        self.short_tags = short_tags
        self.has_audio = has_audio
        self.strip_forms = strip_forms
        self.strict_tags = strict_tags
        # Sense tags that mark the unremarkable case (a noun is countable, a
        # verb transitive) add no information and are dropped; the rest are
        # abbreviated through ``sense_short_tags``.
        self.sense_noise_tags = set(sense_noise_tags or ())
        self.sense_short_tags = dict(sense_short_tags or {})
        # Part-of-speech display labels, so a part of speech reads in the
        # dictionary's language. Empty means the source code is shown as-is.
        self.pos_labels = dict(pos_labels or {})
        # Readings (Japanese on-yomi/kun-yomi) arrive as forms but are not
        # inflections: they are grouped under a mark and shown on their own line.
        self.reading_tags = set(reading_tags or ())
        self.reading_marks = dict(reading_marks or {})
        self.reading_default = reading_default

    def form_qualifies(self, tags: Sequence[str]) -> bool:
        """Whether a form belongs in the article's forms line.

        The default is a blocklist: keep a tagged form unless it carries a
        register/dialect or table-machinery tag. That keeps ordinary paradigms
        (``children (plural)``, ``ran (past)``) whose tag sets include
        bookkeeping tags the profile does not enumerate. ``strict_tags`` flips
        it to a whitelist for languages whose tag space is noisy enough to
        need one.
        """
        tags = [str(t) for t in tags]
        if not tags:
            return False
        if any(t in self.form_noise_tags for t in tags):
            return False
        if self.strict_tags:
            return all(t in self.form_tags for t in tags)
        return True

    def label_tags(self, tags: Sequence[str]) -> str:
        """Compact human label for a tag set.

        A person tag already implies its number (``third-person`` + ``singular``
        is just "3rd sg."), so the number is dropped when a person is present,
        and tags outside the language's vocabulary are dropped as noise.
        """
        tags = [str(t) for t in tags]
        if "third-person" in tags or "first-person" in tags or "second-person" in tags:
            tags = [t for t in tags if t not in ("singular", "plural")]
        if self.form_tags:
            tags = [t for t in tags if t in self.form_tags]
        parts = [self.short_tags.get(t, t.replace("-", " ")) for t in tags]
        return ", ".join(parts)

# Register and dialect tags: a learner wants the standard paradigm, not every
# archaic, dialectal or eye-dialect variant Wiktionary records beside it.
_REGISTER_TAGS = {
    "archaic", "obsolete", "dialectal", "nonstandard", "rare", "humorous",
    "slang", "informal", "colloquial", "vulgar", "offensive", "derogatory",
    "pronunciation-spelling", "alternative", "misspelling", "Internet",
    "proscribed", "dated", "poetic", "literary", "regional",
}
_TABLE_TAGS = {"table-tags", "inflection-template", "no-table-tags"}
_FORM_NOISE = _TABLE_TAGS | _REGISTER_TAGS

# English grammatical vocabulary, used to label forms and to strip bookkeeping
# tags (canonical, etc.) from a label.
_EN_FORM_TAGS = {
    "plural", "singular", "past", "present", "participle",
    "third-person", "first-person", "second-person",
    "comparative", "superlative", "imperative", "infinitive",
    "positive", "attributive", "predicative", "not-comparable",
    "definite", "indefinite",
}
_EN_NOISE = _FORM_NOISE
_EN_SHORT_TAGS = {
    "third-person": "3rd sg.", "first-person": "1st", "second-person": "2nd",
    "singular": "sg.", "plural": "pl.",
    "present": "pres.", "past": "past", "participle": "part.",
    "comparative": "comp.", "superlative": "sup.",
    "imperative": "imper.", "infinitive": "inf.",
}

# Sense tags on English glosses that describe the unremarkable case: a verb is
# transitive unless said otherwise, so printing "(transitive)" on every other
# sense is pure noise. (Countability is *not* noise — it is shown as an icon, see
# ``_SENSE_TAG_ICONS``.) The rest are abbreviated to the forms a printed
# dictionary uses.
_EN_SENSE_NOISE = {"transitive", "intransitive", "not-comparable"}
_EN_SENSE_SHORT = {
    "figuratively": "fig.", "derogatory": "derog.", "informal": "inform.",
    "colloquial": "colloq.", "slang": "slang", "archaic": "arch.",
    "obsolete": "obs.", "dialectal": "dial.", "humorous": "hum.",
    "vulgar": "vulg.", "offensive": "offens.", "rare": "rare",
    "literary": "lit.", "poetic": "poet.", "dated": "dated",
    "metonymically": "meton.", "transferred sense": "fig.",
    "historical": "hist.", "law": "law", "medicine": "med.",
    "computing": "comput.", "biology": "biol.", "chemistry": "chem.",
    "mathematics": "math.", "physics": "phys.", "sports": "sports",
    "informal or colloquial": "inform.",
}

# German forms are dominated by case/number/gender; a global whitelist would
# discard the most useful information, hence a dedicated row.
_DE_FORM_TAGS = {
    "singular", "plural", "nominative", "genitive", "dative", "accusative",
    "strong", "weak", "mixed", "definite", "indefinite", "without-article",
    "with-article", "comparative", "superlative", "positive",
    "present", "past", "participle", "first-person", "second-person",
    "third-person", "imperative",
}
_DE_NOISE = _FORM_NOISE
_DE_SHORT_TAGS = {
    "singular": "sg.", "plural": "pl.", "nominative": "nom.",
    "genitive": "gen.", "dative": "dat.", "accusative": "acc.",
    "strong": "strong", "weak": "weak", "mixed": "mixed",
    "present": "pres.", "past": "past", "participle": "part.",
    "comparative": "comp.", "superlative": "sup.",
}

# Japanese readings (on-yomi/kun-yomi) arrive as `forms[]` tagged
# `transliteration` plus an origin tag (`go-on`, `kan-on`, `kun`, ...). They are
# not inflections, so they leave the forms line for one of their own:
# `reading_tags` names the marker, and every origin tag collapses to the
# conventional 音 (on) or 訓 (kun) mark. A reading the source does not classify
# prints under 読み. Inflections carry conjugation tags (`sa-row`,
# `imperfective`, ...): the row tags name the conjugation class rather than the
# form, so they are kept out of `form_tags` and simply drop from the label.
_JA_READING_TAGS: Set[str] = {"transliteration"}
_JA_READING_MARKS = {
    "go-on": "音", "kan-on": "音", "to-on": "音", "kun": "訓", "ko-kun": "訓",
}
_JA_READING_DEFAULT = "読み"
_JA_FORM_TAGS: Set[str] = {
    # a kana headword's kanji spelling, and the forms a Japanese grammar prints
    "kanji",
    "imperfective", "continuative", "conclusive", "attributive",
    "hypothetical", "imperative", "negative", "past", "completive",
    "conditional", "volitional", "polite", "passive", "causative",
    "potential", "stem", "definitive", "noun-from-verb",
}
# Table machinery and register/dialect, plus: the canonical lemma itself, a
# romanization (the reading is the kana form, not its rōmaji), and transitivity,
# which describes the verb rather than the form.
_JA_NOISE = _FORM_NOISE | {"canonical", "romanization", "transitive", "intransitive"}
_JA_SHORT_TAGS = {
    "kanji": "漢字",
    "imperfective": "未然形", "continuative": "連用形", "conclusive": "終止形",
    "attributive": "連体形", "hypothetical": "仮定形", "imperative": "命令形",
    "negative": "否定", "past": "過去", "completive": "完了",
    "conditional": "条件", "volitional": "意志", "polite": "丁寧",
    "passive": "受身", "causative": "使役", "potential": "可能",
    "stem": "語幹", "definitive": "已然形", "noun-from-verb": "名詞形",
}
# Parts of speech as a Japanese dictionary prints them (the source's `pos` codes
# are English for every edition).
_JA_POS_LABELS = {
    "noun": "名詞", "verb": "動詞", "adj": "形容詞", "adj_noun": "形容動詞",
    "adv": "副詞", "adnominal": "連体詞", "pron": "代名詞", "num": "数詞",
    "counter": "助数詞", "particle": "助詞", "conj": "接続詞", "intj": "感動詞",
    "prefix": "接頭辞", "suffix": "接尾辞", "affix": "接辞", "phrase": "成句",
    "proverb": "諺", "abbrev": "略語", "contraction": "縮約", "name": "固有名詞",
    "character": "漢字", "symbol": "記号",
}
# Register/context tags on a gloss, in Japanese. Countability, the initialism
# family and the obsolete/dated/archaic trio are drawn as icons (see
# `_SENSE_TAG_ICONS`), so they need no entry here; `form-of` is structural and
# says nothing the gloss does not.
_JA_SENSE_NOISE = {"transitive", "intransitive", "not-comparable", "no-gloss"}
_JA_SENSE_SHORT = {
    "figuratively": "比喩", "informal": "口語", "colloquial": "口語",
    "slang": "俗語", "historical": "歴史", "rare": "稀", "literary": "文語",
    "euphemistic": "婉曲", "broadly": "広義", "childish": "幼児語",
    "vulgar": "卑語", "rhetoric": "修辞", "onomatopoeic": "擬音",
    "Internet": "ネット", "Christian": "キリスト教", "Judaism": "ユダヤ教",
    "place": "地名", "ordinal": "序数", "cardinal": "基数",
    "in-compounds": "複合語", "literally": "文字通り", "ironic": "皮肉",
    "especially": "特に", "regional": "方言", "dialectal": "方言",
}

# Russian forms are dominated by case/number/gender and, for verbs, aspect and
# person. This vocabulary is measured from the snapshot's `ru` records.
_RU_FORM_TAGS: Set[str] = {
    "singular", "plural",
    "nominative", "genitive", "dative", "accusative", "instrumental",
    "prepositional", "locative", "partitive",
    "masculine", "feminine", "neuter",
    "animate", "inanimate",
    "present", "past", "future", "imperative", "infinitive",
    "participle", "adverbial", "active", "passive",
    "imperfective", "perfective",
    "first-person", "second-person", "third-person",
    "comparative", "superlative", "short-form",
    "reflexive", "irregular", "personal", "indeclinable", "plural-only",
}
# Table machinery and register/dialect, plus: the canonical entry is the headword
# itself, a romanization is a transliteration (Russian has IPA), `class`/`error-*`
# are bookkeeping, and the derivational tags name *other* lemmas (a relational
# adjective, a diminutive) rather than an inflected form of this one.
_RU_NOISE = _FORM_NOISE | {
    "canonical", "romanization", "class", "error-unknown-tag",
    "error-unrecognized-form",
    "relational", "diminutive", "augmentative", "abstract-noun",
    "noun-from-verb", "collective", "possessive", "emphatic",
}
_RU_SHORT_TAGS = {
    "singular": "ед.", "plural": "мн.",
    "nominative": "им.", "genitive": "род.", "dative": "дат.",
    "accusative": "вин.", "instrumental": "тв.", "prepositional": "пр.",
    "locative": "местн.", "partitive": "частичн.",
    "masculine": "м.", "feminine": "ж.", "neuter": "с.",
    "animate": "одуш.", "inanimate": "неодуш.",
    "present": "наст.", "past": "прош.", "future": "буд.",
    "imperative": "пов.", "infinitive": "инф.",
    "participle": "прич.", "adverbial": "деепр.",
    "active": "действ.", "passive": "страд.",
    "imperfective": "несов.", "perfective": "сов.",
    "first-person": "1-е л.", "second-person": "2-е л.", "third-person": "3-е л.",
    "comparative": "сравн.", "superlative": "прев.", "short-form": "кр.",
    "reflexive": "возвр.", "irregular": "неправ.",
    "personal": "личн.", "indeclinable": "нескл.", "plural-only": "только мн.",
}
# Indicative is the unmarked mood, and transitive/intransitive/not-comparable say
# nothing a Russian entry does not already carry. Aspect is *kept* -- unlike
# these, it is meaningful for Russian.
_RU_SENSE_NOISE = {"indicative", "transitive", "intransitive", "not-comparable"}

# Part-of-speech labels as a Russian dictionary prints them (the source's `pos`
# codes are English for every edition).
_RU_POS_LABELS = {
    "noun": "сущ.", "verb": "гл.", "adj": "прил.", "adv": "нареч.",
    "pron": "мест.", "num": "числ.", "prep": "предл.", "conj": "союз",
    "particle": "част.", "intj": "межд.", "phrase": "фразеол.",
    "name": "собств.", "abbrev": "сокр.", "onomatopeia": "звукоподр.",
}
# Sense-tag abbreviations in Russian (the source tags are English). An unmapped
# tag still falls back to its English text.
_RU_SENSE_SHORT = {
    "figuratively": "перен.", "colloquial": "разг.", "informal": "разг.",
    "slang": "жарг.", "dated": "устар.", "archaic": "арх.", "obsolete": "устар.",
    "historical": "ист.", "humorous": "шутл.", "ironic": "ирон.",
    "vulgar": "вульг.", "offensive": "оскорб.", "derogatory": "пренебр.",
    "rare": "редк.", "literary": "лит.", "poetic": "поэт.", "medicine": "мед.",
    "law": "юр.", "Internet": "интернет", "neologism": "неол.",
    "dialectal": "диал.", "regional": "обл.", "endearing": "ласк.",
    "childish": "детск.", "euphemistic": "эвф.",
}

LANG_PROFILES: Dict[str, LangProfile] = {
    "en": LangProfile(
        "en", _EN_FORM_TAGS, _EN_NOISE, ("ipa", "enpr"), _EN_SHORT_TAGS,
        sense_noise_tags=_EN_SENSE_NOISE, sense_short_tags=_EN_SENSE_SHORT,
    ),
    "de": LangProfile(
        "de", _DE_FORM_TAGS, _DE_NOISE, ("ipa", "enpr"), _DE_SHORT_TAGS,
    ),
    "ja": LangProfile(
        "ja", _JA_FORM_TAGS, _JA_NOISE, ("ipa",), _JA_SHORT_TAGS, has_audio=True,
        sense_noise_tags=_JA_SENSE_NOISE, sense_short_tags=_JA_SENSE_SHORT,
        pos_labels=_JA_POS_LABELS,
        reading_tags=_JA_READING_TAGS, reading_marks=_JA_READING_MARKS,
        reading_default=_JA_READING_DEFAULT,
    ),
    "ru": LangProfile(
        "ru", _RU_FORM_TAGS, _RU_NOISE, ("ipa",), _RU_SHORT_TAGS,
        sense_noise_tags=_RU_SENSE_NOISE, sense_short_tags=_RU_SENSE_SHORT,
        pos_labels=_RU_POS_LABELS,
    ),
}

def get_lang_profile(code: str) -> LangProfile:
    """The source-language profile, or a permissive fallback.

    The fallback keeps any tagged form and shows any transcription the source
    happens to provide, so an unknown source language still produces a sane
    article (and a warning) instead of an empty one.
    """
    profile = LANG_PROFILES.get(code)
    if profile is not None:
        return profile
    print(
        f"warning: no language profile for {code!r}; using a permissive default",
        file=sys.stderr,
    )
    return LangProfile(code, set(), _EN_NOISE, ("ipa", "enpr"), {})

def collect_profile_forms(record: dict, profile: LangProfile, limit: int = 8) -> List[str]:
    """Standard paradigm forms, compactly labelled and de-duplicated.

    Register/dialect variants and raw inflection tables are dropped, so an
    article shows ``ran (past)`` and ``children (pl.)`` but not
    ``runnest (archaic, 2nd sg.)`` or ``childer (dialectal, pl.)``.
    """
    forms: List[str] = []
    seen: Set[Tuple[str, Tuple[str, ...]]] = set()
    for form in record.get("forms") or []:
        if not isinstance(form, dict):
            continue
        text = form.get("form")
        if not text:
            continue
        tags = tuple(str(t) for t in (form.get("tags") or []))
        if profile.reading_tags.intersection(tags):
            # A reading, not an inflection: it is collected onto the readings
            # line instead (see `collect_profile_readings`).
            continue
        if not profile.form_qualifies(tags):
            continue
        key = (str(text), tags)
        if key in seen:
            continue
        seen.add(key)
        label = profile.label_tags(tags)
        if not label:
            # No grammatical label the profile recognises (the lemma itself, a
            # transliteration, a derivation, an unknown tag): not a form to list.
            continue
        forms.append(f"{text} ({label})")
        if len(forms) >= limit:
            break
    return forms


def _reading_groups(record: dict, profile: LangProfile) -> List[Tuple[str, List[str]]]:
    """The record's readings, grouped under their mark, in first-seen order.

    A reading's mark is the first of its tags the profile maps (``go-on`` → 音),
    or the profile's default when it maps none (→ 読み).
    """
    groups: List[Tuple[str, List[str]]] = []
    bucket_by_mark: Dict[str, List[str]] = {}
    for form in record.get("forms") or []:
        if not isinstance(form, dict):
            continue
        text = form.get("form")
        if not text:
            continue
        tags = [str(t) for t in (form.get("tags") or [])]
        if not profile.reading_tags.intersection(tags):
            continue
        mark = profile.reading_default
        for tag in tags:
            if tag in profile.reading_marks:
                mark = profile.reading_marks[tag]
                break
        bucket = bucket_by_mark.get(mark)
        if bucket is None:
            bucket = []
            bucket_by_mark[mark] = bucket
            groups.append((mark, bucket))
        if str(text) not in bucket:
            bucket.append(str(text))
    return groups


def collect_profile_readings(record: dict, profile: LangProfile) -> str:
    """One card's readings, grouped by mark, as a line (or "").

    Japanese readings are *forms* in the source but not inflections, and printing
    one label per reading ("ザ (音), サ (音), ...") is not how a dictionary reads.
    They are grouped under their conventional mark instead -- ``音: ザ, サ　訓:
    すわ-る, くら`` -- with a reading the source does not classify under the
    profile's default. A language with no ``reading_tags`` yields "".
    """
    groups = _reading_groups(record, profile)
    if not groups:
        return ""
    return "\u3000".join(f"{mark}: " + ", ".join(words) for mark, words in groups)


# A reading as a person would type it: kana only (the middle dot and the source's
# stem hyphen are separators between kana, not part of the word).
_KANA_READING = re.compile(r"^[\u3040-\u309f\u30a0-\u30ff\u30fc]+$")


def _to_hiragana(text: str) -> str:
    """Katakana to its hiragana equivalent (the shared ー is left alone)."""
    return "".join(
        chr(ord(ch) - 0x60) if "\u30a1" <= ch <= "\u30f6" else ch for ch in text
    )


def reading_words(record: dict, profile: LangProfile) -> List[str]:
    """The record's readings as lookupable kana words, de-duplicated, in order.

    For indexing a reading as an extra headword: separators are removed
    (``すわ-る`` → ``すわる``), and the reading is folded to **hiragana** — the
    form a lookup is typed in — so a katakana on-yomi (``ベイ``) also answers
    ``べい``. Only a kana-only reading is returned; a romanization or an annotated
    form is not something a lookup is typed as.
    """
    words: List[str] = []
    seen: Set[str] = set()
    for _mark, group in _reading_groups(record, profile):
        for text in group:
            word = _to_hiragana(text.replace("-", "").replace("\u30fb", "").strip())
            if not word or word in seen or not _KANA_READING.match(word):
                continue
            seen.add(word)
            words.append(word)
    return words
