package aurelex.android

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit

/**
 * Single persistence layer over SharedPreferences (design D4, task 5.1).
 * Owns the user's data-store: dark-mode toggle, TTS toggle, lookup history
 * and favorites. Loaded at app startup, written on change.
 */
class PreferencesStore(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences("aurelex", Context.MODE_PRIVATE)

    // --- dark mode ---
    var darkMode: Boolean
        get() = prefs.getBoolean(KEY_DARK, false)
        set(value) = prefs.edit { putBoolean(KEY_DARK, value) }

    // --- TTS ---
    var ttsEnabled: Boolean
        get() = prefs.getBoolean(KEY_TTS, true)
        set(value) = prefs.edit { putBoolean(KEY_TTS, value) }

    // --- history ---
    val history: List<String>
        get() = prefs.getString(KEY_HISTORY, null)
            ?.split(HISTORY_SEP)
            ?.filter { it.isNotBlank() }
            ?: emptyList()

    /** Move [word] to front, de-duplicating; cap at [cap] entries. */
    fun addHistory(word: String, cap: Int = 100) {
        val current = history
        val updated = (listOf(word) + current.filter { it != word }).take(cap)
        prefs.edit { putString(KEY_HISTORY, updated.joinToString(HISTORY_SEP)) }
    }

    fun removeHistory(word: String) {
        val updated = history.filter { it != word }
        prefs.edit { putString(KEY_HISTORY, updated.joinToString(HISTORY_SEP)) }
    }

    fun clearHistory() {
        prefs.edit { remove(KEY_HISTORY) }
    }

    // --- favorites (insertion-ordered) ---
    val favorites: List<String>
        get() = prefs.getString(KEY_FAVORITES, null)
            ?.split(FAVORITES_SEP)
            ?.filter { it.isNotBlank() }
            ?: emptyList()

    fun addFavorite(word: String) {
        if (favorites.contains(word)) return
        val updated = favorites + word
        prefs.edit { putString(KEY_FAVORITES, updated.joinToString(FAVORITES_SEP)) }
    }

    fun removeFavorite(word: String) {
        val updated = favorites.filter { it != word }
        prefs.edit { putString(KEY_FAVORITES, updated.joinToString(FAVORITES_SEP)) }
    }

    fun isFavorite(word: String): Boolean = favorites.contains(word)

    companion object {
        private const val KEY_DARK = "darkMode"
        private const val KEY_TTS = "ttsEnabled"
        private const val KEY_HISTORY = "history"
        private const val KEY_FAVORITES = "favorites"
        private const val HISTORY_SEP = "\u0001"
        private const val FAVORITES_SEP = "\u0001"
    }
}