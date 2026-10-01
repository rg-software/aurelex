package org.aurelex.pocket.dictionary;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.IBinder;

import androidx.core.content.ContextCompat;

/**
 * Foreground service that stages (copies) a newly picked dictionary folder
 * into app-private storage (folder-scoped-storage, D3/D4a).
 *
 * The copy itself runs on a background thread inside this service; the
 * service's job is to hold a foreground notification ("Preparing
 * dictionaries…") so a large copy (GB-scale .mdd) survives the app being
 * backgrounded and is not silently killed, and to give the user visible
 * feedback that processing is happening.
 *
 * Files land in {@code files/staging-tmp/<sourceId>} and are merged into
 * {@code files/staged/<sourceId>} only when the copy is complete, so a killed
 * copy never leaves a half-copied tree that the engine would (re)scan. The merge
 * is an OVERLAY, not a replace: the staging walk dedups unchanged files against
 * this folder's previous copy, so those files never reach the temp dir and must
 * not be deleted with it. Only then is the source registered via
 * {@code source.xml} for the C++ poller (EngineController) to ingest and scan.
 */
public class StagingService extends Service {
    private static final String TAG = "Aurelex";
    private static final String CHANNEL_ID = "dictionary-processing";
    private static final int NOTIFICATION_ID = 1002;
    private static final String EXTRA_TREE_URI = "treeUri";
    private static final String EXTRA_DISPLAY = "display";
    private static final String PREFS_STAGING = "staging";

    /** Writes/clears the "copy in progress" marker the C++ poller reads. */
    private static void writeStagingMarker(Context context, boolean active) {
        try {
            final SharedPreferences prefs =
                    context.getSharedPreferences(PREFS_STAGING, Context.MODE_PRIVATE);
            prefs.edit().clear().putBoolean("stagingActive", active).commit();
        } catch (Exception e) {
            android.util.Log.w(TAG, "writeStagingMarker failed: " + e);
        }
    }

