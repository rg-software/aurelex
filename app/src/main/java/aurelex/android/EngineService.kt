package aurelex.android

import android.app.Service
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Message
import android.os.Messenger
import android.util.Log

/**
 * Hosts the dictionary engine in its own Android process (`:engine`, see the
 * manifest's android:process).
 *
 * Rationale (design D-revised): the engine links the Qt android libraries
 * (libQt6Core/Gui/Widgets). Merely dlopen-ing those into an app process that
 * also runs Compose breaks HWUI frame production (the UI freezes blank).
 * Running the engine in a separate process keeps Compose and the Qt libs in
 * different processes. The UI talks to this service over Binder (Messenger),
 * which is reliable multi-process IPC for a same-app pair (unlike local
 * sockets, whose naming proved unreliable on-device).
 *
 * This service loads libaurelex.so + runs gd_init (on the main thread, as Qt
 * requires), then answers gd_* requests delivered as Messages via Messenger.
 */
class EngineService : Service() {

    private val handler = object : Handler(Looper.getMainLooper()) {
        override fun handleMessage(msg: Message) {
            val op = msg.what
            val replyTarget: Messenger = msg.replyTo ?: return
            val bundle = msg.data

            // Run the engine request on the engine thread (NativeEngine's
            // single executor) so we never block this (engine) process's main
            // looper, then send the result back to the caller via replyTarget.
            val task = when (op) {
                OP_SCAN -> Runnable { sendInt(replyTarget, NativeEngine.scanDicts(bundle.getString("arg0", "")).get()) }
                OP_SUGGEST -> Runnable {
                    val list = NativeEngine.suggest(bundle.getString("arg0", "")).get()
                    sendBytes(replyTarget, list.joinToString("\n").toByteArray())
                }
                OP_LOOKUP -> Runnable {
                    val html = NativeEngine.lookup(bundle.getString("arg0", "")).get()
                    sendBytes(replyTarget, html?.toByteArray(Charsets.UTF_8))
                }
                OP_GET_RESOURCE -> Runnable { sendBytes(replyTarget, NativeEngine.getResource(bundle.getString("arg0", "")).get()) }
                OP_GET_AUDIO -> Runnable { sendBytes(replyTarget, NativeEngine.getAudio(bundle.getString("arg0", "")).get()) }
                OP_DICT_COUNT -> Runnable { sendInt(replyTarget, NativeEngine.dictCount().get()) }
                OP_DICT_INFO -> Runnable {
                    val info = NativeEngine.dictInfo().get()
                    val sb = StringBuilder()
                    info.forEach { (name, file) -> sb.append(name).append('\n').append(file).append('\n') }
                    sendBytes(replyTarget, sb.toString().toByteArray(Charsets.UTF_8))
                }
                OP_MOVE_DICT -> Runnable { sendInt(replyTarget, NativeEngine.moveDict(bundle.getInt("from"), bundle.getInt("to")).get()) }
                OP_SET_DARK -> Runnable { sendInt(replyTarget, NativeEngine.setDarkMode(bundle.getBoolean("on")).get()) }
                OP_GROUP_COUNT -> Runnable { sendInt(replyTarget, NativeEngine.groupCount().get()) }
                OP_GROUP_INFO -> Runnable {
                    val info = NativeEngine.groupInfo().get()
                    val sb = StringBuilder()
                    info.forEach { (id, name, cnt) -> sb.append(id).append('\n').append(name).append('\n').append(cnt).append('\n') }
                    sendBytes(replyTarget, sb.toString().toByteArray(Charsets.UTF_8))
                }
                OP_GROUP_CREATE -> Runnable { sendInt(replyTarget, NativeEngine.groupCreate(bundle.getString("name", "")).get()) }
                OP_GROUP_RENAME -> Runnable { sendInt(replyTarget, NativeEngine.groupRename(bundle.getInt("id"), bundle.getString("name", "")).get()) }
                OP_GROUP_DELETE -> Runnable { sendInt(replyTarget, NativeEngine.groupDelete(bundle.getInt("id")).get()) }
                OP_GROUP_ADD_DICT -> Runnable { sendInt(replyTarget, NativeEngine.groupAddDict(bundle.getInt("id"), bundle.getInt("idx")).get()) }
                OP_GROUP_REMOVE_DICT -> Runnable { sendInt(replyTarget, NativeEngine.groupRemoveDict(bundle.getInt("id"), bundle.getInt("idx")).get()) }
                OP_GROUP_MOVE_DICT -> Runnable { sendInt(replyTarget, NativeEngine.groupMoveDict(bundle.getInt("id"), bundle.getInt("from"), bundle.getInt("to")).get()) }
                OP_GROUP_DICTS -> Runnable {
                    val list = NativeEngine.groupDicts(bundle.getInt("id")).get()
                    sendInts(replyTarget, list.toIntArray())
                }
                OP_GROUP_ACTIVE -> Runnable { sendInt(replyTarget, NativeEngine.groupActive().get()) }
                OP_GROUP_SET_ACTIVE -> Runnable { sendInt(replyTarget, NativeEngine.groupSetActive(bundle.getInt("id")).get()) }
                OP_FTS_INDEX -> Runnable { sendInt(replyTarget, NativeEngine.ftsIndex(bundle.getInt("dictIndex")).get()) }
                OP_FTS_INDEX_STATE -> Runnable { sendInt(replyTarget, NativeEngine.ftsIndexState(bundle.getInt("dictIndex")).get()) }
                OP_FTS_SEARCH -> Runnable {
                    val results = NativeEngine.ftsSearch(
                        bundle.getString("query", ""),
                        bundle.getInt("mode"),
                        bundle.getInt("groupId")
                    ).get()
                    val sb = StringBuilder()
                    results.forEach { (headword, dictId) -> sb.append(headword).append('\t').append(dictId).append('\n') }
                    sendBytes(replyTarget, sb.toString().toByteArray(Charsets.UTF_8))
                }
                else -> return
            }
            engineExecutor.execute {
                try {
                    task.run()
                } catch (e: Exception) {
                    Log.e(TAG, "engine op $op failed", e)
                    val reply = Message.obtain(null, MSG_RESULT)
                    try {
                        replyTarget.send(reply.apply { data = Bundle().apply { putBoolean("error", true); putString("message", e.message ?: "engine error") } })
                    } catch (_: Exception) {
                    }
                }
            }
        }
    }

