# Play Store listing copy

The listing text for Google Play, kept here so it is reviewable in git rather
than living only in the Play Console. Paste into
**Grow → Store presence → Main store listing** (per language).

Limits Play enforces: app name 30, short description 80, full description 4000
characters. All three languages below are within them.

## Assets

Everything Play shows for this app is in this directory. None of it is a build
input — no Gradle or CMake rule reads these files; they are the published
artifact, versioned so a re-upload is byte-identical and a copy change is
reviewable in a pull request.

| File | Play slot | Produced by |
|---|---|---|
| `play-store-icon-512.png` | App icon (512×512) | `scripts/make-app-icons.ps1` (from `app/android/icon/aurelex-icon-1024.png`) |
| `feature-graphic-1024x500.png` | Feature graphic | `scripts/make-app-icons.ps1 -FeatureGraphic` |
| `screenshots/NN-*.png` | Phone screenshots (1080×1920) | `scripts/make-store-screenshots.ps1 -Captures <dir>` |

The two icon assets are generated from the master artwork, so re-run the icon
script after replacing it rather than editing the PNGs. The screenshots come
from `adb exec-out screencap -p` on a real device; the `NN-` prefix is the
gallery order (hero first), so re-ordering means renaming captures, and the
converter strips metadata so an unchanged capture re-converts byte-for-byte.

### Constraints Play enforces

`scripts/check-store-assets.py` is the enforcing copy of this table. CI runs it
on any change to this directory, and again in the release workflow, so a mistake
fails in the repository rather than at upload time.

| Asset | Rule Play enforces | Constant in the check |
|---|---|---|
| Phone screenshots | 2–8 per language | `MIN_SCREENSHOTS` / `MAX_SCREENSHOTS` |
| Phone screenshots | 320–3840 px on each side | `MIN_SIDE_PX` / `MAX_SIDE_PX` |
| Phone screenshots | aspect ratio 16:9 or 9:16 (1% tolerance) | `ACCEPTED_RATIOS` / `RATIO_TOLERANCE` |
| Phone screenshots | no two files byte-identical | duplicate-content rule |
| Phone screenshots | `NN-` prefixes unique and contiguous from 1 | ordering rule |
| App icon | 512×512 PNG | `ICON_SIZE` |
| Feature graphic | 1024×500 PNG | `FEATURE_GRAPHIC_SIZE` |

The bounds and ratio are why the converter exists: a phone capture is
1080×2400 (20:9), which Play rejects, so it is scaled and centred on a
1080×1920 canvas. The duplicate rule exists because a renamed capture leaves the
previous file behind, and the upload appends in file order — so the orphan
occupies a gallery slot until someone notices the count is wrong.

**What this check does not cover.** It reads PNG headers, so it validates
*shape*, not *content*. Specifically it does **not** check:

- the listing **text** limits (app name 30, short description 80, full
  description 4000 characters) — those are stated at the top of this file and
  the script never reads this one;
- whether a screenshot is *appropriate* — that it belongs in the gallery, that
  its `NN-` position tells the right story, or that what it shows is true. A
  well-formed capture of the wrong screen passes. The gallery's meaning is
  judged in review, not by the script.

`docs/screenshots/main.png` is unrelated: that is the README image for GitHub,
not a Play asset.

## Facts the copy is allowed to claim

Verified against the source, so the listings cannot drift from the app:

- Formats: MDict `.mdx`/`.mdd`, Lingvo DSL `.dsl`/`.dsl.dz`, StarDict `.ifo`.
- Free catalog: three **monolingual** Wiktionary-derived dictionaries via
  kaikki.org (English, Japanese, Russian), CC BY-SA 4.0, each with an opt-in
  resource bundle (pronunciation audio, images). No cross-language translation
  is offered on purpose — see `docs/KAIKKI-CONVERSION.md`.
- Offline lookup; nothing bundled in the APK.
- No storage permission (folder-scoped SAF import into app-private storage).
- No account, no ads, no analytics, no crash SDK. Network use: the catalog
  (`rg-software.github.io`, downloads from `github.com`) and resources an
  article itself references.
- Requires Android 6.0+ (`minSdk 23`) and a 64-bit **arm64-v8a** device.
- Interface in English, Russian and Japanese.
- Engine derived from goldendict-ng; app is GPL v3.

---

## English (en-US)

**App name:** Aurelex

**Short description**

```
Your own dictionaries, searched offline. No ads, no account, no tracking.
```

**Full description**

