package aurelex.android;

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
 * ExperimentActivity#startIndexing} (called from EngineController via JNI)
 * before the bulk build and stopped by {@link ExperimentActivity#stopIndexing}
 * when the build completes.
 *
 * Completion is also mirrored to the C++ side through the existing
 * shared-preferences poller pattern: this service writes
 * {@code indexingDone=true} into shared_prefs/indexing.xml when it stops, and
 * EngineController's poller consumes it.
 */
public class IndexingService extends Service {
    private static final String TAG = "AurelexExp";
    private static final String CHANNEL_ID = "fts-indexing";
    private static final String CHANNEL_NAME = "Full-text indexing";
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
            ContextCompat.startForegroundService(app, intent);
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

    @Override
    public void onCreate() {
        super.onCreate();
        createChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(NOTIFICATION_ID, buildNotification());
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
                CHANNEL_ID, CHANNEL_NAME, NotificationManager.IMPORTANCE_LOW);
        try {
            getSystemService(NotificationManager.class).createNotificationChannel(channel);
        } catch (Exception e) {
            android.util.Log.w(TAG, "createChannel failed: " + e);
        }
    }

    private Notification buildNotification() {
        final Intent open = new Intent(this, ExperimentActivity.class);
        open.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        final PendingIntent pi = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        final Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return builder
                .setContentTitle("AurelexExp")
                .setContentText("Indexing dictionaries\u2026")
                .setSmallIcon(android.R.drawable.ic_menu_search)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
    }
}