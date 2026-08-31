package aurelex.android

import android.content.Context
import java.io.File

/**
 * Version-stamps the dictionary index cache on disk (design D5, task 6.3).
 *
 * The engine skips/rebuilds per-dictionary indexes itself (signature checks).
 * What the app owns is the index *format* version: the pinned engine tag's
 * version string is injected as BuildConfig.ENGINE_VERSION on every build, so
 * when the engine submodule changes, indexes are invalidated and rebuilt —
 * surfacing "reindexing" to the user instead of silently reusing incompatible
 * indexes. Contract: never reuse indexes across engine versions.
 */
object IndexVersion {

    fun engineVersion(): String = BuildConfig.ENGINE_VERSION

    private fun stampFile(context: Context): File =
        File(context.filesDir, "index-version").also {
            if (!it.parentFile.exists()) it.parentFile.mkdirs()
        }

    /** True when the stored index format matches the running engine. */
    fun isCurrent(context: Context): Boolean =
        stampFile(context).takeIf { it.exists() }?.readText() == engineVersion()

    /** Records that indexes now match this engine version. */
    fun markCurrent(context: Context) {
        stampFile(context).writeText(engineVersion())
    }

    /** Clears the index cache and stamp (forces a full rebuild next scan). */
    fun invalidate(context: Context) {
        // The engine writes its btree index files (*.idx) directly into the
        // passed index dir (context.filesDir, see NativeEngine.init).
        context.filesDir.listFiles()?.forEach {
            if (it.isFile && it.name.endsWith(".idx")) it.delete()
        }
        stampFile(context).delete()
    }
}