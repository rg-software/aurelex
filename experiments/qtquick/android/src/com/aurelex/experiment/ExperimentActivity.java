package com.aurelex.experiment;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;

import org.qtproject.qt.android.bindings.QtActivity;

/**
 * Gate-3 + M6 bridge: the QtActivity subclass captures incoming lookup intents
 * (share sheet / aurelex:// / PROCESS_TEXT) and writes the word into a
 * SharedPreferences file the Qt side can read at startup and on resume.
 *
 * The Qt side (EngineController.readPendingLookup) polls this file when the
 * app resumes and clears it after consuming. This mirrors the shipped app's
 * MainActivity.handleLookupIntent routing, minus the direct engine call (the
 * Qt process owns the engine here).
 */
public class ExperimentActivity extends QtActivity {
    private static final String TAG = "AurelexExp";

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Workaround for QTBUG-122886 (Qt 6.6): QtActivityDelegate's display
        // listener fires setActivityDisplayRotation on a null mLayout when a
        // display change races with activity teardown. The NPE is harmless but
        // kills the process. Swallow it until we upgrade to Qt 6.7+.
        // NOTE: must be set AFTER super.onCreate() because Qt's own setup
        // installs its own default handler which would overwrite ours.
        final Thread.UncaughtExceptionHandler defaultHandler =
                Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread, throwable) -> {
            if (throwable instanceof NullPointerException
                    && throwable.getMessage() != null
                    && throwable.getMessage().contains("setActivityDisplayRotation")) {
                android.util.Log.w(TAG, "Swallowed QTBUG-122886 display-rotation NPE");
                return; // don't crash
            }
            if (defaultHandler != null) defaultHandler.uncaughtException(thread, throwable);
        });

        captureLookupText(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        captureLookupText(intent);
    }

    private void captureLookupText(Intent intent) {
        if (intent == null) return;
        final SharedPreferences prefs = getSharedPreferences("intent", Context.MODE_PRIVATE);
        String word = null;
        final String action = intent.getAction();
        if (Intent.ACTION_SEND.equals(action)) {
            word = intent.getStringExtra(Intent.EXTRA_TEXT);
            if (word == null) word = intent.getStringExtra(Intent.EXTRA_SUBJECT);
        } else if (Intent.ACTION_VIEW.equals(action)) {
            final android.net.Uri uri = intent.getData();
            if (uri != null) {
                // Tile funnel: no word in the URI; the app reads the clipboard
                // itself once it has window focus (tile services can't reliably).
                if ("1".equals(uri.getQueryParameter("clipboard"))) {
                    // clear(): the in-memory prefs cache must not resurrect
                    // stale keys into later captures; commit(): synchronous, so
                    // the C++ poller never races a half-written file.
                    prefs.edit().clear().putBoolean("lookupClipboard", true).commit();
                    android.util.Log.i(TAG, "captured clipboard-lookup request");
                    return;
                }
                word = uri.getQueryParameter("word");
                if (word == null) word = uri.getPath();
                if (word != null) word = word.replaceFirst("^/", "");
            }
        } else if (Intent.ACTION_PROCESS_TEXT.equals(action)) {
            final CharSequence cs = intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT);
            if (cs != null) word = cs.toString();
        }
        if (word == null) return;
        word = word.trim();
        if (word.isEmpty()) return;
        prefs.edit().clear().putString("lookupText", word).commit();
        android.util.Log.i(TAG, "captured lookup text: " + word);
    }
}