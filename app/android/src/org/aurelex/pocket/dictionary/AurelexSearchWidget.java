package org.aurelex.pocket.dictionary;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.widget.RemoteViews;

/**
 * Home-screen search widget: the whole bar is tappable and opens the app's
 * search screen (matching the shipped app's design D2 — RemoteViews widgets
 * cannot reliably capture typed text).
 */
public class AurelexSearchWidget extends AppWidgetProvider {

    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] appWidgetIds) {
        for (int id : appWidgetIds) {
            appendPendingIntent(context, manager, id);
        }
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        super.onReceive(context, intent);
        // Re-wire after a submit in case the launcher re-created the widget.
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        int[] ids = manager.getAppWidgetIds(
                new ComponentName(context, AurelexSearchWidget.class));
        for (int id : ids) {
            appendPendingIntent(context, manager, id);
        }
    }

    private void appendPendingIntent(Context context, AppWidgetManager manager, int appWidgetId) {
        Intent search = new Intent(context, AurelexActivity.class);
        PendingIntent pending = PendingIntent.getActivity(
                context, appWidgetId, search,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.widget_search);
        views.setOnClickPendingIntent(R.id.widget_search_root, pending);
        manager.updateAppWidget(appWidgetId, views);
    }
}
