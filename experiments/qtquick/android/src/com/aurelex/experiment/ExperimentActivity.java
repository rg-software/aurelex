package com.aurelex.experiment;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.media.MediaPlayer;
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

    private static MediaPlayer sAudioPlayer = null;

    /**
     * Plays pronunciation audio from the loopback ArticleServer URL
     * (http://127.0.0.1:PORT/gdau/<dictId>/<file>.wav). Mirrors the shipped
     * app's AudioPlayer (MediaPlayer backend, wav/ogg/mp3; speex unsupported).
     * Called from the native side via QAndroidJniObject on the UI thread.
     */
    public static void playAudio(String url) {
        try {
            if (sAudioPlayer != null) {
                stopAudio();
            }
            if (url == null || url.isEmpty()) {
                return;
            }
            if (url.endsWith(".spx")) {
                android.util.Log.w(TAG, "speex audio unsupported: " + url);
                return;
            }
            final MediaPlayer p = new MediaPlayer();
            p.setDataSource(url);
            p.setOnPreparedListener(mp -> mp.start());
            p.setOnCompletionListener(mp -> releaseAudioPlayer());
            p.setOnErrorListener((mp, what, extra) -> {
                android.util.Log.e(TAG, "MediaPlayer error " + what + "/" + extra + " for " + url);
                releaseAudioPlayer();
                return true;
            });
            p.prepareAsync();
            sAudioPlayer = p;
            android.util.Log.i(TAG, "playing " + url);
        } catch (Exception e) {
            android.util.Log.e(TAG, "playAudio failed: " + e);
        }
    }

    public static void stopAudio() {
        try {
            if (sAudioPlayer != null) {
                sAudioPlayer.stop();
                releaseAudioPlayer();
            }
        } catch (Exception e) {
            android.util.Log.w(TAG, "stopAudio: " + e);
        }
    }

    private static void releaseAudioPlayer() {
        try {
            if (sAudioPlayer != null) sAudioPlayer.release();
        } catch (Exception ignored) {
        }
        sAudioPlayer = null;
    }

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

    @Override
    protected void onResume() {
        super.onResume();
        // Qt 6.6 on Android 14+: the QtEditText InputConnection can bind
        // INACTIVE ("getExtractedText on inactive InputConnection"); IME
        // composing then gets swallowed/reset by the keyboard (text appears
        // and instantly vanishes). Force a re-bind shortly after resume.
        new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(this::restartQtInput, 400);
    }

    private void restartQtInput() {
        try {
            android.view.View focused = getCurrentFocus();
            if (focused == null) {
                android.util.Log.i(TAG, "restartQtInput: no focused view");
                return;
            }
            android.view.inputmethod.InputMethodManager imm =
                    (android.view.inputmethod.InputMethodManager)
                            getSystemService(INPUT_METHOD_SERVICE);
            imm.restartInput(focused);
            android.util.Log.i(TAG, "restarted IME input connection for " + focused.getClass().getName());
        } catch (Exception e) {
            android.util.Log.w(TAG, "restartQtInput failed: " + e);
        }
    }

    @Override
    protected void onDestroy() {
        // Qt 6.6 cannot start the Qt app a second time in the same process:
        // the second startApplication blocks forever on QtThread's semaphore
        // (QtLayout.onSizeChanged -> QtNative.startApplication -> Semaphore
        // .acquire). Task removal (swipe-away from recents) destroys the
        // activity but leaves the process cached, so a relaunch would resume
        // this doomed process and freeze on the splash screen forever.
        // Kill the process here so every relaunch is a clean start.
        android.util.Log.w(TAG, "onDestroy: terminating process (Qt 6.6 cannot restart Qt in-process)");
        android.os.Process.killProcess(android.os.Process.myPid());
        System.exit(0);
        super.onDestroy();
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