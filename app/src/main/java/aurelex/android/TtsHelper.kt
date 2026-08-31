package aurelex.android

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

/**
 * Platform text-to-speech helper (design D3, task 4.1).
 *
 * Lazily initializes a [TextToSpeech] on first use (init is async).
 * [speak] only runs once the engine reports SUCCESS; if init fails or no
 * engine is installed, failure is surfaced via [onUnavailable] instead of
 * crashing. Call [shutdown] from the owning screen's dispose/onDestroy.
 */
class TtsHelper(
    private val context: Context,
    private val onUnavailable: (String) -> Unit,
) {

    private var tts: TextToSpeech? = null
    private var ready = false

    fun speak(text: String) {
        if (text.isBlank()) return
        if (ready) {
            doSpeak(text)
            return
        }
        // Init is async; keep a single shared instance.
        tts = TextToSpeech(context.applicationContext) { status ->
            if (status == TextToSpeech.SUCCESS) {
                ready = true
                doSpeak(text)
            } else {
                onUnavailable("Text-to-speech is unavailable on this device")
            }
        }
    }

    private fun doSpeak(text: String) {
        tts?.let {
            it.language = Locale.getDefault()
            it.speak(text, TextToSpeech.QUEUE_FLUSH, null, "aurelex")
        }
    }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        ready = false
    }
}