    /** Starts the foreground staging service. Returns false if it could not start. */
    public static boolean start(Context context, android.net.Uri treeUri, String display) {
        try {
            final Context app = context.getApplicationContext();
            final Intent intent = new Intent(app, StagingService.class);
            intent.putExtra(EXTRA_TREE_URI, treeUri.toString());
            intent.putExtra(EXTRA_DISPLAY, display == null ? "" : display);
            // Use startService (allowed while the app is foreground) instead of
            // startForegroundService: the latter requires startForeground() within
            // ~5s of the call, which on a cold start can be delayed past the limit
            // by Qt/engine main-thread init -> ForegroundServiceDidNotStartInTime.
            // Our onCreate() calls startForeground() immediately, so the service
            // is always a proper FGS by the time it matters.
            app.startService(intent);
            android.util.Log.i(TAG, "StagingService starting for " + display);
            return true;
        } catch (Exception e) {
            android.util.Log.e(TAG, "StagingService.start failed: " + e);
            return false;
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        createChannel();
        // Call startForeground() early (not only in onStartCommand) so a busy
        // main thread during cold start can't delay it past Android's ~5s
        // ForegroundServiceDidNotStartInTimeException window.
        startForeground(NOTIFICATION_ID, buildNotification());
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(NOTIFICATION_ID, buildNotification());
        writeStagingMarker(getApplicationContext(), true);
        final String treeUriStr = intent == null ? null : intent.getStringExtra(EXTRA_TREE_URI);
        final String display = intent == null ? "" : intent.getStringExtra(EXTRA_DISPLAY);
        // The copy must NOT run on the service's main thread.
        new Thread(() -> {
            boolean attempted = false;
            int totalCopied = 0;
            try {
                if (treeUriStr != null) {
                    attempted = true;
                    totalCopied += stageOne(treeUriStr, display);
                }
                // Drain picks that queued while the copy above was running
                // (or that the activity queued because this service was already
                // active). Each is a separate one-off import.
                for (;;) {
                    final String[] pick = AurelexActivity.nextPendingPick();
                    if (pick == null) break;
                    attempted = true;
                    totalCopied += stageOne(pick[0], pick[1]);
                }
                // Nothing supported was staged from any pick: tell the user
                // instead of silently doing nothing (a blocked/empty folder, or
                // a folder with no .mdx/.dsl/.ifo files looks like a no-op).
                if (attempted && totalCopied <= 0) {
                    final android.content.Context app = getApplicationContext();
                    new android.os.Handler(getMainLooper()).post(() -> {
                        try {
                            android.widget.Toast.makeText(app,
                                    app.getString(R.string.import_no_supported),
                                    android.widget.Toast.LENGTH_LONG).show();
                        } catch (Exception ignored) {
                        }
                    });
                }
            } catch (Exception e) {
                android.util.Log.w(TAG, "staging failed: " + e);
            } finally {
                writeStagingMarker(getApplicationContext(), false);
                AurelexActivity.sStagingRunning = false;
                stopSelf();
            }
        }).start();
        return START_NOT_STICKY;
    }

    /** Stages a single folder pick: temp-copy into files/staged/<sourceId>.
     *  Returns the number of files copied (0 when nothing supported/unchanged). */
    private int stageOne(String treeUriStr, String display) {
        try {
            android.util.Log.i(TAG, "staging " + display);
            final android.net.Uri treeUri = android.net.Uri.parse(treeUriStr);
            final String sourceId = Integer.toHexString(treeUri.toString().hashCode());
            final java.io.File stagedRoot = new java.io.File(getFilesDir(), "staged");
            final java.io.File tmpDir = new java.io.File(getFilesDir(), "staging-tmp/" + sourceId);
            final java.io.File stagedDir = new java.io.File(getFilesDir(), "staged/" + sourceId);

            // Discard any leftover partial copy from a previously killed run.
            final java.io.File tmpRoot = tmpDir.getParentFile();
            if (tmpRoot != null) AurelexActivity.deleteRecursively(tmpRoot);

            final int copied =
                    AurelexActivity.stageTree(treeUri, tmpDir.getAbsolutePath(), stagedRoot, this);
            if (copied <= 0) {
                // 0 may mean "nothing new" (already-local/unchanged/deduped) or
                // "no supported files at all". StageService.log still has the
                // detailed counts from stageTreeInto when supported files were
                // found; the caller surfaces a hint either way so the pick isn't
                // a silent no-op.
                android.util.Log.w(TAG, "no new dictionary files staged from " + treeUri
                        + " (displaying " + display + "); the dictionary is likely "
                        + "already added, or the folder has no supported files.");
                // Clean up the temp dir we would have filled.
                if (tmpDir.exists()) AurelexActivity.deleteRecursively(tmpDir);
                return 0;
            }
            // Merge temp -> final. A plain replace is WRONG here: stageTreeInto
            // dedups unchanged files against this folder's OWN previous copy in
            // files/staged, so they never reach the temp dir. Deleting the final
            // dir and renaming the (partial) temp over it would drop every file
            // that was skipped as a duplicate — e.g. re-importing a StarDict
            // folder after adding its res/ tree destroyed dzsample.{ifo,idx,dict}
            // and left only res/ (data loss). Overlay instead: unchanged files
            // stay in the final dir, new/changed files are moved over them.
            if (!stagedDir.exists() && !stagedDir.mkdirs()) {
                android.util.Log.e(TAG, "cannot create " + stagedDir + ", discarding " + tmpDir);
                AurelexActivity.deleteRecursively(tmpDir);
                return 0;
            }
            if (!overlayTree(tmpDir, stagedDir)) {
                android.util.Log.e(TAG, "stage overlay failed, discarding " + tmpDir);
                AurelexActivity.deleteRecursively(tmpDir);
                return 0;
            }
            AurelexActivity.deleteRecursively(tmpDir);
            // One-off import: no source.xml registration (that was the old
            // "persistent sources" model). Clearing the staging marker below is
            // the C++ poller's signal to scan the staged root.
            android.util.Log.i(TAG, "dictionary import staged: " + display
                    + " staged=" + copied + " files into " + stagedDir);
            return copied;
        } catch (Exception e) {
            android.util.Log.w(TAG, "stageOne failed for " + display + ": " + e);
            return 0;
        }
    }

    /**
     * Moves every file under {@code src} to the same relative path under
     * {@code dst}, creating directories and replacing a same-named file. Both
     * trees live under {@code getFilesDir()}, so a move is a rename; a copy is
     * the fallback if the rename is refused. Returns false on the first failure
     * (the caller then discards the temp tree).
     */
    private static boolean overlayTree(java.io.File src, java.io.File dst) {
        final java.io.File[] children = src.listFiles();
        if (children == null) return true;
        if (!dst.exists() && !dst.mkdirs()) return false;
        for (java.io.File child : children) {
            final java.io.File target = new java.io.File(dst, child.getName());
            if (child.isDirectory()) {
                if (!overlayTree(child, target)) return false;
                continue;
            }
            if (target.exists() && !target.delete()) return false;
            if (!child.renameTo(target)) {
                if (!copyFile(child, target)) return false;
                child.delete();
            }
        }
        return true;
    }

    /** Byte copy fallback for {@link #overlayTree}; returns false on failure. */
    private static boolean copyFile(java.io.File src, java.io.File dst) {
        try (java.io.InputStream in = new java.io.FileInputStream(src);
             java.io.FileOutputStream out = new java.io.FileOutputStream(dst)) {
            final byte[] buf = new byte[64 * 1024];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            return true;
        } catch (Exception e) {
            android.util.Log.w(TAG, "copyFile failed for " + src + ": " + e);
            return false;
        }
    }

    @Override
    public void onDestroy() {
        try {
            stopForeground(true);
        } catch (Exception e) {
            android.util.Log.w(TAG, "StagingService.onDestroy: " + e);
        }
        android.util.Log.i(TAG, "StagingService stopped");
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        final NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, getString(R.string.notification_channel_dict_processing),
                NotificationManager.IMPORTANCE_LOW);
        try {
            getSystemService(NotificationManager.class).createNotificationChannel(channel);
        } catch (Exception e) {
            android.util.Log.w(TAG, "createChannel failed: " + e);
        }
    }

    private Notification buildNotification() {
        final Intent open = new Intent(this, AurelexActivity.class);
        open.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        final PendingIntent pi = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        final Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return builder
                .setContentTitle(getString(R.string.notification_title))
                .setContentText(getString(R.string.notification_staging))
                .setSmallIcon(R.drawable.ic_notification)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
    }
}