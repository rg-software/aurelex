# Aurelex: the ultimate pocket dictionary

Aurelex is a mobile dictionary app for Android built upon [GoldenDict-NG](https://github.com/xiaoyifang/goldendict-ng)
dictionary engine. Look up words offline in your mdict / DSL / StarDict dictionaries, rendered in a
clean mobile interface. Download free dictionaries from our curated collection.

> This is a work in progress. The current builds are usable but still rough. Only one downloadable dictionary is available at the moment.

## Why Aurelex

Aurelex strives to be a worthy successor of now-discontinued [GoldenDict Mobile](http://goldendict.mobi), providing numerous useful functions:

- Offline lookup in **mdict (MDX/MDD)**, **DSL/DSL.DZ**, and **StarDict** dictionaries.
- Search-as-you-type prefix suggestions.
- Article rendering with images and audio from your dictionary packs.
- Audio playback (ogg / mp3 / wav).
- In-article link navigation and browser-style back / forward buttons.
- Full-text search across your dictionaries.
- History and favorites.
- Light and dark modes (follow your system or set manually).
- Lookup from clipboard in the app and from the quick settings tile.
- Send a selected word to the app using "share with" menu or selection toolbar.
- Downloadable online dictionaries.

Note that other dictionary formats, such as BGL, SDict, XDXF, Aard, SLOB, LSA, Zim, and EPWING are not supported. They can be converted to StarDict or MDX format with [pyglossary](https://github.com/ilius/pyglossary):

```bash
pip install pyglossary

# Convert one .bgl file to StarDict (produces .ifo/.idx/.dict):
pyglossary --read-format=BGL --write-format=Stardict mydict.bgl mydict.ifo
```

## Importing dictionaries

Aurelex will scan your source folder and its subfolders and copy all supported files into its own private storage area. You can remove the original folder after import.

Indexing will take time. You can use the dictionary normally during this process.

## Privacy

Dictionary files you bring are your own and are never uploaded. Lookups happen entirely on-device. The app (a) may access remote resources embedded into article definitions; (b) will read a remote catalog if you attempt to download a remote dictionary.

## License

GPLv3, see `LICENSE`.
