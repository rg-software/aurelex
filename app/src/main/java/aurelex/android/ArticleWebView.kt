package aurelex.android

import android.content.Context
import android.content.res.AssetManager
import android.webkit.MimeTypeMap
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.runtime.Composable
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.util.concurrent.ExecutionException

/**
 * Renders an engine article (upstream article_maker HTML) in a WebView and
 * intercepts goldendict's custom URL schemes (design D4/D9):
 *
 * - `qrc:///`  → served from the Android asset mirror of upstream scripts/
 *   stylesheets/icons/flags (URL→asset map below).
 * - `bres://`  → embedded dictionary resource via gd_get_resource (mdd images).
 * - `gdau://`  → audio anchor: fetch via gd_get_audio and play on-device
 *   (ogg/mp3/wav; speex reported unsupported, never crashes).
 * - `gdlookup://` → in-app article navigation (task 5.6); http/https links are
 *   swallowed (v1 has no external article sources).
 */
class ArticleWebView(
    private val context: Context,
    private val onLookup: (String) -> Unit,
    private val onAudioResult: (String) -> Unit,
) {

    private val audioPlayer = AudioPlayer(context.applicationContext)

    fun render(webView: WebView, html: String) {
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webViewClient = createClient()
        webView.loadDataWithBaseURL("qrc:///", html, "text/html", "UTF-8", null)
    }

    private fun createClient(): WebViewClient = object : WebViewClient() {

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val url = request.url
            return when (url.scheme) {
                "gdlookup" -> {
                    // In-article link → in-app lookup. e.g. gdlookup://localhost/?word=foo
                    val word = url.getQueryParameter("word")
                        ?: url.host?.takeIf { it.isNotBlank() && it != "localhost" }
                        ?: ""
                    if (word.isNotBlank()) {
                        onLookup(word)
                        true
                    } else {
                        false
                    }
                }
                "gdau" -> {
                    playAudio(url.toString())
                    true
                }
                "http", "https" -> true // swallow: no external sources in v1
                else -> false
            }
        }

        override fun shouldInterceptRequest(
            view: WebView,
            request: WebResourceRequest
        ): WebResourceResponse? {
            val url = request.url
            return when {
                url.scheme == "qrc" -> serveQrc(url.path)
                url.scheme == "bres" -> serveEngineResource(url.toString())
                url.scheme == "gico" -> null // dict icon; article renders without it
                else -> null
            }
        }
    }

    private fun playAudio(url: String) {
        audioPlayer.play(url) { result ->
            when (result) {
                is AudioResult.Unsupported -> onAudioResult("Unsupported audio: ${result.reason}")
                is AudioResult.Error -> onAudioResult("Audio error: ${result.message}")
                is AudioResult.Playing -> Unit
            }
        }
    }

    /** Maps a qrc:/// path to an Android asset and returns it (design D9). */
    private fun serveQrc(path: String?): WebResourceResponse? {
        if (path == null) return null

        // Upstream emits: qrc:///scripts/x.js, qrc:///article-style*.css,
        // qrc:///qtwebchannel/qwebchannel.js, qrc:///icons/*, qrc:///flags/*.
        val assetPath = when {
            path.startsWith("/scripts/") -> "scripts/${path.removePrefix("/scripts/")}"
            path.startsWith("/stylesheets/") -> "stylesheets/${path.removePrefix("/stylesheets/")}"
            path.startsWith("/qtwebchannel/") -> "qtwebchannel/${path.removePrefix("/qtwebchannel/")}"
            path.startsWith("/icons/") -> "icons/${path.removePrefix("/icons/")}"
            path.startsWith("/flags/") -> "flags/${path.removePrefix("/flags/")}"
            path.endsWith(".css") && !path.contains('/') -> "stylesheets/${path.removePrefix("/")}"
            else -> null
        } ?: return null

        val input = openAsset(assetPath) ?: return null
        return WebResourceResponse(mimeFor(assetPath), "UTF-8", input)
    }

    private fun openAsset(assetPath: String): InputStream? =
        try {
            context.assets.open(assetPath)
        } catch (e: Exception) {
            null
        }

    /** Fetches a bres:// (or gdau:// used as an <img> subresource) via the engine. */
    private fun serveEngineResource(url: String): WebResourceResponse? {
        val bytes = try {
            EngineClient.getResource(url).get()
        } catch (e: ExecutionException) {
            null
        } catch (e: InterruptedException) {
            null
        } ?: return null
        val sub = url.substringBefore('?').substringAfterLast('.').lowercase()
        val mime = when (sub) {
            "jpg", "jpeg" -> "image/jpeg"
            "png" -> "image/png"
            "gif" -> "image/gif"
            "svg" -> "image/svg+xml"
            "webp" -> "image/webp"
            "mp3" -> "audio/mpeg"
            "ogg" -> "audio/ogg"
            "wav" -> "audio/x-wav"
            else -> "application/octet-stream"
        }
        return WebResourceResponse(mime, null, ByteArrayInputStream(bytes))
    }

    private fun mimeFor(path: String): String =
        MimeTypeMap.getSingleton().getMimeTypeFromExtension(path.substringAfterLast('.', ""))
            ?: "application/octet-stream"
}

@Composable
fun ArticleView(
    word: String,
    html: String,
    onLookup: (String) -> Unit,
    onAudioResult: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    // key(word) rebuilds the WebView when the article changes (in-article links
    // navigate to a different word, which is a distinct article).
    key(word) {
        AndroidView(
            modifier = modifier,
            factory = { ctx ->
                val webView = WebView(ctx)
                ArticleWebView(ctx, onLookup, onAudioResult).render(webView, html)
                webView
            }
        )
    }
}