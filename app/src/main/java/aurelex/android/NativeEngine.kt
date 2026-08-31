package aurelex.android

import android.content.Context
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.Future

/**
 * Kotlin-facing facade over the gd_* C API (design D2), loaded as libaurelex.so.
 *
 * Every native call — including init and cleanup — is submitted to a single
 * dedicated engine thread. This is required, not just nice: gd_init constructs
 * a QGuiApplication and Qt objects are thread-affine, so all engine work (and
 * the event loops the C boundary pumps) must live on one thread.
 */
object NativeEngine {
    init {
        System.loadLibrary("aurelex")
    }

    /** Single thread that owns the engine. All native calls run here, in order. */
    private val engine: ExecutorService = Executors.newSingleThreadExecutor { r ->
        Thread(r, "aurelex-engine").apply { isDaemon = true }
    }

    @Volatile
    private var initialized = false

    private external fun nativeInit(configDir: String, indexDir: String)
    private external fun nativeScanDicts(folder: String): Int
    private external fun nativeSuggest(word: String): String
    private external fun nativeLookup(word: String): ByteArray?
    private external fun nativeGetResource(url: String): ByteArray?
    private external fun nativeGetAudio(url: String): ByteArray?
    private external fun nativeDictCount(): Int
    private external fun nativeDictInfo(): Array<Array<String>>
    private external fun nativeMoveDict(from: Int, to: Int): Int
    private external fun nativeSetDarkMode(on: Boolean): Int
    private external fun nativeCleanup()

    /**
     * Queues engine init (idempotent at the C boundary). Must be called at
     * app start with the app Context.
     */
    fun init(context: Context) {
        submit {
            if (!initialized) {
                val files = context.filesDir.absolutePath
                nativeInit(files, files)
                initialized = true
            }
        }
    }

    /** Scan [folder] for supported dictionaries, building/validating indexes. */
    fun scanDicts(folder: String): Future<Int> = submit { nativeScanDicts(folder) }

    /** Prefix/fuzzy headword suggestions, newline-separated from native. */
    fun suggest(word: String): Future<List<String>> = submit {
        nativeSuggest(word)
            .split('\n')
            .filter { it.isNotBlank() }
    }

    /** Full article HTML for [word], or null if not found / engine error. */
    fun lookup(word: String): Future<String?> = submit {
        nativeLookup(word)?.let { it.toString(Charsets.UTF_8) }
    }

    /** Embedded resource bytes (image/audio) for a bres:// or gdau:// URL. */
    fun getResource(url: String): Future<ByteArray?> = submit { nativeGetResource(url) }

    /** Audio bytes for a gdau:// URL. */
    fun getAudio(url: String): Future<ByteArray?> = submit { nativeGetAudio(url) }

    /** Number of loaded dictionaries. */
    fun dictCount(): Future<Int> = submit { nativeDictCount() }

    /** Metadata ([name, source file]) for each loaded dictionary, in order. */
    fun dictInfo(): Future<List<Pair<String, String>>> = submit {
        nativeDictInfo().mapNotNull { pair ->
            if (pair.size >= 2) pair[0] to pair[1] else null
        }
    }

    /** Move a dictionary in the single-group order; returns 0 on success. */
    fun moveDict(from: Int, to: Int): Future<Int> = submit { nativeMoveDict(from, to) }

    /** Toggle article dark mode (engine-emitted CSS); returns 0 on success. */
    fun setDarkMode(on: Boolean): Future<Int> = submit { nativeSetDarkMode(on) }

    /** Queues engine teardown. Safe to call once at process exit. */
    fun cleanup() {
        submit {
            if (initialized) {
                nativeCleanup()
                initialized = false
            }
        }
    }

    private fun <T> submit(block: () -> T): Future<T> =
        engine.submit(block as java.util.concurrent.Callable<T>)
}