    private val messenger: Messenger = Messenger(handler)

    private fun sendInt(replyTarget: Messenger, value: Int) {
        sendInts(replyTarget, intArrayOf(value))
    }

    private fun sendInts(replyTarget: Messenger, values: IntArray) {
        val reply = Message.obtain(null, MSG_RESULT)
        reply.data = Bundle().apply { putIntArray("value", values) }
        try {
            replyTarget.send(reply)
        } catch (_: Exception) {
        }
    }

    private fun sendBytes(replyTarget: Messenger, data: ByteArray?) {
        val reply = Message.obtain(null, MSG_RESULT)
        reply.data = Bundle().apply { putByteArray("bytes", data) }
        try {
            replyTarget.send(reply)
        } catch (_: Exception) {
        }
    }

    private val engineExecutor = java.util.concurrent.Executors.newSingleThreadExecutor { r ->
        Thread(r, "aurelex-engine-worker").apply { isDaemon = true }
    }

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "onCreate: loading engine + gd_init")
        // Foreground so the engine process survives UI activity recreation /
        // SAF grant restarts. startForeground() must be called quickly.
        val nc = android.app.NotificationChannel(
            CHANNEL_ID, "Dictionary engine", android.app.NotificationManager.IMPORTANCE_LOW
        )
        getSystemService(android.app.NotificationManager::class.java).createNotificationChannel(nc)
        val notif = android.app.Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("Aurelex engine")
            .setContentText("Dictionary engine running")
            .setSmallIcon(android.R.drawable.ic_menu_search)
            .build()
        startForeground(NOTIF_ID, notif)

        NativeEngine.init(this)
        Log.i(TAG, "onCreate: gd_init done")
    }

    override fun onBind(intent: Intent?): IBinder? = messenger.binder

    companion object {
        private const val TAG = "AurelexEngine"
        private const val CHANNEL_ID = "aurelex_engine"
        private const val NOTIF_ID = 1001

        // Shared with EngineClient.
        const val OP_SCAN = 1
        const val OP_SUGGEST = 2
        const val OP_LOOKUP = 3
        const val OP_GET_RESOURCE = 4
        const val OP_GET_AUDIO = 5
        const val OP_DICT_COUNT = 6
        const val OP_DICT_INFO = 7
        const val OP_MOVE_DICT = 8
        const val OP_SET_DARK = 9
        const val OP_GROUP_COUNT = 20
        const val OP_GROUP_INFO = 21
        const val OP_GROUP_CREATE = 22
        const val OP_GROUP_RENAME = 23
        const val OP_GROUP_DELETE = 24
        const val OP_GROUP_ADD_DICT = 25
        const val OP_GROUP_REMOVE_DICT = 26
        const val OP_GROUP_MOVE_DICT = 27
        const val OP_GROUP_DICTS = 30
        const val OP_GROUP_ACTIVE = 28
        const val OP_GROUP_SET_ACTIVE = 29
        // full-text search (xapian)
        const val OP_FTS_INDEX = 40
        const val OP_FTS_INDEX_STATE = 41
        const val OP_FTS_SEARCH = 42

        const val MSG_RESULT = 100
    }
}
