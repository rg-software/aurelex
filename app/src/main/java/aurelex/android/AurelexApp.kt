package aurelex.android

import android.app.Application
import android.content.Context
import android.content.Intent

class AurelexApp : Application() {
    companion object {
        /** UI registers a handler to re-scan staged dicts when the engine dies. */
        @Volatile
        var onEngineDied: ((Context) -> Unit)? = null

        /** The app context (used by the engine-died handler). */
        @Volatile
        var appContext: Context? = null
    }

    override fun onCreate() {
        super.onCreate()
        appContext = this

        // Engine runs in the separate `:engine` process (loads Qt libs there,
        // never in the Compose UI process). Start it as a FOREGROUND service so
        // the engine process survives UI activity recreation (e.g. after a SAF
        // folder grant restarts the activity). The UI then binds + proxies via
        // EngineClient over Binder (Messenger).
        if (android.os.Build.VERSION.SDK_INT >= 26) {
            startForegroundService(Intent(this, EngineService::class.java))
        } else {
            startService(Intent(this, EngineService::class.java))
        }
        EngineClient.bind(this)
        // When the engine process is killed (e.g. by a storage-grant package
        // restart), ask the UI to re-scan the staged dictionaries.
        EngineClient.onEngineDied = {
            onEngineDied?.invoke(appContext ?: this)
        }
    }

    override fun onTerminate() {
        super.onTerminate()
    }
}
