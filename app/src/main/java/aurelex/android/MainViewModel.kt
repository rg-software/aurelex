package aurelex.android

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.util.concurrent.Future

/** Single-activity navigation destinations (task 3.2). */
enum class Dest { SEARCH, ARTICLE, DICTIONARIES }

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

    data class DictEntry(val name: String, val file: String)

    private val _dictionaries = MutableStateFlow<List<DictEntry>>(emptyList())
    val dictionaries: StateFlow<List<DictEntry>> = _dictionaries

    private fun refreshDictionaries() {
        _dictionaries.value = NativeEngine.dictInfo().get().map { DictEntry(it.first, it.second) }
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

    /** Queues engine init on the engine thread (idempotent). Call from the app. */
    fun init(context: android.content.Context) = NativeEngine.init(context)

    /** Scans [folder] for dictionaries; [onDone] runs with the load count. */
    fun scanDicts(folder: String, onDone: (Int) -> Unit) {
        viewModelScope.launch(Dispatchers.IO) {
            val n = NativeEngine.scanDicts(folder).get()
            _dictCount.value += n
            refreshDictionaries()
            onDone(n)
        }
    }

    /** Moves dictionary at [from] to [to] in the single group; refreshes list. */
    fun moveDict(from: Int, to: Int) {
        viewModelScope.launch(Dispatchers.IO) {
            if (NativeEngine.moveDict(from, to).get() == 0) {
                refreshDictionaries()
            }
        }
    }

    /** Toggles article dark mode (task 7.1); re-looks-up so the CSS is re-emitted. */
    fun toggleDarkMode(word: String?) {
        viewModelScope.launch(Dispatchers.IO) {
            val next = !_darkMode.value
            NativeEngine.setDarkMode(next).get()
            _darkMode.value = next
            word?.let { lookup(it) }
        }
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

            if (!IndexVersion.isCurrent(context)) {
                IndexVersion.invalidate(context)
                _indexMessage.value = "Reindexing dictionaries (engine version changed)…"
            }

            try {
                val resolvedPath = SafResolver.resolveTreePath(treeUri)
                val scanPath = if (resolvedPath != null) {
                    resolvedPath
                } else {
                    val dest = java.io.File(context.filesDir, "staged").apply { mkdirs() }
                    SafResolver.stageDictionaryFiles(context, treeUri, dest).absolutePath
                }
                val n = NativeEngine.scanDicts(scanPath).get()
                _dictCount.value += n
                if (n > 0) IndexVersion.markCurrent(context)
                refreshDictionaries()
                onDone(n)
            } finally {
                _isIndexing.value = false
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
                NativeEngine.suggest(word).get()
            } catch (e: Exception) {
                emptyList()
            }
        }
    }

    /** Looks up [word], publishes the article and navigates to the article screen. */
    fun lookup(word: String, onDone: ((Dest?) -> Unit)? = null) {
        viewModelScope.launch(Dispatchers.IO) {
            val html = try {
                NativeEngine.lookup(word).get()
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
    fun fetchResource(url: String): Future<ByteArray?> = NativeEngine.getResource(url)

    override fun onCleared() {
        NativeEngine.cleanup()
        super.onCleared()
    }
}