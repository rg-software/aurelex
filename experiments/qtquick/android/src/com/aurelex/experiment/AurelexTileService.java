package com.aurelex.experiment;

import android.app.PendingIntent;
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
            // Do NOT read the clipboard here: tile services have no window
            // focus, so clipboard access is unreliable on Android 12+ (the read
            // intermittently returns null). Instead signal the app; it reads
            // the clipboard itself once it has window focus (pollPendingLookup).
            Uri uri = new Uri.Builder()
                    .scheme("aurelex")
                    .authority("lookup")
                    .appendQueryParameter("clipboard", "1")
                    .build();
            Intent intent = new Intent(Intent.ACTION_VIEW, uri, this, ExperimentActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            launchFromTile(intent);

            final Tile t = getQsTile();
            if (t != null) {
                t.setState(Tile.STATE_INACTIVE);
                t.updateTile();
            }
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
