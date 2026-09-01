package aurelex.android

/**
 * Shared action/extra constants for the launcher shortcuts (Quick Settings tile
 * and home-screen widget). Both surfaces funnel into
 * [MainActivity.handleLookupIntent] via these custom actions (design D1/D2).
 */
object QuickLookup {
    /** Tile action: MainActivity reads the clipboard itself (Android 10+ restriction). */
    const val ACTION_LOOKUP_CLIPBOARD = "aurelex.android.action.LOOKUP_CLIPBOARD"

    /** Widget action: MainActivity looks up the text carried in [EXTRA_TEXT]. */
    const val ACTION_SEARCH = "aurelex.android.action.SEARCH"

    /** Text web for [ACTION_SEARCH]; blank means "open the search screen". */
    const val EXTRA_TEXT = "aurelex.android.extra.TEXT"

    /** Re-wires the widget's RemoteViews after it has been interacted with. */
    const val ACTION_REFRESH_WIDGET = "aurelex.android.action.REFRESH_WIDGET"
}