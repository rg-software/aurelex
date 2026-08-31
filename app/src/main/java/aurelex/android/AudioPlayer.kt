package aurelex.android

import android.content.Context
import android.media.MediaPlayer
import java.io.File

/**
 * Plays pronunciation audio fetched from the engine (design D4/D8).
 *
 * v1 supports ogg/mp3/wav via Android MediaPlayer — no libspeex. `.spx`
 * audio is fetched but reported as unsupported rather than crashing (the
 * lookup spec's graceful-unsupported requirement).
 */
class AudioPlayer(context: Context) {

    private val cacheDir: File = File(context.cacheDir, "audio").apply { mkdirs() }

    /** Guards the single MediaPlayer instance; all calls happen off the UI thread. */
    @Volatile
    private var player: MediaPlayer? = null

    @Volatile
    private var playingUrl: String? = null

    private val supportedExtensions = setOf("ogg", "mp3", "wav")

    /**
     * Plays the audio referenced by a gdau:// URL. Returns an [AudioResult]
     * describing what happened. Non-blocking.
     */
    fun play(url: String, onResult: (AudioResult) -> Unit) {
        val ext = url.substringAfterLast('.', "").lowercase()

        if (ext == "spx") {
            onResult(AudioResult.Unsupported(url, "speex (.spx) is not supported on this device"))
            return
        }
        if (ext.isNotEmpty() && ext !in supportedExtensions) {
            onResult(AudioResult.Unsupported(url, "audio format \"$ext\" is not supported"))
            return
        }

        // Fetch happens on the engine thread; run it synchronously here (caller
        // is expected to be on a background dispatcher).
        val bytes = try {
            EngineClient.getAudio(url).get()
        } catch (e: Exception) {
            null
        }
        if (bytes == null) {
            onResult(AudioResult.Error(url, "audio not found or engine error"))
            return
        }

        stop()

        val file = File(cacheDir, url.hashCode().toString() + ".bin")
        file.writeBytes(bytes)
        playingUrl = url

        try {
            val p = MediaPlayer()
            p.setDataSource(file.absolutePath)
            p.setOnPreparedListener { it.start() }
            p.setOnCompletionListener { release() }
            p.setOnErrorListener { _, what, extra ->
                onResult(AudioResult.Unsupported(url, "player could not decode audio (code $what/$extra)"))
                release()
                true
            }
            p.prepareAsync()
            player = p
            onResult(AudioResult.Playing(url))
        } catch (e: Exception) {
            release()
            onResult(AudioResult.Error(url, "init failed: ${e.message}"))
        }
    }

    /** Stops current playback without tearing the player down for reuse. */
    fun stop() {
        player?.let {
            try {
                if (it.isPlaying) it.stop()
                it.reset()
            } catch (_: Exception) {
            }
        }
    }

    private fun release() {
        try {
            player?.release()
        } catch (_: Exception) {
        }
        player = null
        playingUrl = null
    }
}

sealed class AudioResult(val url: String) {
    class Playing(url: String) : AudioResult(url)
    class Unsupported(url: String, val reason: String) : AudioResult(url)
    class Error(url: String, val message: String) : AudioResult(url)
}