```
Your own dictionaries, on your phone, at the speed you type.

Aurelex is an offline dictionary for Android. It reads the formats you already own — MDict, Lingvo DSL and StarDict — and searches them entirely on-device. No account, no ads, no tracking, no limits on how much you can look up. A free built-in catalog gets you started without a computer.

GET STARTED IN THREE STEPS
1. Open Aurelex and tap the cloud icon in the Dictionaries tab.
2. Install a free dictionary from the catalog — English, Japanese or Russian.
3. Tap Search and start typing.

OR BRING YOUR OWN COLLECTION
Pick a folder of dictionary files; Aurelex copies it into private app storage and indexes it there. No storage permission is involved, and you can delete the original folder afterwards. Supported: .mdx and .mdd (MDict), .dsl and .dsl.dz (Lingvo DSL), .ifo (StarDict). Working in Zim, EPWING, BGL, SDict, XDXF, Aard or another format? Convert it to StarDict on a computer with pyglossary, then import it the same way.

SEARCHING
• Results as you type, with a suggestion panel
• Full-text search across every definition, not just headwords
• Bilingual and monolingual dictionaries together, grouped by language pair
• Groups: search one subject, one language pair, or your own set
• Search history you can clear, and favorites you keep
• Look up from anywhere — clipboard, share menu, text-selection toolbar, Quick Settings tile, or a home-screen widget

READING
• Articles keep the dictionary's own images, pronunciation audio and cross-references
• Find in page: every match highlighted, with jump to next and previous
• Zoom from 75% to 250%, with text reflow
• Back and forward through your lookups
• Light, dark, or follow the system theme
• Interface in English, Russian and Japanese

FREE DICTIONARIES IN THE CATALOG
The catalog offers dictionaries derived from Wiktionary via kaikki.org (CC BY-SA 4.0): English, Japanese and Russian. Each one installs once; pronunciation audio and extra resources are an opt-in toggle during install. They are explanatory monolingual dictionaries — they define a language rather than translate between two — which is why cross-language work is left to the bilingual dictionaries you import yourself. Once installed, they work with the network off.

PRIVACY
Everything happens on your phone. Your dictionaries are never uploaded, and no lookup ever leaves the device. Two things can use the network: the dictionary catalog, and images or other resources that a dictionary article itself references. No account, no advertising, no analytics.

OPEN SOURCE
Aurelex is free software, licensed under the GPL v3. The dictionary engine comes from the goldendict-ng project; the app, the catalog pipeline and everything around it are open source in the GitHub repository.

Requires Android 6.0 or later on a 64-bit (arm64) device.
```

---

## Russian (ru-RU)

**App name:** Aurelex

**Short description**

```
Ваши словари — офлайн. Без аккаунта, рекламы и слежки.
```

**Full description**

```
Ваши словари — на телефоне, со скоростью набора текста.

Aurelex — офлайн-словарь для Android. Он читает форматы, которые у вас уже есть: MDict, Lingvo DSL и StarDict, и ищет по ним полностью на устройстве. Без аккаунта, без рекламы, без слежки и без ограничений на число запросов. Встроенный бесплатный каталог поможет начать без компьютера.

ТРИ ШАГА
1. Откройте Aurelex и нажмите облако на вкладке «Словари».
2. Установите бесплатный словарь из каталога: английский, японский или русский.
3. Перейдите на вкладку «Поиск» и начните печатать.

ИЛИ ПРИНЕСИТЕ СВОИ СЛОВАРИ
Выберите папку с файлами словарей: Aurelex скопирует их в приватное хранилище приложения и проиндексирует. Разрешение на доступ к хранилищу не запрашивается, исходную папку после этого можно удалить. Поддерживаются: .mdx и .mdd (MDict), .dsl и .dsl.dz (Lingvo DSL), .ifo (StarDict). Словари в форматах Zim, EPWING, BGL, SDict, XDXF, Aard? Сконвертируйте их в StarDict на компьютере (например, через pyglossary) и импортируйте точно так же.

ПОИСК
• Результаты по мере набора, с панелью подсказок
• Полнотекстовый поиск по всем определениям, а не только по заголовкам
• Двуязычные и одноязычные словари рядом, сгруппированные по языковой паре
• Группы: ищите по одной теме, одной языковой паре или по своему набору
• История поиска, которую можно очистить, и избранное
• Ищите откуда угодно: из буфера обмена, меню «Поделиться», панели выделения текста, плитки в быстрых настройках или с виджета на главном экране

ЧТЕНИЕ
• Статьи сохраняют изображения, произношение и перекрёстные ссылки самого словаря
• Поиск по странице: все совпадения подсвечены, есть переход к следующему и предыдущему
• Масштаб от 75% до 250% с переносом текста
• Назад и вперёд по истории просмотра
• Светлая тема, тёмная тема или как в системе
• Интерфейс на английском, русском и японском

БЕСПЛАТНЫЕ СЛОВАРИ В КАТАЛОГЕ
В каталоге есть словари на основе Wiktionary через kaikki.org (CC BY-SA 4.0): английский, японский и русский. Каждый устанавливается один раз; произношение и дополнительные ресурсы включаются отдельным переключателем при установке. Это одноязычные словари: они объясняют язык, а не переводят между языками, поэтому для перевода используйте двуязычные словари, которые вы импортировали сами. После установки словари работают без сети.

ПРИВАТНОСТЬ
Всё происходит на телефоне. Ваши словари никогда не отправляются в сеть, и ни один запрос поиска не покидает устройство. Сеть используется только в двух случаях: каталог словарей и внешние файлы, на которые ссылаются сами статьи. Ни аккаунта, ни рекламы, ни аналитики.

ОТКРЫТЫЙ КОД
Aurelex — свободное программное обеспечение под лицензией GPL v3. Движок словарей взят из проекта goldendict-ng; само приложение, каталог и всё остальное опубликовано в репозитории на GitHub.

Требуется Android 6.0 или новее, 64-разрядное устройство (arm64).
```

