package aurelex.android

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Message
import android.os.Messenger
import java.util.concurrent.Callable
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.Future
import java.util.concurrent.TimeUnit

/**
 * UI-process proxy to the engine running in the separate `:engine` process
 * (see EngineService). This process NEVER loads libaurelex.so / the Qt libs,
 * so Compose rendering is unaffected. Calls go over Binder (Messenger), which
 * is reliable multi-process IPC.
 *
 * Mirrors the NativeEngine API (returns [Future]) so the ViewModel is agnostic.
 */
object EngineClient {

    private const val REQUEST_TIMEOUT_MS = 30_000L

    private val io: ExecutorService = Executors.newCachedThreadPool { r ->
        Thread(r, "aurelex-engine-client").apply {
            isDaemon = true
            setUncaughtExceptionHandler { t, e ->
                android.util.Log.e("EngineClient", "uncaught error on ${t.name}", e)
            }
        }
    }

    @Volatile
    private var messenger: Messenger? = null

    @Volatile
    private var bound = false

    /** Invoked when the engine service process dies (onServiceDisconnected). */
    @Volatile
    var onEngineDied: (() -> Unit)? = null
    fun bind(context: Context) {
        if (bound) return
        val success = context.bindService(
            Intent(context, EngineService::class.java),
            object : ServiceConnection {
                override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
                    messenger = Messenger(service)
                    bound = true
                    android.util.Log.i("EngineClient", "bound to engine service")
                }

                override fun onServiceDisconnected(name: ComponentName?) {
                    messenger = null
                    bound = false
                    android.util.Log.w("EngineClient", "engine service died")
                    onEngineDied?.invoke()
                }
            },
            Context.BIND_AUTO_CREATE
        )
        if (!success) android.util.Log.e("EngineClient", "bindService failed")
    }

    /** Waits (bounded) until the service is bound. Called from a worker thread. */
    private fun awaitMessenger(): Messenger {
        val deadline = System.currentTimeMillis() + REQUEST_TIMEOUT_MS
        while (System.currentTimeMillis() < deadline) {
            messenger?.let { return it }
            if (!bound) {
                // maybe service not up yet; keep polling
            }
            try {
                Thread.sleep(100)
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
            }
        }
        throw IllegalStateException("engine service not bound")
    }

    // --- public API (Future-returning, mirroring NativeEngine) ---

    fun scanDicts(folder: String): Future<Int> = submit { callInt(EngineService.OP_SCAN) { it.putString("arg0", folder) } }

    fun suggest(word: String): Future<List<String>> = submit {
        val s = callBytes(EngineService.OP_SUGGEST) { it.putString("arg0", word) }
        s?.toString(Charsets.UTF_8)?.split('\n')?.filter { it.isNotBlank() } ?: emptyList()
    }

    fun lookup(word: String): Future<String?> = submit {
        callBytes(EngineService.OP_LOOKUP) { it.putString("arg0", word) }?.toString(Charsets.UTF_8)
    }

    fun getResource(url: String): Future<ByteArray?> = submit { callBytes(EngineService.OP_GET_RESOURCE) { it.putString("arg0", url) } }
    fun getAudio(url: String): Future<ByteArray?> = submit { callBytes(EngineService.OP_GET_AUDIO) { it.putString("arg0", url) } }
    fun dictCount(): Future<Int> = submit { callInt(EngineService.OP_DICT_COUNT) {} }

    fun dictInfo(): Future<List<Pair<String, String>>> = submit {
        val raw = callBytes(EngineService.OP_DICT_INFO) {} ?: return@submit emptyList()
        val parts = raw.toString(Charsets.UTF_8).split('\n')
        parts.filter { it.isNotBlank() }.chunked(2).mapNotNull { if (it.size >= 2) it[0] to it[1] else null }
    }

    fun moveDict(from: Int, to: Int): Future<Int> = submit {
        callInt(EngineService.OP_MOVE_DICT) { it.putInt("from", from); it.putInt("to", to) }
    }

    fun setDarkMode(on: Boolean): Future<Int> = submit {
        callInt(EngineService.OP_SET_DARK) { it.putBoolean("on", on) }
    }

    // --- groups (multi-group-management) ---

    fun groupCount(): Future<Int> = submit { callInt(EngineService.OP_GROUP_COUNT) {} }

    fun groupInfo(): Future<List<Triple<Int, String, Int>>> = submit {
        val raw = callBytes(EngineService.OP_GROUP_INFO) {} ?: return@submit emptyList()
        val parts = raw.toString(Charsets.UTF_8).split('\n')
        parts.filter { it.isNotBlank() }.chunked(3).mapNotNull {
            if (it.size >= 3) Triple(it[0].toIntOrNull() ?: 0, it[1], it[2].toIntOrNull() ?: 0) else null
        }
    }

    fun groupCreate(name: String): Future<Int> = submit { callInt(EngineService.OP_GROUP_CREATE) { it.putString("name", name) } }
    fun groupRename(id: Int, name: String): Future<Int> = submit { callInt(EngineService.OP_GROUP_RENAME) { it.putInt("id", id); it.putString("name", name) } }
    fun groupDelete(id: Int): Future<Int> = submit { callInt(EngineService.OP_GROUP_DELETE) { it.putInt("id", id) } }
    fun groupAddDict(id: Int, dictIndex: Int): Future<Int> = submit { callInt(EngineService.OP_GROUP_ADD_DICT) { it.putInt("id", id); it.putInt("idx", dictIndex) } }
    fun groupRemoveDict(id: Int, dictIndex: Int): Future<Int> = submit { callInt(EngineService.OP_GROUP_REMOVE_DICT) { it.putInt("id", id); it.putInt("idx", dictIndex) } }
    fun groupMoveDict(id: Int, from: Int, to: Int): Future<Int> = submit { callInt(EngineService.OP_GROUP_MOVE_DICT) { it.putInt("id", id); it.putInt("from", from); it.putInt("to", to) } }
    fun groupDicts(id: Int): Future<List<Int>> = submit {
        callIntArray(EngineService.OP_GROUP_DICTS) { it.putInt("id", id) }?.toList() ?: emptyList()
    }
    fun groupActive(): Future<Int> = submit { callInt(EngineService.OP_GROUP_ACTIVE) {} }
    fun groupSetActive(id: Int): Future<Int> = submit { callInt(EngineService.OP_GROUP_SET_ACTIVE) { it.putInt("id", id) } }

    // --- full-text search (xapian) ---

    /** Full-text search modes, mirroring NativeEngine.FtsMode. */
    object FtsMode {
        const val WHOLE_WORDS = 0
        const val PLAIN_TEXT = 1
        const val WILDCARDS = 2
        const val REGEXP = 3
    }

    /** Index availability for dictionary [dictIndex]: 0 built, 1 missing, -1 unsupported. */
    fun ftsIndexState(dictIndex: Int): Future<Int> = submit {
        callInt(EngineService.OP_FTS_INDEX_STATE) { it.putInt("dictIndex", dictIndex) }
    }

    /** Build/refresh dictionary [dictIndex]'s full-text index; 0 on success. */
    fun ftsIndex(dictIndex: Int): Future<Int> = submit {
        callInt(EngineService.OP_FTS_INDEX) { it.putInt("dictIndex", dictIndex) }
    }

    /** Full-text search across group [groupId] (0 = "All"); returns (headword, dictId). */
    fun ftsSearch(query: String, mode: Int, groupId: Int): Future<List<Pair<String, String>>> = submit {
        val raw = callBytes(EngineService.OP_FTS_SEARCH) {
            it.putString("query", query)
            it.putInt("mode", mode)
            it.putInt("groupId", groupId)
        } ?: return@submit emptyList()
        raw.toString(Charsets.UTF_8)
            .split('\n')
            .filter { it.isNotBlank() }
            .mapNotNull { line ->
                val parts = line.split('\t')
                if (parts.size >= 2) parts[0] to parts[1] else null
            }
    }

    // --- low-level blocking call ---

    private fun <T> submit(block: () -> T): Future<T> = io.submit(Callable<T> { block() })

    private inline fun <T> request(op: Int, build: (Bundle) -> Unit, parse: (Bundle) -> T): T {
        val target = awaitMessenger()
        val latch = java.util.concurrent.CountDownLatch(1)
        val resultBox = java.util.concurrent.atomic.AtomicReference<Any?>()
        val errBox = java.util.concurrent.atomic.AtomicReference<Exception?>()

        val replyHandler = object : Handler(Looper.getMainLooper()) {
            override fun handleMessage(msg: Message) {
                if (msg.what == EngineService.MSG_RESULT) {
                    resultBox.set(msg.data)
                    latch.countDown()
                }
            }
        }
        val replyMessenger = Messenger(replyHandler)

        val b = Bundle()
        build(b)
        val request = Message.obtain(null, op)
        request.data = b
        request.replyTo = replyMessenger
        try {
            target.send(request)
        } catch (e: Exception) {
            errBox.set(e)
            latch.countDown()
        }

        if (!latch.await(REQUEST_TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
            throw IllegalStateException("engine request $op timed out")
        }
        errBox.get()?.let { throw it }
        val data = resultBox.get() as? Bundle ?: throw IllegalStateException("no result for $op")
        if (data.getBoolean("error")) throw RuntimeException(data.getString("message") ?: "engine error")
        return parse(data)
    }

    private fun callInt(op: Int, build: (Bundle) -> Unit): Int =
        request(op, build) { it.getIntArray("value")?.firstOrNull() ?: -1 }

    private fun callIntArray(op: Int, build: (Bundle) -> Unit): IntArray? =
        request(op, build) { it.getIntArray("value") }

    private fun callBytes(op: Int, build: (Bundle) -> Unit): ByteArray? =
        request(op, build) { it.getByteArray("bytes") }
}
