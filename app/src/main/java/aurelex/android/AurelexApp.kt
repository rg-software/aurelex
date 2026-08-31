package aurelex.android

import android.app.Application

class AurelexApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // Engine init (gd_init, which builds Qt's QCoreApplication). Qt on
        // Android requires its application object on the MAIN thread, so this
        // runs synchronously on the main looper and blocks until done.
        NativeEngine.init(this)
    }

    override fun onTerminate() {
        // Only invoked in controlled environments (emulator/instrumentation),
        // but keeps the contract explicit: teardown on exit.
        NativeEngine.cleanup()
        super.onTerminate()
    }
}