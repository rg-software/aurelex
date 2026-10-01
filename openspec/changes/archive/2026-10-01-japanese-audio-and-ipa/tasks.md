## 1. Japanese audio and IPA

- [x] 1.1 `ja` profile: `has_audio=True`, `pron_fields=("ipa",)`
- [x] 1.2 Skip a `sounds[]` entry whose tags name a different notation
- [x] 1.3 Tests: ja declares audio; X-SAMPA under `ipa` is not shown; a real IPA is
- [x] 1.4 Rewrite the no-audio-archive test to use a synthetic `has_audio=False` profile
- [x] 1.5 Update `docs/KAIKKI-CONVERSION.md`
- [x] 1.6 `openspec validate japanese-audio-and-ipa --strict`
- [x] 1.7 `python -m unittest scripts.tests.test_kaikki_to_dsl`
