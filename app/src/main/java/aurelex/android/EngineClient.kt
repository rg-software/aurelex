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

    private fun callBytes(op: Int, build: (Bundle) -> Unit): ByteArray? =
        request(op, build) { it.getByteArray("bytes") }
}
