package com.aurelex.experiment;

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

        // Read the clipboard (tile services can read without focus on API 29+).
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        CharSequence text = (cm != null && cm.hasPrimaryClip())
                ? cm.getPrimaryClip().getItemAt(0).getText() : null;
        if (text == null || text.toString().trim().isEmpty()) {
            // Empty clipboard: just open the app's search screen.
            Intent open = new Intent(this, ExperimentActivity.class);
            open.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
            startActivity(open);
            return;
        }

        // Funnel the word into the app via the aurelex://lookup deep link
        // (ExperimentActivity.captureLookupText picks it up).
        Uri uri = new Uri.Builder()
                .scheme("aurelex")
                .authority("lookup")
                .appendQueryParameter("word", text.toString().trim())
                .build();
        Intent lookup = new Intent(Intent.ACTION_VIEW, uri, this, ExperimentActivity.class);
        lookup.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(lookup);
    }
}
