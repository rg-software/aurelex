package aurelex.android

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.util.concurrent.Future

/** Single-activity navigation destinations (task 3.2). */
enum class Dest { SEARCH, ARTICLE, DICTIONARIES, HISTORY, FAVORITES }

class MainViewModel : ViewModel() {

    /** Currently looked-up word shown in the article screen, if any. */
    data class ArticleState(val word: String, val html: String)

    private val _suggestions = MutableStateFlow<List<String>>(emptyList())
    val suggestions: StateFlow<List<String>> = _suggestions

    private val _article = MutableStateFlow<ArticleState?>(null)
    val article: StateFlow<ArticleState?> = _article

    private val _dictCount = MutableStateFlow(0)
    val dictCount: StateFlow<Int> = _dictCount

    private val _isIndexing = MutableStateFlow(false)
    val isIndexing: StateFlow<Boolean> = _isIndexing

    private val _indexMessage = MutableStateFlow<String?>(null)
    val indexMessage: StateFlow<String?> = _indexMessage

    private val _darkMode = MutableStateFlow(false)
    val darkMode: StateFlow<Boolean> = _darkMode

    private val _history = MutableStateFlow<List<String>>(emptyList())
    val history: StateFlow<List<String>> = _history

    private val _favorites = MutableStateFlow<List<String>>(emptyList())
    val favorites: StateFlow<List<String>> = _favorites

    private val _ttsEnabled = MutableStateFlow(true)
    val ttsEnabled: StateFlow<Boolean> = _ttsEnabled

    @Volatile
    private var prefs: PreferencesStore? = null

    /** Initializes app state from the persisted preferences (task 5.1). */
    fun loadPreferences(store: PreferencesStore) {
        prefs = store
        _darkMode.value = store.darkMode
        _ttsEnabled.value = store.ttsEnabled
        _history.value = store.history
        _favorites.value = store.favorites
    }

    data class DictEntry(val name: String, val file: String)

    private val _dictionaries = MutableStateFlow<List<DictEntry>>(emptyList())
    val dictionaries: StateFlow<List<DictEntry>> = _dictionaries

    private fun refreshDictionaries() {
        _dictionaries.value = try {
            EngineClient.dictInfo().get().map { DictEntry(it.first, it.second) }
        } catch (e: Exception) {
            android.util.Log.e("MainViewModel", "dictInfo failed", e)
            emptyList()
        }
    }

    /** Simple back-stack of destinations (back navigates within it). */
    private val _backStack = MutableStateFlow<List<Dest>>(listOf(Dest.SEARCH))
    val backStack: StateFlow<List<Dest>> = _backStack

    fun push(dest: Dest) {
        _backStack.value = _backStack.value + dest
    }

    fun pop(): Boolean {
        val s = _backStack.value
        if (s.size <= 1) return false
        _backStack.value = s.dropLast(1)
        return true
    }

    /** Engine init happens in the separate EngineService process on startup. */
    fun init(context: android.content.Context) {
        // Nothing to do in the UI process; kept for API compatibility.
    }

    /** Scans [folder] for dictionaries; [onDone] runs with the load count. */
    fun scanDicts(folder: String, onDone: (Int) -> Unit) {
        viewModelScope.launch(Dispatchers.IO) {
            val n = EngineClient.scanDicts(folder).get()
            _dictCount.value += n
            refreshDictionaries()
            onDone(n)
        }
    }

