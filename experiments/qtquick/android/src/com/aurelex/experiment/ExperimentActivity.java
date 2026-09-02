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
        String word = null;
        final String action = intent.getAction();
        if (Intent.ACTION_SEND.equals(action)) {
            word = intent.getStringExtra(Intent.EXTRA_TEXT);
            if (word == null) word = intent.getStringExtra(Intent.EXTRA_SUBJECT);
        } else if (Intent.ACTION_VIEW.equals(action)) {
            final android.net.Uri uri = intent.getData();
            if (uri != null) {
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
        final SharedPreferences prefs = getSharedPreferences("intent", Context.MODE_PRIVATE);
        prefs.edit().putString("lookupText", word).apply();
        android.util.Log.i(TAG, "captured lookup text: " + word);
    }
}