---

## Japanese (ja-JP)

**App name:** Aurelex

**Short description**

```
手元の辞書をオフラインで。アカウントも広告もトラッキングもなし。
```

**Full description**

```
手元の辞書を、打鍵の速さで。

Aurelex は Android のオフライン辞書です。お手元の MDict、Lingvo DSL、StarDict をそのまま読み込み、端末の中で検索します。アカウントは不要、広告なし、トラッキングなし、検索できる量に制限もありません。内蔵の無料カタログを使えば，电脑なしで始められます。

3 ステップで開始
1. Aurelex を開き、「辞書」タブのクラウドアイコンをタップします。
2. カタログから無料の辞書をインストールします（英語・日本語・ロシア語）。
3. 「検索」タブに移って入力を始めます。

または自分の辞書を持ち込む
辞書の入ったフォルダを選ぶと、Aurelex がアプリ専用ストレージにコピーしてインデックスします。ストレージ権限は不要で、コピー元のフォルダは削除しても構いません。対応形式: .mdx と .mdd（MDict）、.dsl と .dsl.dz（Lingvo DSL）、.ifo（StarDict）。Zim、EPWING、BGL、SDict、XDXF、Aard などの形式は、パソコンで StarDict に変換してから（例: pyglossary）、同じように取り込めます。

検索
• 入力しながら候補が出るサジェストパネル
• 見出し語だけでなく、すべての定義を検索する全文検索
• 二言語・単言語の辞書を言語ペアごとにまとめて表示
• グループで、テーマ別・言語ペア別・自分だけのセットを検索
• 消去できる検索履歴とお気に入り
• クリップボード、共有メニュー、テキスト選択ツールバー、クイック設定タイル、ホーム画面ウィジェットから検索

記事を読む
• 辞書の画像・発音音声・相互参照をそのまま表示
• 記事内検索: 一致する箇所をすべて強調し、前後の該当へ移動
• 75%〜250% のズーム（テキストの折り返しに対応）
• 閲覧履歴を戻る・進む
• ライト、ダーク、システムに合わせるテーマ
• 画面表示: 英語・ロシア語・日本語

カタログの無料辞書
カタログには、kaikki.org 経由の Wiktionary 由来（CC BY-SA 4.0）の辞書が英語・日本語・ロシア語で入っています。それぞれ一度インストールすれば、あとはオフラインで使えます。発音音声とその他のリソースは、インストール時の切り替えで追加できます。これらは単言語の解説辞書で、言語どうしの翻訳用の辞書ではありません。翻訳用の二言語辞書は、自分で取り込んだものを使ってください。

プライバシー
処理はすべて端末内で完結します。辞書をアップロードすることはなく、検索が端末の外に出ることもありません。ネットワークを使うのは 2 つだけ: 辞書カタログと、辞書記事から参照されている外部画像などのリソースです。アカウント・広告・アクセス解析は一切ありません。

オープンソース
Aurelex は GPL v3 の自由ソフトウェアです。辞書エンジンは goldendict-ng プロジェクト由来で、アプリ、カタログ、周辺ツールまで含めてすべて GitHub で公開しています。

Android 6.0 以降の 64 ビット（arm64）端末が必要です。
```