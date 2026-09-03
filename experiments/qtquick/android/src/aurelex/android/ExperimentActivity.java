package aurelex.android;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.Configuration;
import android.media.MediaPlayer;
import android.os.Bundle;

import org.qtproject.qt.android.bindings.QtActivity;
import org.qtproject.qt.android.QtNative;

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

    private static final int REQUEST_PICK_DICTIONARY_FOLDER = 2001;

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

    /**
     * Reports whether the system is in dark mode. Qt 6.6's Android QPA does not
     * surface the system dark/light setting to the Material style, so the C++
     * side (EngineController.readSystemDark) reads it here over JNI via
     * QJniObject — the same pattern as isStorageManager handling.
     */
    public static boolean isNightModeActive() {
        try {
            android.app.Activity activity = QtNative.activity();
            if (activity == null) return false;
            int uiMode = activity.getResources().getConfiguration().uiMode;
            return (uiMode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
        } catch (Exception e) {
            android.util.Log.w(TAG, "isNightModeActive failed: " + e);
            return false;
        }
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        // A live dark/light switch lands here; the C++ poller (EngineController
        // updateSystemDark, 500ms) picks up the new value on its next tick and
        // re-palettes via Material.theme.
        android.util.Log.i(TAG, "configuration changed; night=" + isNightModeActive());
    }

    /**
     * SAF dictionary folder picker (folder-scoped storage, no All-Files-Access).
     * Called from the native side via QJniObject. The result arrives in
     * {@link #onActivityResult}; the picked tree is persisted, resolved (or
     * staged), and written to shared_prefs/source.xml for the C++ poller.
     */
    public static void pickDictionaryFolder() {
        try {
            android.app.Activity activity = QtNative.activity();
            if (activity == null) return;
            android.content.Intent intent =
                    new android.content.Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                    | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                    | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
            activity.startActivityForResult(intent, REQUEST_PICK_DICTIONARY_FOLDER);
        } catch (Exception e) {
            android.util.Log.w(TAG, "pickDictionaryFolder failed: " + e);
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, android.content.Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_PICK_DICTIONARY_FOLDER) return;
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            android.util.Log.i(TAG, "dictionary folder pick cancelled");
            return;
        }
        try {
            final android.net.Uri treeUri = data.getData();
            final android.content.ContentResolver cr = getContentResolver();
            cr.takePersistableUriPermission(treeUri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);

            // ALWAYS stage-copy into app-private storage. Scoped storage blocks
            // direct path reads of /storage/emulated/0 for apps without AFA, so
            // scanning the resolved physical path would find nothing; the engine
            // can only read files the app can reach by path, which means copying
            // the picked tree's supported files through the SAF URIs (the grant
            // we hold) into files/staged/<sourceId>. The resolved path is kept
            // as a display label only.
            final String sourceId = Integer.toHexString(treeUri.toString().hashCode());
            final String stagedDir = new java.io.File(getFilesDir(),
                    "staged/" + sourceId).getAbsolutePath();
            final int copied = stageTree(treeUri, stagedDir);
            if (copied <= 0) {
                android.util.Log.w(TAG, "no supported files staged from " + treeUri);
                return;
            }
            final String display = resolveTreePath(treeUri); // may be empty (cloud)

            // Write the source for the C++ poller (mirrors intent.xml pattern).
            final SharedPreferences prefs = getSharedPreferences("source", Context.MODE_PRIVATE);
            prefs.edit().clear()
                    .putString("sourceUri", treeUri.toString())
                    .putString("sourcePath", stagedDir)
                    .putString("sourceDisplay", display)
                    .putBoolean("sourceStaged", true)
                    .commit();
            android.util.Log.i(TAG, "dictionary source added: " + display
                    + " staged=" + copied + " files into " + stagedDir);
        } catch (Exception e) {
            android.util.Log.w(TAG, "onActivityResult source handling failed: " + e);
        }
    }

    /**
     * Resolves a SAF tree URI to a physical path when the provider allows:
     * - "primary:<rel>" -> /storage/emulated/0/<rel>
     * - "<volume>:<rel>" -> /storage/<volume>/<rel>
     * - anything else (non-'external' provider, no doc id) -> "" (unresolvable;
     *   the caller falls back to staging).
     */
    static String resolveTreePath(android.net.Uri uri) {
        try {
            final String docId = android.provider.DocumentsContract.getTreeDocumentId(uri);
            final int colon = docId.indexOf(':');
            if (colon < 0) return "";
            final String volume = docId.substring(0, colon);
            String rel = docId.substring(colon + 1);
            while (rel.startsWith("/")) rel = rel.substring(1);
            if ("primary".equals(volume)) {
                return "/storage/emulated/0" + (rel.isEmpty() ? "" : "/" + rel);
            }
            return "/storage/" + volume + (rel.isEmpty() ? "" : "/" + rel);
        } catch (Exception e) {
            return "";
        }
    }

    /**
     * Copies the supported dictionary files from a SAF tree into app-private
     * storage INCREMENTALLY, recursing into nested subfolders (relative paths
     * preserved) so the staged copy mirrors the picked folder tree. Files whose
     * destination already exists with the same size and close last-modified time
     * are skipped; copied files get the source's timestamp so a later refresh can
     * compare cheaply. Returns the number of files copied, or -1 on failure.
     */
    static int stageTree(android.net.Uri treeUri, String destDir) {
        final android.content.ContentResolver cr;
        try {
            cr = QtNative.activity().getContentResolver();
        } catch (Exception e) {
            return -1;
        }
        final java.io.File dir = new java.io.File(destDir);
        if (!dir.exists() && !dir.mkdirs()) return -1;
        return stageTreeInto(treeUri, cr, dir);
    }

    private static int stageTreeInto(android.net.Uri treeUri,
                                     android.content.ContentResolver cr,
                                     java.io.File destDir) {
        final String[] cols = {
                android.provider.DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                android.provider.DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                android.provider.DocumentsContract.Document.COLUMN_MIME_TYPE,
                android.provider.DocumentsContract.Document.COLUMN_SIZE,
                android.provider.DocumentsContract.Document.COLUMN_LAST_MODIFIED };
        int copied = 0;
        try {
            final String treeDocId = android.provider.DocumentsContract.getTreeDocumentId(treeUri);
            final android.net.Uri childrenUri =
                    android.provider.DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, treeDocId);
            try (android.database.Cursor c = cr.query(childrenUri, cols, null, null, null)) {
                while (c != null && c.moveToNext()) {
                    final String docId = c.getString(0);
                    final String name = c.getString(1);
                    final String mime = c.getString(2);
                    if (name == null) continue;
                    if (android.provider.DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                        // Recurse into the subfolder, preserving the relative path.
                        final java.io.File sub = new java.io.File(destDir, name);
                        final android.net.Uri subTree = android.provider.DocumentsContract
                                .buildDocumentUriUsingTree(treeUri, docId);
                        copied += stageTreeInto(subTree, cr, sub);
                        continue;
                    }
                    if (!isSupportedDictionaryName(name)) continue;
                    final long srcSize = c.isNull(3) ? -1 : c.getLong(3);
                    final long srcModified = c.isNull(4) ? 0 : c.getLong(4);
                    final java.io.File out = new java.io.File(destDir, name);
                    if (out.exists() && out.isFile()
                            && srcSize >= 0 && out.length() == srcSize
                            && (srcModified <= 0
                                || Math.abs(out.lastModified() - srcModified) < 5000)) {
                        continue; // unchanged since we staged it
                    }
                    final android.net.Uri child = android.provider.DocumentsContract
                            .buildDocumentUriUsingTree(treeUri, docId);
                    try (java.io.InputStream in = cr.openInputStream(child);
                         java.io.FileOutputStream fos = new java.io.FileOutputStream(out)) {
                        final byte[] buf = new byte[64 * 1024];
                        int n;
                        while (in != null && (n = in.read(buf)) > 0) fos.write(buf, 0, n);
                        if (srcModified > 0) out.setLastModified(srcModified);
                        copied++;
                    }
                }
            }
            return copied;
        } catch (Exception e) {
            android.util.Log.w(TAG, "stageTreeInto failed: " + e);
            return copied;
        }
    }

    private static volatile boolean sRefreshRunning = false;

    /**
     * Re-pulls all persisted dictionary sources from their ORIGINAL SAF folders
     * (incremental stageTree), then signals the C++ poller via
     * shared_prefs/refresh.xml so it rescans the refreshed staging. Called from
     * EngineController.rescan() over JNI; the copy runs on a background thread so
     * the UI thread is not blocked on large dictionaries.
     */
    public static void refreshSources() {
        if (sRefreshRunning) return;
        sRefreshRunning = true;
        new Thread(() -> {
            try {
                final java.io.File f = new java.io.File(QtNative.activity().getFilesDir(), "settings.json");
                if (!f.exists()) {
                    android.util.Log.i(TAG, "refreshSources: no settings.json");
                } else {
                    final String raw =
                            new String(java.nio.file.Files.readAllBytes(f.toPath()),
                                       java.nio.charset.StandardCharsets.UTF_8);
                    final org.json.JSONObject obj = new org.json.JSONObject(raw);
                    final org.json.JSONArray arr = obj.optJSONArray("sources");
                    if (arr == null) {
                        android.util.Log.i(TAG, "refreshSources: no sources in settings");
                    } else {
                        for (int i = 0; i < arr.length(); i++) {
                            final org.json.JSONObject s = arr.getJSONObject(i);
                            final String uriStr = s.optString("uri");
                            final String path = s.optString("path");
                            if (uriStr.isEmpty() || path.isEmpty()) continue;
                            final android.content.ContentResolver cr =
                                    QtNative.activity().getContentResolver();
                            // Best-effort: a revoked/unmounted source just fails quietly.
                            try { cr.takePersistableUriPermission(
                                    android.net.Uri.parse(uriStr),
                                    Intent.FLAG_GRANT_READ_URI_PERMISSION
                                            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION); } catch (Exception ignored) {}
                            final int n = stageTree(android.net.Uri.parse(uriStr), path);
                            android.util.Log.i(TAG, "refreshSources [" + i + "] copied=" + n
                                    + " " + path);
                        }
                    }
                }
            } catch (Exception e) {
                android.util.Log.w(TAG, "refreshSources failed: " + e);
            } finally {
                try {
                    final android.app.Activity a = QtNative.activity();
                    if (a != null) {
                        final android.content.SharedPreferences prefs =
                                a.getSharedPreferences("refresh", android.content.Context.MODE_PRIVATE);
                        prefs.edit().clear().putBoolean("refreshDone", true).commit();
                    }
                } catch (Exception e) {
                    android.util.Log.w(TAG, "refreshSources marker failed: " + e);
                }
                sRefreshRunning = false;
            }
        }).start();
    }

    private static boolean isSupportedDictionaryName(String name) {
        final String lower = name.toLowerCase(java.util.Locale.ROOT);
        return lower.endsWith(".mdx") || lower.endsWith(".mdd")
                || lower.endsWith(".dsl") || lower.endsWith(".dsl.dz")
                || lower.endsWith(".ifo");
    }

    static void releaseSourcePermission(String uriStr) {
        try {
            final android.net.Uri uri = android.net.Uri.parse(uriStr);
            QtNative.activity().getContentResolver().releasePersistableUriPermission(uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
        } catch (Exception e) {
            android.util.Log.w(TAG, "releaseSourcePermission failed: " + e);
        }
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