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
import android.os.StatFs;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;

/**
 * Foreground service that downloads dictionaries from the remote catalog.
 *
 * <p>Each batch is handed over as a JSON payload by EngineController over JNI:
 * <pre>
 * {
 *   "requests": [
 *     { "id", "name", "contentHash",
 *       "files": [ { "name", "url", "sizeBytes", "sha256", "required" } ] }
 *   ],
 *   "catalogIndex": { "&lt;entryId&gt;": "&lt;contentHash&gt;" }
 * }
 * </pre>
 *
 * <p>Files are written to {@code files/staging-tmp/<contentHash>} and the
 * directory is atomically renamed to {@code files/staged/<contentHash>} only
 * once every file in the entry has arrived, been size-checked, and (when the
 * catalog supplies a checksum) been SHA-256 verified. A partial transfer
 * therefore never becomes visible to the engine scan.
 *
 * <p>Why a service and not the Qt side: a multi-hundred-MB download must
 * survive the app being backgrounded or the process being reclaimed, and
 * Android requires a foreground notification for that. The service also keeps
 * downloading after the Qt activity is gone, which is what makes a "keep
 * downloading while you read" flow possible at all.
 *
 * <p>Progress is published the same way the staging/indexing services do it: by
 * writing {@code shared_prefs/download.xml}, which the C++ poller
 * (EngineController::syncDownloadState) reads every 500ms. That keeps QML from
 * needing any JNI for rendering progress, and means a completed batch is
 * reported even if the download finished while the app was in the background.
 */
public class DictionaryDownloadService extends Service {
    private static final String TAG = "Aurelex";
    private static final String CHANNEL_ID = "dictionary-download";
    private static final int NOTIFICATION_ID = 1003;
    private static final String PREFS_DOWNLOAD = "download";
    private static final String EXTRA_PAYLOAD = "payload";

    /**
     * Mirrors RemoteCatalog::kMinHeadroomBytes. Re-checked here because this is
     * the authoritative check: the Qt preflight is a UX gate that the user can
     * dismiss, while this one runs immediately before the first byte and cannot
     * be talked out of it.
     */
    private static final long MIN_HEADROOM_BYTES = 512L * 1024 * 1024;

    /**
     * A request is cancelled the first time this is observed true. Reset to
     * false in onStartCommand, so cancelling one batch cannot cancel the next.
     */
    private static volatile boolean sCanceled = false;
    /** One batch at a time; a second start while busy is refused. */
    private static volatile boolean sBusy = false;

    /**
     * Content-hash recipe shared with the C++ side
     * (RemoteCatalog::contentHash). Mirrored rather than imported because the
     * C++ function is not reachable over JNI, and the two MUST agree: the
     * directory name is what makes an installed entry's files findable again
     * for the optional-audio follow-up.
     */
    private static String contentHashFor(String id, List<String> requiredNames) {
        final List<String> names = new ArrayList<>(requiredNames);
        java.util.Collections.sort(names);
        final StringBuilder seed = new StringBuilder(id);
        for (String n : names) seed.append('\n').append(n);
        try {
            final MessageDigest md = MessageDigest.getInstance("MD5");
            final byte[] digest = md.digest(seed.toString().getBytes("UTF-8"));
            final StringBuilder hex = new StringBuilder(32);
            for (byte b : digest) {
                final String h = Integer.toHexString(b & 0xff);
                if (h.length() == 1) hex.append('0');
                hex.append(h);
            }
            return hex.toString();
        } catch (Exception e) {
            // Deliberately NOT a fallback hash: any other value would name a
            // different directory than the C++ side derives, and the entry would
            // then never be found again. Failing loudly beats a silent split.
            throw new IllegalStateException("MD5 unavailable, cannot derive the content hash", e);
        }
    }

    /** Starts the foreground download service with a JSON payload. */
    public static boolean start(Context context, String payloadJson) {
        try {
            final Context app = context.getApplicationContext();
            final Intent intent = new Intent(app, DictionaryDownloadService.class);
            intent.putExtra(EXTRA_PAYLOAD, payloadJson == null ? "" : payloadJson);
            // startService, not startForegroundService, for the same reason as
            // StagingService: onCreate() calls startForeground() immediately, so
            // the 5s ForegroundServiceDidNotStartInTime window cannot be missed
            // by a slow cold start. The service is started from a user action
            // while the app is in the foreground, where startService is allowed.
            app.startService(intent);
            android.util.Log.i(TAG, "DictionaryDownloadService starting");
            return true;
        } catch (Exception e) {
            android.util.Log.e(TAG, "DictionaryDownloadService.start failed: " + e);
            return false;
        }
    }