    /** Moves dictionary at [from] to [to] in the single group; refreshes list. */
    fun moveDict(from: Int, to: Int) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                if (EngineClient.moveDict(from, to).get() == 0) {
                    refreshDictionaries()
                }
            } catch (e: Exception) {
                android.util.Log.e("MainViewModel", "moveDict failed", e)
            }
        }
    }

    /** Toggles article dark mode (task 7.1); persists + re-looks-up so CSS re-emits. */
    fun toggleDarkMode(word: String?) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val next = !_darkMode.value
                EngineClient.setDarkMode(next).get()
                _darkMode.value = next
                prefs?.darkMode = next
                word?.let { lookup(it) }
            } catch (e: Exception) {
                android.util.Log.e("MainViewModel", "setDarkMode failed", e)
            }
        }
    }

    /** Toggles the TTS pronunciation preference (task 4.2). */
    fun toggleTts() {
        val next = !_ttsEnabled.value
        _ttsEnabled.value = next
        prefs?.ttsEnabled = next
    }

    // --- History (tasks 2.1/2.3) ---

    fun recordHistory(word: String) {
        prefs?.addHistory(word)
        _history.value = prefs?.history ?: emptyList()
    }

    fun removeHistory(word: String) {
        prefs?.removeHistory(word)
        _history.value = prefs?.history ?: emptyList()
    }

    fun clearHistory() {
        prefs?.clearHistory()
        _history.value = emptyList()
    }

    // --- Favorites (tasks 3.1/3.3) ---

    fun toggleFavorite(word: String) {
        val p = prefs ?: return
        if (p.isFavorite(word)) {
            p.removeFavorite(word)
        } else {
            p.addFavorite(word)
        }
        _favorites.value = p.favorites
    }

    fun isFavorite(word: String): Boolean = prefs?.isFavorite(word) == true

    fun removeFavorite(word: String) {
        prefs?.removeFavorite(word)
        _favorites.value = prefs?.favorites ?: emptyList()
    }

    /**
     * Picks the folder [treeUri] and scans it. Resolves the physical path
     * when possible; otherwise stages copies into app-private storage first.
     * When the stored index format no longer matches the running engine
     * (design D5), existing indexes are invalidated and the user is told that
     * a reindex is happening. [onDone] receives the number of dictionaries
     * loaded by this pick.
     */
    fun pickAndScan(context: android.content.Context, treeUri: android.net.Uri, onDone: (Int) -> Unit) {
        viewModelScope.launch(Dispatchers.IO) {
            _isIndexing.value = true
            _indexMessage.value = null
            var n = 0
            try {
                if (!IndexVersion.isCurrent(context)) {
                    IndexVersion.invalidate(context)
                    _indexMessage.value = "Reindexing dictionaries (engine version changed)…"
                }

                // On Android the engine process cannot read /storage/emulated/0
                // paths via QDir (scoped storage) even after a SAF grant, and the
                // content-URI grant only covers the UI process's access. So we
                // ALWAYS stage supported files into app-private storage and scan
                // the copy — the engine (same package) can read its own data dir.
                val dest = java.io.File(context.filesDir, "staged").apply { mkdirs() }
                dest.listFiles()?.forEach { it.delete() }
                n = try {
                    val scanPath = SafResolver.stageDictionaryFiles(context, treeUri, dest).absolutePath
                    android.util.Log.i("MainViewModel", "scanPath=$scanPath")
                    // Remember the staged dir so a later engine restart can
                    // re-scan it (the engine's in-memory dicts die with the process).
                    context.getSharedPreferences("aurelex", 0).edit().putString("scanPath", scanPath).apply()
                    EngineClient.scanDicts(scanPath).get()
                } catch (e: Exception) {
                    // Engine process not reachable yet (starting/restarting).
                    android.util.Log.e("MainViewModel", "scan engine call failed", e)
                    _indexMessage.value = "Engine not ready — try again in a moment."
                    0
                }
                _dictCount.value += n
                if (n > 0) IndexVersion.markCurrent(context)
                refreshDictionaries()
            } catch (e: Exception) {
                android.util.Log.e("MainViewModel", "pickAndScan failed", e)
                _indexMessage.value = "Scanning failed: ${e.message}"
                n = 0
            } finally {
                _isIndexing.value = false
                onDone(n)
            }
        }
    }

    fun suggest(word: String) {
        if (word.isBlank()) {
            _suggestions.value = emptyList()
            return
        }
        viewModelScope.launch(Dispatchers.IO) {
            _suggestions.value = try {
                EngineClient.suggest(word).get()
            } catch (e: Exception) {
                emptyList()
            }
        }
    }

    /** Reads the current clipboard primary clip text (task 1.2), or null. */
    fun clipboardText(context: android.content.Context): String? {
        return try {
            val cm = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE)
                    as android.content.ClipboardManager
            cm.primaryClip?.takeIf { it.itemCount > 0 }
                ?.getItemAt(0)?.text?.toString()
        } catch (e: Exception) {
            null
        }
    }

    /** Looks up [word], publishes the article and navigates to the article screen. */
    fun lookup(word: String, onDone: ((Dest?) -> Unit)? = null) {
        viewModelScope.launch(Dispatchers.IO) {
            val html = try {
                EngineClient.lookup(word).get()
            } catch (e: Exception) {
                null
            }
            // Upstream article_maker marks found articles with a dictionary body
            // section (gdarticlebody); the (untitled) empty page has none. Use
            // that so the not-found UX (task 5.7) is driven by the engine,
            // not by string heuristics on the Kotlin side.
            val found = html != null && html.contains("gdarticlebody")
            if (found) {
                _article.value = ArticleState(word, html)
                recordHistory(word) // only successful lookups are recorded
            } else {
                _article.value = null
            }
            navigateToArticle()
            onDone?.invoke(if (found) Dest.ARTICLE else null)
        }
    }

    /** Ensures the article screen is on top, without duplicate entries. */
    private fun navigateToArticle() {
        val s = _backStack.value
        if (s.lastOrNull() == Dest.ARTICLE) return
        _backStack.value = s + Dest.ARTICLE
    }

    /** Fetches an embedded resource (bres://) or audio (gdau://) URL. */
    fun fetchResource(url: String): Future<ByteArray?> = EngineClient.getResource(url)

    /**
     * Re-scans the folder staged into app-private storage on a previous
     * pickAndScan. The engine's in-memory dictionaries die with its process,
     * so after an engine restart the app re-runs the scan to restore state.
     */
    fun resumeScan(context: android.content.Context) {
        val prefs = context.getSharedPreferences("aurelex", 0)
        val savePath = prefs.getString("scanPath", null) ?: return
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val n = EngineClient.scanDicts(savePath).get()
                _dictCount.value = n
                refreshDictionaries()
                android.util.Log.i("MainViewModel", "resumeScan($savePath) -> $n")
            } catch (e: Exception) {
                android.util.Log.e("MainViewModel", "resumeScan failed", e)
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
    }
}