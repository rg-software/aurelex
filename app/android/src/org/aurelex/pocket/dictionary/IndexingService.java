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
 * Foreground service that keeps the bulk full-text index build alive when the
 * app is backgrounded (bulk-fts-indexing, design D3).
 *
 * The actual {@code gd_fts_index} loop runs in-process on the C++ worker
 * thread; this service's job is to hold a foreground notification so the
 * process is not starved/suspended while a long build runs, and to show the
 * user that indexing is in progress. It is started by {@link
 * AurelexActivity#startIndexing} (called from EngineController via JNI)
 * before the bulk build and stopped by {@link AurelexActivity#stopIndexing}
 * when the build completes.
 *
 * Completion is also mirrored to the C++ side through the existing
 * shared-preferences poller pattern: this service writes
 * {@code indexingDone=true} into shared_prefs/indexing.xml when it stops, and
 * EngineController's poller consumes it.
 */
public class IndexingService extends Service {
    private static final String TAG = "Aurelex";
    private static final String CHANNEL_ID = "fts-indexing";
    private static final int NOTIFICATION_ID = 1001;
    private static final String PREFS_INDEXING = "indexing";

    /** Write the "index build finished" marker for the C++ poller. */
    private static void writeDoneMarker(Context context) {
        try {
            final SharedPreferences prefs =
                    context.getSharedPreferences(PREFS_INDEXING, Context.MODE_PRIVATE);
            prefs.edit().clear().putBoolean("indexingDone", true).commit();
        } catch (Exception e) {
            android.util.Log.w(TAG, "writeDoneMarker failed: " + e);
        }
    }

    /** Starts the foreground service (API-gated by ContextCompat). */
    public static void start(Context context) {
        try {
            final Context app = context.getApplicationContext();
            final Intent intent = new Intent(app, IndexingService.class);
            // Use startService (allowed while the app is foreground) instead of
            // startForegroundService: the latter requires startForeground() within
            // ~5s of the call, which on a cold start can be delayed past the limit
            // by Qt/engine main-thread init -> ForegroundServiceDidNotStartInTime
            // -> the crash-relaunch loop we've hit. Our onCreate() calls
            // startForeground() immediately, so the service is a proper FGS by the
            // time the system checks.
            app.startService(intent);
            android.util.Log.i(TAG, "IndexingService starting");
        } catch (Exception e) {
            android.util.Log.e(TAG, "IndexingService.start failed: " + e);
        }
    }

    /** Stops the foreground service; its onDestroy writes the done marker. */
    public static void stop(Context context) {
        try {
            final Context app = context.getApplicationContext();
            app.stopService(new Intent(app, IndexingService.class));
        } catch (Exception e) {
            android.util.Log.w(TAG, "IndexingService.stop failed: " + e);
        }
    }

    private static IndexingService sInstance = null;

    @Override
    public void onCreate() {
        super.onCreate();
        sInstance = this;
        createChannel();
        // startForegroundService() requires startForeground() within ~5s, and
        // Android enforces it from the moment the process starts. Call it as
        // early as possible (in onCreate, not onStartCommand) so a busy main
        // thread during cold start can't delay it past the limit and crash with
        // ForegroundServiceDidNotStartInTimeException. onStartCommand updates it.
        startForeground(NOTIFICATION_ID, buildNotification(0, 0, null, 0));
    }

    /** Static access to the live service for cross-thread notification updates. */
    static IndexingService instance() { return sInstance; }

    /**
     * Updates the foreground notification with live progress: "Indexing
     * (current of total): <name>" with a determinate bar for the OVERALL batch
     * fraction (monotonic). Called over JNI from the C++ side
     * (EngineController) each poll while indexing runs.
     */
    public static void updateProgress(int currentIndex, int total,
                                      String name, int overallPercent) {
        try {
            final IndexingService svc = sInstance;
            if (svc == null) return;
            final NotificationManager nm =
                    (NotificationManager) svc.getSystemService(NOTIFICATION_SERVICE);
            if (nm == null) return;
            nm.notify(NOTIFICATION_ID, svc.buildNotification(currentIndex, total, name, overallPercent));
        } catch (Exception e) {
            android.util.Log.w(TAG, "updateProgress failed: " + e);
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(NOTIFICATION_ID, buildNotification(0, 0, null, 0));
        android.util.Log.i(TAG, "IndexingService foreground: bulk FTS indexing running");
        // Not sticky: if the process is killed mid-build, a restart re-scans on
        // next launch and autoIndexMissing rebuilds what is still missing.
        return START_NOT_STICKY;
    }

    @Override
    public void onDestroy() {
        try {
            writeDoneMarker(getApplicationContext());
            stopForeground(true);
        } catch (Exception e) {
            android.util.Log.w(TAG, "IndexingService.onDestroy failed: " + e);
        }
        sInstance = null;
        android.util.Log.i(TAG, "IndexingService stopped");
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        final NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, getString(R.string.notification_channel_fts_indexing),
                NotificationManager.IMPORTANCE_LOW);
        try {
            getSystemService(NotificationManager.class).createNotificationChannel(channel);
        } catch (Exception e) {
            android.util.Log.w(TAG, "createChannel failed: " + e);
        }
    }

    private Notification buildNotification(int currentIndex, int total,
                                           String name, int overallPercent) {
        final Intent open = new Intent(this, AurelexActivity.class);
        open.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        final PendingIntent pi = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        final Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        final String text = (total > 0 && name != null && !name.isEmpty())
                ? getString(R.string.notification_indexing_progress, currentIndex, total, name)
                : getString(R.string.notification_indexing_done);
        builder
                .setContentTitle(getString(R.string.notification_title))
                .setContentText(text)
                .setSmallIcon(R.drawable.ic_notification)
                .setContentIntent(pi)
                .setOnlyAlertOnce(true)
                .setOngoing(true);
        if (total > 0) {
            // Determinate bar for the OVERALL batch progress (0..100).
            builder.setProgress(100, overallPercent, false);
        } else {
            builder.setProgress(0, 0, true); // indeterminate while starting
        }
        return builder.build();
    }
}