    /**
     * Requests cancellation of the running batch (or of the next one). The
     * transfer thread checks the flag between chunks and aborts in-flight
     * connections, then reports "cancelled" through the marker.
     */
    public static void cancel() {
        // Only set the flag: the transfer thread checks it between chunks, aborts
        // the connection, and its finally block writes "cancelled" and calls
        // stopSelf(). Stopping the service from here would remove the foreground
        // notification while the worker was still unwinding a blocking read,
        // leaving a window where the transfer looks finished but is not.
        sCanceled = true;
        android.util.Log.i(TAG, "DictionaryDownloadService cancel requested");
    }

    /** Progress snapshot written to shared_prefs/download.xml for the C++ poller. */
    private static class State {
        boolean active = true;
        boolean canceled = false;
        String entryName = "";
        int filesDone = 0;
        int filesTotal = 0;
        long bytesDone = 0;
        long bytesTotal = 0;
        String speed = "";
        String message = "";
        /** Pipe-separated content hashes a live transfer owns (never purged). */
        final List<String> scratchHashes = new ArrayList<>();
        final List<String> succeeded = new ArrayList<>();
        final List<String> failed = new ArrayList<>();
    }

    private static void writeState(Context context, State s) {
        try {
            final SharedPreferences prefs =
                    context.getSharedPreferences(PREFS_DOWNLOAD, Context.MODE_PRIVATE);
            final SharedPreferences.Editor ed = prefs.edit().clear();
            ed.putBoolean("downloadActive", s.active);
            ed.putBoolean("downloadCanceled", s.canceled);
            ed.putInt("filesDone", s.filesDone);
            ed.putInt("filesTotal", s.filesTotal);
            ed.putLong("bytesDone", s.bytesDone);
            ed.putLong("bytesTotal", s.bytesTotal);
            ed.putString("entryName", s.entryName);
            ed.putString("speed", s.speed);
            ed.putString("message", s.message);
            ed.putString("scratchHashes", String.join("|", s.scratchHashes));
            ed.putString("succeeded", String.join("|", s.succeeded));
            ed.putString("failed", String.join("|", s.failed));
            // commit(), not apply(): the C++ poller polls this file and a
            // delayed write would make a finished download look like it is
            // still running (or miss the terminal outcome entirely).
            ed.commit();
        } catch (Exception e) {
            android.util.Log.w(TAG, "writeState failed: " + e);
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        createChannel();
        startForeground(NOTIFICATION_ID, buildNotification(0, 0, 0, ""));
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        // One batch at a time: a second start while the worker is alive would
        // race it over the same state file and the same scratch dirs.
        if (sBusy) {
            android.util.Log.w(TAG, "a download batch is already running; ignoring the new start");
            return START_NOT_STICKY;
        }
        // Must happen BEFORE the worker starts, or a previous batch's cancel
        // would instantly cancel this one and no download would ever run again.
        sCanceled = false;
        sBusy = true;
        startForeground(NOTIFICATION_ID, buildNotification(0, 0, 0, ""));
        final String payload = intent == null ? "" : intent.getStringExtra(EXTRA_PAYLOAD);
        // Downloads must never run on the service's main thread.
        new Thread(() -> {
            final State state = new State();
            try {
                runBatch(payload, state);
            } catch (Exception e) {
                android.util.Log.w(TAG, "download batch failed: " + e);
                state.failed.add("batch");
                state.message = String.valueOf(e.getMessage() == null ? e : e.getMessage());
            } finally {
                // Every exit path leaves a terminal state behind: the C++ poller
                // ends the download by seeing active=false, so a silent return
                // here would hang the progress bar forever.
                if (!state.canceled && state.succeeded.isEmpty() && state.failed.isEmpty())
                    state.failed.add("batch");
                state.active = false;
                writeState(getApplicationContext(), state);
                sBusy = false;
                stopSelf();
            }
        }).start();
        return START_NOT_STICKY;
    }

    private void runBatch(String payload, State state) {
        final JSONObject root;
        try {
            root = new JSONObject(payload);
        } catch (Exception e) {
            state.failed.add("payload");
            state.message = "malformed download request";
            return;
        }
        final JSONArray requests = root.optJSONArray("requests");
        if (requests == null || requests.length() == 0) {
            state.message = "nothing to download";
            return;
        }
        final JSONObject catalogIndex = root.optJSONObject("catalogIndex");

        // Count the whole batch up front so the progress bar is meaningful and
        // the free-space check covers everything, not just the first entry.
        final List<JSONObject> plan = new ArrayList<>();
        for (int i = 0; i < requests.length(); i++) {
            final JSONObject r = requests.optJSONObject(i);
            if (r == null) continue;
            final JSONArray files = r.optJSONArray("files");
            if (files == null || files.length() == 0) continue;
            plan.add(r);
            state.filesTotal += files.length();
            for (int f = 0; f < files.length(); f++) {
                final JSONObject fo = files.optJSONObject(f);
                if (fo != null) state.bytesTotal += fo.optLong("sizeBytes", 0L);
            }
        }
        if (plan.isEmpty()) {
            state.message = "nothing to download";
            return;
        }

        // Authoritative free-space check, before the first byte. Mirrors
        // EngineController::freeBytesForDownloads: the app's files dir volume,
        // not the first StatFs root, which may be a different volume.
        final StatFs fs = new StatFs(getFilesDir().getAbsolutePath());
        final long free = fs.getAvailableBytes();
        if (free < state.bytesTotal + MIN_HEADROOM_BYTES) {
            state.failed.add("space");
            state.message = "not enough free space";
            android.util.Log.w(TAG, "refusing batch: need " + state.bytesTotal
                    + " + " + MIN_HEADROOM_BYTES + " headroom, have " + free);
            return;
        }

        reconcileOrphanScratch(catalogIndex, state);

        for (JSONObject r : plan) {
            if (sCanceled) {
                state.canceled = true;
                state.message = "cancelled";
                return;
            }
            downloadEntry(r, state);
        }
        state.message = "";
    }

    /**
     * Purges leftover {@code staging-tmp/<hash>} download dirs from a run that
     * was killed (or whose entry has since been withdrawn from the catalog), so
     * an interrupted transfer cannot silently consume gigabytes forever. A dir
     * whose entry is still in the catalog is left alone: a later batch for that
     * entry resumes it.
     */
    private void reconcileOrphanScratch(JSONObject catalogIndex, State state) {
        final File tmpRoot = new File(getFilesDir(), "staging-tmp");
        if (!tmpRoot.isDirectory()) return;
        final File[] children = tmpRoot.listFiles();
        if (children == null) return;
        for (File child : children) {
            if (!child.isDirectory()) continue;
            final String hash = child.getName();
            // SAF staging uses Integer.toHexString(treeUri.hashCode()) (<= 8 hex
            // chars) for the SAME staging-tmp root. Download dirs are always a
            // full 32-char MD5, so anything shorter belongs to a folder import
            // and must not be touched here -- a download batch must never delete
            // a pick that is being copied right now.
            if (hash.length() != 32) {
                android.util.Log.i(TAG, "leaving non-download scratch dir alone: " + hash);
                continue;
            }
            boolean stillOffered = false;
            if (catalogIndex != null) {
                final java.util.Iterator<String> it = catalogIndex.keys();
                while (it.hasNext()) {
                    if (hash.equals(catalogIndex.optString(it.next(), ""))) {
                        stillOffered = true;
                        break;
                    }
                }
            }
            if (stillOffered) {
                android.util.Log.i(TAG, "keeping scratch dir for a catalog entry: " + hash);
                continue;
            }
            android.util.Log.i(TAG, "purging orphaned scratch dir " + hash);
            AurelexActivity.deleteRecursively(child);
        }
        if (!state.scratchHashes.isEmpty()) writeState(getApplicationContext(), state);
    }

    /** Downloads every file of one entry, then atomically publishes the dir. */
    private void downloadEntry(JSONObject request, State state) {
        final String name = request.optString("name", "?");
        final String id = request.optString("id", "");
        final JSONArray files = request.optJSONArray("files");
        state.entryName = name;

        // The content hash the C++ side derived wins; recompute it only as a
        // fallback so a payload from a future/older caller still lands in a
        // stable directory.
        String hash = request.optString("contentHash", "");
        if (hash.isEmpty()) {
            final List<String> required = new ArrayList<>();
            for (int i = 0; i < files.length(); i++) {
                final JSONObject fo = files.optJSONObject(i);
                if (fo != null && fo.optBoolean("required", false))
                    required.add(fo.optString("name", ""));
            }
            hash = contentHashFor(id, required);
        }

        final File tmpDir = new File(getFilesDir(), "staging-tmp/" + hash);
        final File stagedDir = new File(getFilesDir(), "staged/" + hash);
        if (!tmpDir.isDirectory() && !tmpDir.mkdirs()) {
            state.failed.add(name);
            state.message = "could not create the download directory";
            return;
        }
        if (!state.scratchHashes.contains(hash)) state.scratchHashes.add(hash);
        writeState(getApplicationContext(), state);

        // "Add audio" for an already-installed entry: the destination ALREADY
        // exists and must not be re-created. Download straight into it, one file
        // at a time, and publish nothing — the atomic rename is only for an entry
        // being created, where a half-written dir must stay invisible. A crash
        // mid-way can leave a truncated resource file, which the engine simply
        // fails to play for that word (it is not a dictionary source, so it never
        // reaches the engine's scan-failure path).
        boolean anyRequired = false;
        for (int i = 0; i < files.length(); i++) {
            final JSONObject fo = files.optJSONObject(i);
            if (fo != null && fo.optBoolean("required", false)) anyRequired = true;
        }
        if (stagedDir.isDirectory() && !anyRequired) {
            android.util.Log.i(TAG, "adding optional files to the installed " + stagedDir);
            for (int i = 0; i < files.length(); i++) {
                if (sCanceled) {
                    state.canceled = true;
                    state.message = "cancelled";
                    return;
                }
                final JSONObject fo = files.optJSONObject(i);
                if (fo == null) continue;
                final File dest = new File(stagedDir, fo.optString("name", ""));
                if (dest.isFile() && dest.length() == fo.optLong("sizeBytes", 0L)
                        && shaMatches(dest, fo.optString("sha256", ""))) {
                    state.filesDone++;
                    continue;
                }
                // A `.part` inside the published dir would be scanned as a
                // dictionary sibling, so resume metadata goes to staging-tmp.
                final File partDir = tmpDir.isDirectory() ? tmpDir : new File(getFilesDir(), "staging-tmp");
                if (!partDir.isDirectory() && !partDir.mkdirs()) {
                    state.failed.add(name);
                    state.message = "could not create the download directory";
                    return;
                }
                final long written = fetchOne(fo.optString("url", ""), dest,
                        fo.optLong("sizeBytes", 0L), fo.optString("sha256", ""), partDir, state);
                if (written < 0) {
                    state.failed.add(name);
                    return;
                }
                state.filesDone++;
                state.bytesDone += written;
                writeState(getApplicationContext(), state);
                updateNotification(state);
            }
            // The optional files went straight into the published dir, so the
            // staging-tmp dir created above is empty. Drop it (and its resume
            // claim) instead of leaving a stray the next purge has to clean.
            if (tmpDir.isDirectory()) tmpDir.delete();
            state.scratchHashes.remove(hash);
            state.succeeded.add(name);
            android.util.Log.i(TAG, "added optional files to " + stagedDir);
            return;
        }
        // Already published (a re-install of the same content): nothing to do,
        // and re-copying would only churn GB-scale files.
        if (stagedDir.isDirectory()) {
            android.util.Log.i(TAG, name + " already present at " + stagedDir);
            state.succeeded.add(name);
            for (int i = 0; i < files.length(); i++) state.filesDone++;
            writeState(getApplicationContext(), state);
            return;
        }

        boolean ok = true;
        for (int i = 0; i < files.length(); i++) {
            if (sCanceled) {
                state.canceled = true;
                state.message = "cancelled";
                // Leave the scratch dir: it is not a complete entry, and the
                // next run either resumes or purges it. Publishing it is the one
                // thing we must never do on a cancel.
                return;
            }
            final JSONObject fo = files.optJSONObject(i);
            if (fo == null) continue;
            final String fileName = fo.optString("name", "");
            final String url = fo.optString("url", "");
            final long expected = fo.optLong("sizeBytes", 0L);
            final String sha = fo.optString("sha256", "");
            final File dest = new File(tmpDir, fileName);
            if (dest.isFile() && dest.length() == expected && shaMatches(dest, sha)) {
                android.util.Log.i(TAG, "reusing already-downloaded " + fileName);
                state.filesDone++;
                continue;
            }
            if (dest.isFile()) dest.delete();
            // Bytes this attempt actually put on disk (0 when a resumed file was
            // already complete in the .part), so a resumed file is not counted
            // twice in the progress bar.
            final long written = fetchOne(url, dest, expected, sha, tmpDir, state);
            if (written < 0) {
                state.failed.add(name);
                ok = false;
                break;
            }
            state.filesDone++;
            state.bytesDone += written;
            writeState(getApplicationContext(), state);
            updateNotification(state);
        }
        if (!ok) {
            // A partial entry stays in staging-tmp/ WITH its .part files: a
            // transport failure is exactly the case resume exists for, and
            // reconcileOrphanScratch() purges the dir if the entry later leaves
            // the catalog. The hash is deliberately KEPT in scratchHashes so the
            // C++ side's purgeStagingTmp() does not discard the resume point in
            // the middle of this process's lifetime. What must never happen is the
            // atomic rename, so a half-fetched entry is still invisible to the
            // engine scan.
            return;
        }
        // Publish: temp -> staged. Everything the engine will scan is complete.
        if (stagedDir.exists()) AurelexActivity.deleteRecursively(stagedDir);
        if (!tmpDir.renameTo(stagedDir)) {
            android.util.Log.e(TAG, "publish rename failed for " + name + " (" + tmpDir + ")");
            state.failed.add(name);
            state.message = "could not finalise the download";
            return;
        }
        state.scratchHashes.remove(hash);
        state.succeeded.add(name);
        android.util.Log.i(TAG, "downloaded " + name + " -> " + stagedDir);
    }

    /**
     * Streams one URL to disk, verifying size and (when supplied) SHA-256
     * before the file is considered good.
     *
     * <p>Resumable: bytes land in {@code <dest>.part} plus a sibling
     * {@code <dest>.etag} holding the validator, and a restart sends
     * {@code Range: bytes=<len>-} with {@code If-Range} so a CHANGED remote
     * object is detected instead of being spliced onto stale bytes. A
     * {@code 200} answer to a Range request (or a changed validator) means the
     * server declined to resume, so that file restarts from zero.
     *
     * <p>Returns the number of bytes this attempt wrote, or -1 on failure. The
     * {@code .part} file is KEPT on a cancel or a transport error so the next run
     * can resume it; it is deleted when verification fails, because those bytes
     * are known bad.
     */
    private long fetchOne(String urlStr, File dest, long expected, String sha,
                          File scratchDir, State state) {
        HttpURLConnection conn = null;
        InputStream in = null;
        FileOutputStream out = null;
        try {
            final File part = new File(scratchDir, dest.getName() + ".part");
            final File etagFile = new File(scratchDir, dest.getName() + ".etag");
            long have = (part.isFile() && expected > 0 && part.length() < expected)
                    ? part.length() : 0;
            final String validator = have > 0 ? readValidator(etagFile) : "";

            conn = openHttps(urlStr, have, validator);
            if (conn == null) {
                state.message = "download failed";
                return -1;
            }
            if (conn.getResponseCode() == 416 && have > 0) {
                // "Unsatisfiable range": the .part is at or past the remote
                // length, so it is stale garbage. Start over.
                android.util.Log.w(TAG, "range unsatisfiable for " + urlStr + "; restarting");
                conn.disconnect();
                part.delete();
                etagFile.delete();
                have = 0;
                conn = openHttps(urlStr, 0, "");
                if (conn == null) {
                    state.message = "download failed";
                    return -1;
                }
            }
            final int code = conn.getResponseCode();
            if (code == 200 && have > 0) {
                // The server ignored the Range, or If-Range says the object
                // changed. Either way these bytes replace what we hold, so
                // appending would splice two different files together.
                android.util.Log.i(TAG, "server declined resume for " + urlStr
                        + "; restarting that file from zero");
                part.delete();
                etagFile.delete();
                have = 0;
            } else if (code != 200 && code != 206) {
                android.util.Log.w(TAG, "HTTP " + code + " for " + urlStr);
                state.message = "download failed (HTTP " + code + ")";
                return -1;
            }
            // Record the validator BEFORE writing bytes: If-Range must describe
            // the representation these bytes actually belong to.
            final String newValidator = conn.getHeaderField("ETag") != null
                    ? conn.getHeaderField("ETag")
                    : conn.getHeaderField("Last-Modified");
            if (newValidator != null && !newValidator.isEmpty())
                writeValidator(etagFile, newValidator);

            in = new java.io.BufferedInputStream(conn.getInputStream(), 1 << 16);
            out = new FileOutputStream(part, have > 0);
            final byte[] buf = new byte[1 << 16];
            long written = have;
            long windowStart = System.currentTimeMillis();
            long windowBytes = 0;
            while (true) {
                if (sCanceled) {
                    android.util.Log.i(TAG, "cancelled during " + urlStr);
                    state.message = "cancelled";
                    return -1;
                }
                final int n = in.read(buf);
                if (n < 0) break;
                out.write(buf, 0, n);
                written += n;
                windowBytes += n;
                // Speed over a 1s window. Reported as a plain byte rate; the C++
                // side formats the unit for display.
                final long elapsed = System.currentTimeMillis() - windowStart;
                if (elapsed >= 1000) {
                    state.speed = (windowBytes * 1000L) / elapsed + " B/s";
                    windowStart = System.currentTimeMillis();
                    windowBytes = 0;
                    writeState(getApplicationContext(), state);
                    updateNotification(state);
                }
                // The catalog's sizeBytes is hand-maintained, so a file that
                // outgrew it means the manifest is wrong: stop rather than fill
                // the disk with bytes nobody asked for.
                if (expected > 0 && written > expected) {
                    android.util.Log.w(TAG, "overflowed expected size for " + urlStr);
                    return -1;
                }
            }
            out.flush();
            out.close();
            out = null;
            in.close();
            in = null;
            if (expected > 0 && written != expected) {
                // A short read is a transport problem, not a bad file: keep the
                // .part so the next attempt can resume from here.
                android.util.Log.w(TAG, "short read for " + urlStr + ": " + written
                        + " != " + expected);
                state.message = "download was incomplete";
                return -1;
            }
            if (!shaMatches(part, sha)) {
                android.util.Log.w(TAG, "checksum mismatch for " + urlStr);
                part.delete();
                etagFile.delete();
                state.message = "download failed its checksum";
                return -1;
            }
            // Only now is the file complete: publish it under its real name and
            // drop the resume metadata.
            if (dest.isFile() && !dest.delete()) {
                android.util.Log.w(TAG, "could not replace " + dest);
                return -1;
            }
            if (!part.renameTo(dest)) {
                android.util.Log.e(TAG, "rename " + part + " -> " + dest + " failed");
                return -1;
            }
            etagFile.delete();
            // Only the bytes this attempt appended, so a resumed file is not
            // counted twice in the progress bar.
            return written - have;
        } catch (Exception e) {
            android.util.Log.w(TAG, "fetchOne(" + urlStr + ") failed: " + e);
            state.message = "download failed";
            return -1;
        } finally {
            try { if (in != null) in.close(); } catch (Exception ignored) { }
            try { if (out != null) out.close(); } catch (Exception ignored) { }
            try { if (conn != null) conn.disconnect(); } catch (Exception ignored) { }
            // Only a file that was actually renamed into place is a candidate for
            // cleanup; a .part still on disk is resumable partial state and is
            // deliberately KEPT (a cancel or a transport error should not throw
            // away the bytes). Bytes we could not trust (failed size/checksum)
            // were deleted above.
            if (dest.isFile() && !isComplete(dest, expected, sha)) dest.delete();
        }
    }

    /**
     * Opens an HTTPS connection, following redirects manually so the transport
     * can never be downgraded by one. {@code rangeFrom > 0} adds
     * {@code Range: bytes=<n>-} plus {@code If-Range}, which makes the resume
     * conditional on the bytes already held: if the remote object changed, the
     * server answers 200 with the whole thing and the caller restarts that file.
     * Returns null when the url or any redirect is not https, or the connection
     * could not be opened.
     */
    private static HttpURLConnection openHttps(String urlStr, long rangeFrom, String ifRange) {
        try {
            if (!urlStr.startsWith("https://")) {
                android.util.Log.w(TAG, "refusing non-https url " + urlStr);
                return null;
            }
            String next = urlStr;
            for (int hop = 0; hop < 5; hop++) {
                final HttpURLConnection conn = (HttpURLConnection) new URL(next).openConnection();
                conn.setConnectTimeout(30000);
                conn.setReadTimeout(60000);
                conn.setInstanceFollowRedirects(false);
                conn.setRequestProperty("User-Agent", "Aurelex");
                if (rangeFrom > 0) {
                    conn.setRequestProperty("Range", "bytes=" + rangeFrom + "-");
                    if (ifRange != null && !ifRange.isEmpty())
                        conn.setRequestProperty("If-Range", ifRange);
                }
                conn.connect();
                final int code = conn.getResponseCode();
                if (code >= 300 && code < 400) {
                    next = conn.getHeaderField("Location");
                    conn.disconnect();
                    if (next == null || !next.startsWith("https://")) {
                        android.util.Log.w(TAG, "refusing redirect to " + next);
                        return null;
                    }
                    continue;
                }
                return conn;
            }
            android.util.Log.w(TAG, "too many redirects for " + urlStr);
            return null;
        } catch (Exception e) {
            android.util.Log.w(TAG, "openHttps(" + urlStr + ") failed: " + e);
            return null;
        }
    }

    private static String readValidator(File f) {
        try (java.io.BufferedReader r = new java.io.BufferedReader(
                new java.io.FileReader(f))) {
            final String line = r.readLine();
            return line == null ? "" : line.trim();
        } catch (Exception e) {
            return "";
        }
    }

    private static void writeValidator(File f, String v) {
        try (java.io.FileWriter w = new java.io.FileWriter(f)) {
            w.write(v);
        } catch (Exception e) {
            android.util.Log.w(TAG, "writeValidator failed: " + e);
        }
    }

    private static boolean isComplete(File dest, long expected, String sha) {
        if (expected > 0 && dest.length() != expected) return false;
        return shaMatches(dest, sha);
    }

    /** SHA-256 of a file against the catalog value; "" means "skip the check". */
    private static boolean shaMatches(File f, String sha) {
        if (sha == null || sha.isEmpty()) return true;
        try {
            final MessageDigest md = MessageDigest.getInstance("SHA-256");
            final byte[] want = hexToBytes(sha);
            try (InputStream in = new java.io.BufferedInputStream(
                    new java.io.FileInputStream(f), 1 << 16)) {
                final byte[] buf = new byte[1 << 16];
                int n;
                while ((n = in.read(buf)) > 0) md.update(buf, 0, n);
            }
            return MessageDigest.isEqual(md.digest(), want);
        } catch (Exception e) {
            android.util.Log.w(TAG, "shaMatches failed: " + e);
            // A verification we could not perform must not silently pass.
            return false;
        }
    }

    private static byte[] hexToBytes(String hex) {
        final int n = hex.length() / 2;
        final byte[] out = new byte[n];
        for (int i = 0; i < n; i++) {
            out[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }

    private void updateNotification(State state) {
        try {
            final android.app.NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null)
                nm.notify(NOTIFICATION_ID, buildNotification(
                        state.filesDone, state.filesTotal, state.bytesDone, state.entryName));
        } catch (Exception ignored) {
        }
    }

    @Override
    public void onDestroy() {
        try {
            stopForeground(true);
        } catch (Exception e) {
            android.util.Log.w(TAG, "onDestroy: " + e);
        }
        android.util.Log.i(TAG, "DictionaryDownloadService stopped");
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        final NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, getString(R.string.notification_channel_dict_download),
                NotificationManager.IMPORTANCE_LOW);
        try {
            getSystemService(NotificationManager.class).createNotificationChannel(channel);
        } catch (Exception e) {
            android.util.Log.w(TAG, "createChannel failed: " + e);
        }
    }

    private Notification buildNotification(int filesDone, int filesTotal, long bytesDone, String name) {
        final Intent open = new Intent(this, AurelexActivity.class);
        open.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        final PendingIntent pi = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        final Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        final String text = filesTotal > 0
                ? getString(R.string.notification_downloading_progress,
                        filesDone, filesTotal, name)
                : getString(R.string.notification_downloading);
        if (filesTotal > 0) {
            builder.setProgress(filesTotal, filesDone, false);
        }
        return builder
                .setContentTitle(getString(R.string.notification_title))
                .setContentText(text)
                .setSmallIcon(R.drawable.ic_notification)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
    }
}
