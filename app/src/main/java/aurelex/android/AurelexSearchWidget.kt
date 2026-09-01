package aurelex.android

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews

/**
 * Home-screen search widget. Renders a search field whose tap and IME search
 * action both fire an [QuickLookup.ACTION_SEARCH] intent at [MainActivity]
 * (design D2). [QuickLookup.ACTION_REFRESH_WIDGET] is sent by the activity
 * after it has handled a submit, re-wiring the RemoteViews so the PendingIntent
 * stays fresh (task 3.2).
 */
class AurelexSearchWidget : AppWidgetProvider() {

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        for (appWidgetId in appWidgetIds) {
            appWidgetManager.updateAppWidget(appWidgetId, buildViews(context))
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        if (intent.action == QuickLookup.ACTION_REFRESH_WIDGET) {
            val appWidgetManager = AppWidgetManager.getInstance(context)
            val ids = intent.getIntArrayExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS)
                ?: appWidgetManager.getAppWidgetIds(
                    ComponentName(context, AurelexSearchWidget::class.java)
                )
            for (appWidgetId in ids) {
                appWidgetManager.updateAppWidget(appWidgetId, buildViews(context))
            }
        }
    }

    private fun buildViews(context: Context): RemoteViews {
        val views = RemoteViews(context.packageName, R.layout.widget_search)
        appendPendingIntent(context, views, R.id.widget_search_root)
        return views
    }

    private fun appendPendingIntent(context: Context, views: RemoteViews, viewId: Int) {
        val search = Intent(context, MainActivity::class.java).apply {
            action = QuickLookup.ACTION_SEARCH
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            // Launchers that deliver the field's text on submit put it here;
            // blank text routes to the in-app search screen (design D2).
            putExtra(QuickLookup.EXTRA_TEXT, "")
        }
        val pending = PendingIntent.getActivity(
            context,
            0,
            search,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        views.setOnClickPendingIntent(viewId, pending)
    }
}