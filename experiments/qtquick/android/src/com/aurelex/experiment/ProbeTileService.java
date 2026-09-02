package com.aurelex.experiment;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.IBinder;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;
import android.util.Log;

/**
 * Gate 3 probe: proves our Java shell components (QS tile / widget / SAF host)
 * coexist with the Qt Quick UI in the same process. Mirrors the shipped app's
 * QuickLookupTileService shape so the result carries over to the port.
 */
public class ProbeTileService extends TileService {
    private static final String TAG = "AurelexProbe";

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "TileService onCreate pid=" + android.os.Process.myPid());
    }

    @Override
    public void onTileAdded() {
        super.onTileAdded();
        Log.i(TAG, "onTileAdded");
        updateTile(true);
    }

    @Override
    public void onStartListening() {
        super.onStartListening();
        Log.i(TAG, "onStartListening (tile visible)");
        updateTile(true);
    }

    @Override
    public void onStopListening() {
        super.onStopListening();
        Log.i(TAG, "onStopListening");
    }

    @Override
    public void onClick() {
        super.onClick();
        Log.i(TAG, "Tile clicked");
        // Mirror the shipped tile: remember an "action happened" marker. A full
        // port would funnel into the QML app via an intent with the clipboard.
        SharedPreferences prefs = getSharedPreferences("probe", MODE_PRIVATE);
        prefs.edit().putLong("lastClick", System.currentTimeMillis()).apply();
        updateTile(false);
    }

    @Override
    public IBinder onBind(Intent intent) {
        return super.onBind(intent);
    }

    private void updateTile(boolean active) {
        Tile tile = getQsTile();
        if (tile == null) return;
        tile.setState(active ? Tile.STATE_ACTIVE : Tile.STATE_INACTIVE);
        tile.updateTile();
    }
}