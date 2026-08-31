package aurelex.android

import android.content.Context
import android.os.Handler
import android.os.Looper
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.Future

/**
 * Kotlin-facing facade over the gd_* C API (design D2), loaded as libaurelex.so.
 *
 * Qt on Android requires its application object (QCoreApplication, built inside
 * gd_init) to be constructed on the MAIN thread — building it on a background
 * thread corrupts the Android framework integration and breaks Compose
 * rendering. So gd_init is run synchronously on the main thread, while the
 * blocking lookup/scan/suggest calls run on a dedicated engine thread (Qt
 * objects created on main are used from that thread; the C boundary serializes
 * them with a mutex).
 */
object NativeEngine {
    init {
        System.loadLibrary("aurelex")
    }

    /** Single thread that owns the engine. Blocking native calls run here, in order. */
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
     * Initializes the engine (idempotent at the C boundary). Runs gd_init on
     * the MAIN thread; when already on main it runs inline, otherwise it is
     * posted to the main looper and we block until done. Call at app start.
     */
    fun init(context: Context) {
        if (initialized) return
        val files = context.filesDir.absolutePath
        if (Looper.myLooper() == Looper.getMainLooper()) {
            nativeInit(files, files)
            initialized = true
        } else {
            val lock = Object()
            var done = false
            Handler(Looper.getMainLooper()).post {
                try {
                    nativeInit(files, files)
                    initialized = true
                } finally {
                    synchronized(lock) {
                        done = true
                        lock.notifyAll()
                    }
                }
            }
            synchronized(lock) {
                while (!done) lock.wait()
            }
        }
    }

    /** Scan [folder] for supported dictionaries, building/validating indexes. */
    fun scanDicts(folder: String): Future<Int> = submit { awaitInit(); nativeScanDicts(folder) }

    /** Prefix/fuzzy headword suggestions, newline-separated from native. */
    fun suggest(word: String): Future<List<String>> = submit {
        awaitInit()
        nativeSuggest(word)
            .split('\n')
            .filter { it.isNotBlank() }
    }

    /** Full article HTML for [word], or null if not found / engine error. */
    fun lookup(word: String): Future<String?> = submit {
        awaitInit()
        nativeLookup(word)?.let { it.toString(Charsets.UTF_8) }
    }

    /** Embedded resource bytes (image/audio) for a bres:// or gdau:// URL. */
    fun getResource(url: String): Future<ByteArray?> = submit { awaitInit(); nativeGetResource(url) }

    /** Audio bytes for a gdau:// URL. */
    fun getAudio(url: String): Future<ByteArray?> = submit { awaitInit(); nativeGetAudio(url) }

    /** Number of loaded dictionaries. */
    fun dictCount(): Future<Int> = submit { awaitInit(); nativeDictCount() }

    /** Metadata ([name, source file]) for each loaded dictionary, in order. */
    fun dictInfo(): Future<List<Pair<String, String>>> = submit {
        awaitInit()
        nativeDictInfo().mapNotNull { pair ->
            if (pair.size >= 2) pair[0] to pair[1] else null
        }
    }

    /** Move a dictionary in the single-group order; returns 0 on success. */
    fun moveDict(from: Int, to: Int): Future<Int> = submit { awaitInit(); nativeMoveDict(from, to) }

    /** Toggle article dark mode (engine-emitted CSS); returns 0 on success. */
    fun setDarkMode(on: Boolean): Future<Int> = submit { awaitInit(); nativeSetDarkMode(on) }

    /** Queues engine teardown. Safe to call once at process exit. */
    fun cleanup() {
        submit {
            if (initialized) {
                nativeCleanup()
                initialized = false
            }
        }
    }

    /** Blocks (bounded) until gd_init on the main thread has completed. */
    private fun awaitInit() {
        if (initialized) return
        val deadline = System.currentTimeMillis() + 30_000
        while (!initialized && System.currentTimeMillis() < deadline) {
            try {
                Thread.sleep(50)
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
                return
            }
        }
    }

    private fun <T> submit(block: () -> T): Future<T> =
        engine.submit(java.util.concurrent.Callable<T> { block() })
}