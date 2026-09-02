package com.aurelex.experiment;

import android.app.PendingIntent;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;
import android.util.Log;

/**
 * QS tile: reads the clipboard and opens the app with the word (mirrors the
 * shipped app's QuickLookupTileService). The tile click funnels through
 * ExperimentActivity's aurelex://lookup deep link, which captureLookupText
 * picks up and routes into the engine via readPendingLookup().
 */
public class AurelexTileService extends TileService {
    private static final String TAG = "AurelexTile";

    @Override
    public void onStartListening() {
        final Tile tile = getQsTile();
        if (tile != null) {
            tile.setState(Tile.STATE_INACTIVE);
            tile.updateTile();
        }
    }

    @Override
    public void onClick() {
        final Tile tile = getQsTile();
        if (tile != null) {
            tile.setState(Tile.STATE_ACTIVE);
            tile.updateTile();
        }

        // Run off the main thread: clipboard reads and activity launches from a
        // tile have deadlocked the app's main thread here (service ANR after
        // 200s, window left without an input channel). onClick must return fast.
        new Thread(() -> {
            // Read the clipboard (tile services can read without focus on API 29+).
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            CharSequence text = (cm != null && cm.hasPrimaryClip())
                    ? cm.getPrimaryClip().getItemAt(0).getText() : null;

            final Intent intent;
            if (text == null || text.toString().trim().isEmpty()) {
                // Empty clipboard: just open the app's search screen.
                intent = new Intent(this, ExperimentActivity.class);
            } else {
                // Funnel the word into the app via the aurelex://lookup deep link
                // (ExperimentActivity.captureLookupText picks it up).
                Uri uri = new Uri.Builder()
                        .scheme("aurelex")
                        .authority("lookup")
                        .appendQueryParameter("word", text.toString().trim())
                        .build();
                intent = new Intent(Intent.ACTION_VIEW, uri, this, ExperimentActivity.class);
            }
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            launchFromTile(intent);
        }, "aurelex-tile").start();
    }

    /**
     * API 34+ requires a PendingIntent (the Intent variant is deprecated and
     * plain startActivity() from a tile leaves the shade open without focusing
     * the app on modern Android). startActivityAndCollapse(PendingIntent)
     * collapses the shade and brings the activity forward.
     */
    private void launchFromTile(Intent intent) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            PendingIntent pi = PendingIntent.getActivity(
                    this, 0, intent,
                    PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            startActivityAndCollapse(pi);
        } else {
            //noinspection deprecation
            startActivityAndCollapse(intent);
        }
    }
}
