package aurelex.android

import android.app.PendingIntent
import android.content.Intent
import android.service.quicksettings.TileService

/**
 * Quick Settings tile: looks up the current clipboard text. The clipboard is
 * read by [MainActivity] (not here) once the tile collapses the shade, because
 * reading the clipboard while the app is in the background is restricted on
 * Android 10+ (design D1).
 */
class QuickLookupTileService : TileService() {

    override fun onClick() {
        // Don't launch anything while the device is locked — the shade would
        // collapse to an unusable screen. State stays at the system defaults;
        // we never toggle qsTile.state ourselves (task 2.2).
        if (isLocked) return
        val intent = Intent(this, MainActivity::class.java).apply {
            action = QuickLookup.ACTION_LOOKUP_CLIPBOARD
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        // PendingIntent overload: the Intent overload is forbidden on SDK 35+
        // (throws UnsupportedOperationException), which would crash the tile.
        val pending = PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        startActivityAndCollapse(pending)
    }
}