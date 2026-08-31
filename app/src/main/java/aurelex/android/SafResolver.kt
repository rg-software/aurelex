package aurelex.android

import android.content.Context
import android.net.Uri
import android.os.Environment
import android.provider.DocumentsContract
import java.io.File

/**
 * Resolves a SAF document-tree URI to a physical filesystem path where possible.
 *
 * The engine's gd_scan_dicts takes a real directory path (QDir-based), so the
 * app must hand it a path on disk. Two strategies (in order):
 *
 * 1. Resolve the tree URI to a filesystem path (works for the device's own
 *    ExternalStorageProvider: "primary:Downloads" → /storage/emulated/0/...).
 *    In-place scanning matters for large `.mdd` packs — no copying.
 * 2. If the provider cannot be resolved to a path (cloud/other providers),
 *    the caller copies the supported files into app-private storage and scans
 *    that copy (handled by [stageDictionaryFiles]).
 */
object SafResolver {

    /**
     * Returns the physical directory for [treeUri], or null if unresolvable.
     * [treeUri] is the result of ActivityResultContracts.OpenDocumentTree.
     */
    fun resolveTreePath(treeUri: Uri): String? {
        val docId = try {
            DocumentsContract.getTreeDocumentId(treeUri)
        } catch (e: IllegalArgumentException) {
            return null
        }
        android.util.Log.i("SafResolver", "docId=$docId treeUri=$treeUri")

        // "primary:<relative>" → /storage/emulated/0/<relative>
        if (docId.startsWith("primary:")) {
            val relative = docId.removePrefix("primary:")
            val base = Environment.getExternalStorageDirectory()
            return File(base, relative).absolutePath
        }

        // "home:<relative>" → /storage/emulated/0/<relative> (some providers)
        if (docId.startsWith("home:")) {
            val relative = docId.removePrefix("home:")
            val base = Environment.getExternalStorageDirectory()
            return File(base, relative).absolutePath
        }

        return null
    }

    /**
     * Copies supported dictionary files from a SAF tree into app-private
     * storage so QDir can reach them, returning the staging directory. Used
     * when [resolveTreePath] returns null.
     */
    fun stageDictionaryFiles(context: Context, treeUri: Uri, destDir: File): File {
        destDir.mkdirs()
        val supported = setOf("mdx", "mdd", "dsl", "dz", "ifo")
        val resolver = context.contentResolver
        val childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(
            treeUri, DocumentsContract.getTreeDocumentId(treeUri)
        )
        android.util.Log.i("SafResolver", "stage childrenUri=$childrenUri dest=$destDir")

        var stagedCount = 0
        resolver.query(
            childrenUri,
            arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME),
            null, null, null
        )?.use { cursor ->
            val idCol = cursor.getColumnIndex(DocumentsContract.Document.COLUMN_DOCUMENT_ID)
            val nameCol = cursor.getColumnIndex(DocumentsContract.Document.COLUMN_DISPLAY_NAME)
            while (cursor.moveToNext()) {
                val id = cursor.getString(idCol) ?: continue
                val name = cursor.getString(nameCol) ?: continue
                val ext = name.substringAfterLast('.', "").lowercase()
                if (ext in supported) {
                    val srcUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, id)
                    val out = File(destDir, name)
                    resolver.openInputStream(srcUri)?.use { input ->
                        out.outputStream().use { input.copyTo(it) }
                    }
                    stagedCount++
                }
            }
        }
        android.util.Log.i("SafResolver", "staged $stagedCount files into $destDir")
        return destDir
    }

    /** Finds the physical path of the "primary" storage root (for tests/CI). */
    fun primaryStorageRoot(): String = Environment.getExternalStorageDirectory().absolutePath
}