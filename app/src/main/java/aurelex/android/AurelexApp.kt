package aurelex.android

import android.app.Application

class AurelexApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // Engine init runs on the dedicated native thread (queued): sets HOME,
        // builds the QGuiApplication, and creates the ArticleMaker seam. It is
        // idempotent on the C side, so a later explicit init is harmless.
        NativeEngine.init(this)
    }

    override fun onTerminate() {
        // Only invoked in controlled environments (emulator/instrumentation),
        // but keeps the contract explicit: teardown on exit.
        NativeEngine.cleanup()
        super.onTerminate()
    }
}