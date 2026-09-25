package org.aurelex.pocket.dictionary;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.Configuration;
import android.media.MediaPlayer;
import android.os.Bundle;

import org.qtproject.qt.android.bindings.QtActivity;
import org.qtproject.qt.android.QtNative;

import java.util.HashSet;
import java.util.Set;

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
public class AurelexActivity extends QtActivity {
    private static final String TAG = "Aurelex";

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
        maybeRequestNotificationPermission();
        // Main-looper watchdog for the system-bar icon appearance: Qt's QPA (and
        // the WM) can reset it right after we set it. Re-check every 700ms and
        // rewrite only when it has drifted, so the icons stay matched to our
        // self-painted strips and never flicker.
        new android.os.Handler(android.os.Looper.getMainLooper()).post(new Runnable() {
            @Override
            public void run() {
                syncSystemBarAppearance();
                new android.os.Handler(android.os.Looper.getMainLooper())
                        .postDelayed(this, 700);
            }
        });
    }

    private static final int REQUEST_POST_NOTIFICATIONS = 2002;

    // Desired system-bar icon appearance, remembered from the native side so the
    // Activity can (re)apply it whenever the window regains focus — Qt's QPA
    // sometimes resets the bars to its own (device-theme) appearance after we
    // set it, which is why icons ended up matching the DEVICE theme instead of
    // ours (invisible white-on-white / dark-on-dark).
    private static volatile boolean sDarkBars = false;

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        // Qt can clobber the bar appearance when it re-syncs; reapply the last
        // known value on every focus gain so our chrome and the icons always
        // match.
        if (hasFocus) setSystemBarAppearanceInternal(sDarkBars);
    }

    /**
     * On Android 13+ (API 33) POST_NOTIFICATIONS is a RUNTIME permission. The
     * manifest declares it, but without a runtime grant the system silently
     * drops the foreground-service notifications (IndexingService /
     * StagingService), so the user would never see "Indexing…"/"Preparing…"
     * while the app is backgrounded. Ask for it once at launch.
     */
    private void maybeRequestNotificationPermission() {
        try {
            if (android.os.Build.VERSION.SDK_INT >= 33
                    && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                            != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(
                        new String[]{android.Manifest.permission.POST_NOTIFICATIONS},
                        REQUEST_POST_NOTIFICATIONS);
            }
        } catch (Exception e) {
            android.util.Log.w(TAG, "maybeRequestNotificationPermission failed: " + e);
        }
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

    /**
     * Height (px) of the system status-bar inset at the top of the screen.
     * The Qt window runs edge-to-edge (no Android insets applied), so the QML
     * layer must offset its own top chrome below the status icons. Favors the
     * window's reported inset; falls back to the resource dimension.
     */
    public static int getSystemInsetTop() {
        try {
            android.app.Activity activity = QtNative.activity();
            if (activity != null) {
                android.view.WindowInsets wi = activity.getWindow().getDecorView().getRootWindowInsets();
                if (wi != null && wi.getSystemWindowInsetTop() > 0) return wi.getSystemWindowInsetTop();
            }
            int id = activity.getResources().getIdentifier("status_bar_height", "dimen", "android");
            return id > 0 ? activity.getResources().getDimensionPixelSize(id) : 0;
        } catch (Exception e) {
            android.util.Log.w(TAG, "getSystemInsetTop failed: " + e);
            return 0;
        }
    }

    /**
     * Height (px) of the system navigation-bar inset at the bottom.
     * Same edge-to-edge rationale as {@link #getSystemInsetTop}: the bottom
     * chrome must sit above the gesture/3-button nav area.
     */
    public static int getSystemInsetBottom() {
        try {
            android.app.Activity activity = QtNative.activity();
            if (activity != null) {
                android.view.WindowInsets wi = activity.getWindow().getDecorView().getRootWindowInsets();
                if (wi != null && wi.getSystemWindowInsetBottom() > 0) return wi.getSystemWindowInsetBottom();
            }
            int id = activity.getResources().getIdentifier("navigation_bar_height", "dimen", "android");
            return id > 0 ? activity.getResources().getDimensionPixelSize(id) : 0;
        } catch (Exception e) {
            android.util.Log.w(TAG, "getSystemInsetBottom failed: " + e);
            return 0;
        }
    }

    /**
     * Tells the system whether our chrome (status strip at top, nav strip at
     * bottom) is LIGHT or DARK, so the system icons (clock, signals, gesture
     * bar) are drawn with the right contrast. The Qt window is edge-to-edge and
     * we paint those two strips ourselves; without this the status icons stay
     * white on a white background (invisible). `dark` = our theme is dark.
     */
    public static void setSystemBarAppearance(boolean dark) {
        sDarkBars = dark;
        setSystemBarAppearanceInternal(dark);
    }

    /**
     * Self-healing sync: Qt's QPA (or the WM) can reset the bar icons to the
     * device-theme default after we set them. This reads the CURRENT appearance
     * and only rewrites when it does not match {@link #sDarkBars}. Called
     * periodically from the native poller and on window focus, so the bars heal
     * within ~500ms of any clobber.
     */
    public static void syncSystemBarAppearance() {
        try {
            android.app.Activity activity = QtNative.activity();
            if (activity == null) return;
            android.view.Window window = activity.getWindow();
            if (window == null) return;
            final int want = sDarkBars ? 0 : android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            int have;
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                android.view.WindowInsetsController c = window.getInsetsController();
                if (c == null) return;
                int app = c.getSystemBarsAppearance();
                have = (app & android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS);
            } else {
                have = window.getDecorView().getSystemUiVisibility()
                        & android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            }
            if (have != want) setSystemBarAppearanceInternal(sDarkBars);
        } catch (Exception ignored) {
        }
    }

    private static void setSystemBarAppearanceInternal(boolean dark) {
        try {
            android.app.Activity activity = QtNative.activity();
            if (activity == null) return;
            android.view.Window window = activity.getWindow();
            if (window == null) return;
            final int LIGHT_STATUS = android.view.View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            final int LIGHT_NAV = android.view.View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                android.view.WindowInsetsController c = window.getInsetsController();
                if (c != null) {
                    final int light =
                            android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS;
                    final int lightNav =
                            android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                    // dark theme -> keep default (light/white) icons; light theme ->
                    // dark icons via the LIGHT appearance flags.
                    c.setSystemBarsAppearance(dark ? 0 : (light | lightNav), light | lightNav);
                }
            }
            // Set the window's own deprecated systemUiVisibility attrs too — some
            // ROMs/WMs only honor those for the status-icon color.
            try {
                android.view.WindowManager.LayoutParams lp = window.getAttributes();
                int w = lp.systemUiVisibility & ~(LIGHT_STATUS | LIGHT_NAV);
                if (!dark) w |= (LIGHT_STATUS | LIGHT_NAV);
                lp.systemUiVisibility = w;
                window.setAttributes(lp);
            } catch (Exception ignored) {
            }
            // Belt-and-braces on the decor view too (pre-30 API and any window
            // that doesn't honor the insets controller).
            try {
                int flags = window.getDecorView().getSystemUiVisibility();
                flags = dark ? (flags & ~(LIGHT_STATUS | LIGHT_NAV))
                             : (flags | LIGHT_STATUS | LIGHT_NAV);
                window.getDecorView().setSystemUiVisibility(flags);
            } catch (Exception ignored) {
            }
        } catch (Exception e) {
            android.util.Log.w(TAG, "setSystemBarAppearance failed: " + e);
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
     * {@link #onActivityResult}; the picked folder is one-off imported: staged
     * into app-private storage and then scanned + indexed by the C++ side.
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
            // Open the picker INSIDE a normal, grantable folder rather than the
            // shared-storage ROOT. Android refuses to hand out access to the
            // storage root, so a picker that opens there shows the "Выберите
            // другую папку / protected" card and the user is stuck (and
            // DocumentsUI remembers that location, so every later pick lands
            // there again). We point EXTRA_INITIAL_URI at "primary:Aurelex", a
            // folder we create if missing; the user can still navigate anywhere
            // (e.g. GoldenDict) from there.
            try {
                final String startPath = ensureDefaultImportDir();
                android.net.Uri startUri = android.provider.DocumentsContract.buildRootUri(
                        "com.android.externalstorage.documents", "primary");
                if (startPath != null && !startPath.isEmpty()) {
                    startUri = android.provider.DocumentsContract.buildDocumentUri(
                            "com.android.externalstorage.documents",
                            "primary:" + startPath);
                }
                intent.putExtra(android.provider.DocumentsContract.EXTRA_INITIAL_URI, startUri);
            } catch (Exception ignored) {
                // EXTRA_INITIAL_URI is API 26+; older devices just open default.
            }
            activity.startActivityForResult(intent, REQUEST_PICK_DICTIONARY_FOLDER);
        } catch (Exception e) {
            android.util.Log.w(TAG, "pickDictionaryFolder failed: " + e);
        }
    }

    /**
     * Ensures a normal, grantable folder exists for imports and returns its
     * path relative to the primary shared-storage volume (e.g. "Aurelex"), or
     * "" when it cannot be created/verified. App-private external storage needs
     * no permission, so this works even before any SAF grant exists.
     */
    private static String ensureDefaultImportDir() {
        try {
            java.io.File ext = android.os.Environment.getExternalStorageDirectory();
            if (ext == null) return "";
            java.io.File dir = new java.io.File(ext, "Aurelex");
            if (!dir.exists() && !dir.mkdirs()) return "";
            return "Aurelex";
        } catch (Exception e) {
            android.util.Log.w(TAG, "ensureDefaultImportDir failed: " + e);
            return "";
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
            final String display = resolveTreePath(treeUri); // may be empty (cloud)

            // One-off import: ALWAYS stage-copy into app-private storage.
            // Scoped storage blocks direct path reads of /storage/emulated/0 for
            // apps without AFA, so the engine can only read files the app can
            // reach by path — which means copying the picked tree's supported
            // files through the transient SAF grant into files/staged/<sourceId>.
            // No persistable grant is taken (the staged copy is authoritative and
            // there is no live "source" to re-sync).
            //
            // The copy runs on the foreground StagingService (with a "Preparing
            // dictionaries…" notification) so a large copy survives the app being
            // backgrounded. StagingService clears the staging marker when the copy
            // completes; the C++ poller sees that and scans the staged root.
            //
            // If a copy is ALREADY running, don't drop this pick: queue it and
            // let StagingService drain the queue after the current copy finishes.
            if (sStagingRunning) {
                android.util.Log.i(TAG, "staging in progress; queueing " + display);
                synchronized (sPendingPicks) {
                    sPendingPicks.addLast(new String[]{ treeUri.toString(), display });
                }
                return;
            }
            sStagingRunning = true;
            if (!StagingService.start(getApplicationContext(), treeUri, display)) {
                sStagingRunning = false;
            }
        } catch (Exception e) {
            sStagingRunning = false;
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
     * Dedup scope is the destination's parent (a staged subdir's sibling root).
     */
    static int stageTree(android.net.Uri treeUri, String destDir) {
        return stageTree(treeUri, destDir, new java.io.File(destDir).getParentFile());
    }

    /**
     * stageTree variant with an explicit dedup scope — the copy is compared
     * against {@code stageRoot} (typically {@code files/staged}) so an
     * intersecting pick never stages the same dictionary twice, even when the
     * copy itself lands in a temp dir outside that root.
     */
    static int stageTree(android.net.Uri treeUri, String destDir, java.io.File stageRoot) {
        return stageTree(treeUri, destDir, stageRoot, null);
    }

    /**
     * stageTree variant that obtains the ContentResolver from an explicit
     * Context instead of QtNative.activity() — used by StagingService, which
     * keeps copying even when no Activity is reachable (backgrounded app).
     */
    static int stageTree(android.net.Uri treeUri, String destDir, java.io.File stageRoot,
                         android.content.Context ctx) {
        final android.content.ContentResolver cr;
        if (ctx != null) {
            cr = ctx.getContentResolver();
        } else {
            try {
                cr = QtNative.activity().getContentResolver();
            } catch (Exception e) {
                return -1;
            }
        }
        final java.io.File dir = new java.io.File(destDir);
        if (!dir.exists() && !dir.mkdirs()) return -1;
        // The stage root holds every source's dir: files/staged/<sourceId>. An
        // intersecting pick (e.g. GoldenDict + GoldenDict/English) can stage the
        // same dictionary under two source dirs; without this the engine would
        // load it twice (ids hash the file path). Dedup by (name, size, mtime).
        return stageTreeInto(treeUri,
                android.provider.DocumentsContract.getTreeDocumentId(treeUri),
                cr, dir, stageRoot, 0, new StageVisited(), false);
    }

    /**
     * Recursively deletes a file or directory tree (File.delete() only removes
     * empty dirs). Used to discard incomplete staging copies.
     */
    static void deleteRecursively(java.io.File f) {
        if (f == null || !f.exists()) return;
        if (f.isDirectory()) {
            java.io.File[] children = f.listFiles();
            if (children != null) {
                for (java.io.File c : children) deleteRecursively(c);
            }
        }
        f.delete();
    }

    /** Mutable traversal state shared across the stageTreeInto recursion. */
    private static final class StageVisited {
        final Set<java.io.File> files = new HashSet<>();
        final Set<String> uris = new HashSet<>();
    }

    private static int stageTreeInto(android.net.Uri treeUri,
                                     String currentDocId,
                                     android.content.ContentResolver cr,
                                     java.io.File destDir,
                                     java.io.File stageRoot,
                                     int depth,
                                     StageVisited state,
                                     boolean inResourceDir) {
        final String[] cols = {
                android.provider.DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                android.provider.DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                android.provider.DocumentsContract.Document.COLUMN_MIME_TYPE,
                android.provider.DocumentsContract.Document.COLUMN_SIZE,
                android.provider.DocumentsContract.Document.COLUMN_LAST_MODIFIED };
        int copied = 0;
        try {
            // Depth cap as a hard backstop against pathological providers.
            if (depth > 64) return 0;
            // Physical-path guard: refuse to re-enter a destination dir we have
            // already staged into (a provider that yields a parent as a child
            // would otherwise recurse forever -> StackOverflowError).
            if (destDir != null) {
                try {
                    destDir = destDir.getCanonicalFile();
                } catch (java.io.IOException ignored) {
                }
                if (state.files.contains(destDir)) return 0;
                state.files.add(destDir);
            }
            // List the CURRENT folder's children. IMPORTANT: children are
            // resolved against the root TREE uri using each folder's full
            // document id (e.g. "primary:GoldenDict/Finnish/<sub>"); do NOT
            // build a per-folder document uri and call getTreeDocumentId() on
            // it — that returns the root tree id and would re-list the root
            // forever (the "no supported files staged" / stack-overflow bug).
            final android.net.Uri childrenUri =
                    android.provider.DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, currentDocId);
            int sawFiles = 0, supported = 0, deduped = 0, alreadyLocal = 0;
            try (android.database.Cursor c = cr.query(childrenUri, cols, null, null, null)) {
                if (c == null) {
                    android.util.Log.w(TAG, "stageTreeInto: null cursor for docId=" + currentDocId);
                    return copied;
                }
                while (c != null && c.moveToNext()) {
                    final String docId = c.getString(0);
                    final String name = c.getString(1);
                    final String mime = c.getString(2);
                    if (name == null) continue;
                    if (android.provider.DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                        // Recurse into the subfolder, preserving the relative path.
                        // The SAME root treeUri is kept; only the folder's document
                        // id changes, so the next level lists the right children.
                        final java.io.File sub = new java.io.File(destDir, name);
                        // Create the physical subdir FIRST, or the file writes
                        // below throw FileNotFoundException: ENOENT (the parent
                        // of a nested dict file does not exist yet).
                        if (!sub.exists() && !sub.mkdirs()) {
                            android.util.Log.w(TAG, "stageTreeInto: cannot mkdir " + sub);
                            continue;
                        }
                        copied += stageTreeInto(treeUri, docId, cr, sub, stageRoot,
                                depth + 1, state, inResourceDir || isResourceDirName(name));
                        continue;
                    }
                    sawFiles++;
                    // Inside a "<name>.files" resource tree, copy EVERYTHING (DSL
                    // sounds are .wav/.ogg/.mp3 next to images, etc.) so
                    // pronunciation links and inline assets resolve. Elsewhere
                    // keep the supported-dictionary filter.
                    final boolean resource = inResourceDir;
                    if (!resource && !isSupportedDictionaryName(name)) continue;
                    supported++;
                    final long srcSize = c.isNull(3) ? -1 : c.getLong(3);
                    final long srcModified = c.isNull(4) ? 0 : c.getLong(4);
                    final java.io.File out = new java.io.File(destDir, name);
                    if (out.exists() && out.isFile()
                            && srcSize >= 0 && out.length() == srcSize
                            && (srcModified <= 0
                                || Math.abs(out.lastModified() - srcModified) < 5000)) {
                        alreadyLocal++;
                        continue; // unchanged since we staged it
                    }
                    // Intersecting pick (same dictionary under another source):
                    // if an identical (name, size, mtime) copy already exists
                    // elsewhere in the stage root, skip it so the engine doesn't
                    // load a path-hashed duplicate id twice. Resource files are
                    // exempt: they don't create engine ids and the full-tree scan
                    // would be O(n^2) across a dictionary's tens of thousands of
                    // sound files.
                    if (!resource && hasStagedCopy(stageRoot, name, srcSize, srcModified, destDir)) {
                        deduped++;
                        continue;
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
            if (supported > 0) {
                android.util.Log.i(TAG, "stageTreeInto[" + currentDocId + "]: saw=" + sawFiles
                        + " supported=" + supported + " alreadyLocal=" + alreadyLocal
                        + " deduped=" + deduped + " copied=" + copied);
            }
            return copied;
        } catch (Exception e) {
            android.util.Log.w(TAG, "stageTreeInto failed for " + currentDocId + ": " + e);
            return copied;
        }
    }

    /**
     * True when a file with the same name/size/close-mtime already exists
     * somewhere under the stage root (other than the current source's dir).
     * Prevents intersecting picks from staging the same dictionary twice.
     */
    private static boolean hasStagedCopy(java.io.File stageRoot, String name,
                                         long size, long modified, java.io.File skipDir) {
        if (stageRoot == null || !stageRoot.isDirectory()) return false;
        final java.io.File[] children = stageRoot.listFiles();
        if (children == null) return false;
        for (java.io.File child : children) {
            if (child.equals(skipDir)) continue;
            if (child.isDirectory()) {
                if (hasStagedCopy(child, name, size, modified, null)) return true;
            } else if (child.isFile() && name.equals(child.getName())) {
                if (size >= 0 && child.length() == size
                        && (modified <= 0 || Math.abs(child.lastModified() - modified) < 5000))
                    return true;
            }
        }
        return false;
    }

    static volatile boolean sStagingRunning = false;

    /**
     * Queue of folder picks that arrived while a stage copy was already running.
     * Each entry is {treeUriString, display}. Pops are peeked by StagingService
     * (which drains the queue on its worker thread). Guarded by synchronizing on
     * the deque itself.
     */
    static final java.util.ArrayDeque<String[]> sPendingPicks = new java.util.ArrayDeque<>();

    /** Pops and returns the next queued pick, or null when empty. */
    static String[] nextPendingPick() {
        synchronized (sPendingPicks) {
            return sPendingPicks.pollFirst();
        }
    }

    /**
     * Bulk FTS indexing (bulk-fts-indexing): started by EngineController via
     * JNI before the automatic bulk index build and stopped when it completes.
     * The foreground IndexingService keeps the process alive long enough for
     * the in-process C++ worker to finish the build even when the app is
     * backgrounded, and shows an "Indexing..." notification.
     */
    public static void startIndexing() {
        try {
            final android.app.Activity a = QtNative.activity();
            if (a != null) IndexingService.start(a.getApplicationContext());
        } catch (Exception e) {
            android.util.Log.w(TAG, "startIndexing failed: " + e);
        }
    }

    public static void stopIndexing() {
        try {
            final android.app.Activity a = QtNative.activity();
            if (a != null) IndexingService.stop(a.getApplicationContext());
        } catch (Exception e) {
            android.util.Log.w(TAG, "stopIndexing failed: " + e);
        }
    }

    /**
     * Pushes live FTS progress into the IndexingService's foreground
     * notification: "Indexing (2 of 5): <name>" + a determinate bar for the
     * overall batch. Called over JNI from
     * EngineController.pollFtsProgress on each poll.
     *
     * @param currentIndex 1-based number of the dictionary currently indexing
     * @param total        dictionaries in the batch
     * @param name         display name of the current dictionary
     * @param dictPercent  this dictionary's own 0..100 progress
     */
    public static void updateIndexingProgress(int currentIndex, int total,
                                              String name, int dictPercent) {
        try {
            IndexingService.updateProgress(currentIndex, total, name, dictPercent);
        } catch (Exception e) {
            android.util.Log.w(TAG, "updateIndexingProgress failed: " + e);
        }
    }

    private static boolean isSupportedDictionaryName(String name) {
        final String lower = name.toLowerCase(java.util.Locale.ROOT);
        return lower.endsWith(".mdx") || lower.endsWith(".mdd")
                || lower.endsWith(".dsl") || lower.endsWith(".dsl.dz")
                || lower.endsWith(".ifo")
                // DSL resource archive (sounds/images); the engine opens it via
                // findFirstExistingFile("<name>.dsl.files.zip").
                || lower.endsWith(".files.zip");
    }

    /**
     * DSL keeps a dictionary's sounds and inline images in a sibling tree named
     * "&lt;dictionary file&gt;.files" (the engine's resourceDir1/resourceDir2).
     * Its contents are copied wholesale so gd_get_audio (pronunciations) and
     * gd_get_resource (images) can resolve them.
     */
    private static boolean isResourceDirName(String name) {
        return name.toLowerCase(java.util.Locale.ROOT).endsWith(".files");
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