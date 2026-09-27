#include <gtk/gtk.h>
#include <stdio.h>
#include <string.h>

static const char *text = "Forge 中文剪贴板 😀";
static const char *uri = "file:///tmp/Forge-%E4%B8%AD%E6%96%87.txt\r\n";
static gboolean key(GtkWidget *widget, GdkEventKey *event, gpointer data) {
    (void)widget; (void)data;
    if (event->keyval == GDK_KEY_p) {
        gtk_clipboard_set_text(gtk_clipboard_get(GDK_SELECTION_CLIPBOARD), text, -1);
        gtk_clipboard_set_text(gtk_clipboard_get(GDK_SELECTION_PRIMARY), text, -1);
        puts("owned:clipboard+primary"); fflush(stdout);
    }
    if (event->keyval == GDK_KEY_v) {
        gchar *copied = gtk_clipboard_wait_for_text(gtk_clipboard_get(GDK_SELECTION_CLIPBOARD));
        gchar *primary = gtk_clipboard_wait_for_text(gtk_clipboard_get(GDK_SELECTION_PRIMARY));
        printf("clipboard:%s\nprimary:%s\n", copied ? copied : "MISSING", primary ? primary : "MISSING");
        g_free(copied); g_free(primary); fflush(stdout);
    }
    return FALSE;
}
static void provide(GtkWidget *w, GdkDragContext *c, GtkSelectionData *s, guint info, guint t, gpointer d) {
    (void)w; (void)c; (void)info; (void)t; (void)d;
    gtk_selection_data_set(s, gdk_atom_intern_static_string("text/uri-list"), 8, (const guchar *)uri, strlen(uri));
}
static void receive(GtkWidget *w, GdkDragContext *c, gint x, gint y, GtkSelectionData *s, guint info, guint t, gpointer d) {
    (void)w; (void)x; (void)y; (void)info; (void)d;
    int n = gtk_selection_data_get_length(s);
    gboolean ok = n == (int)strlen(uri) && !memcmp(gtk_selection_data_get_data(s), uri, n);
    printf("drop:%s\n", ok ? "file-uri-exact" : "BAD"); fflush(stdout);
    gtk_drag_finish(c, ok, FALSE, t);
}
static void realized(GtkWidget *w, gpointer d) {
    (void)d;
    GdkPixbuf *image = gdk_pixbuf_new(GDK_COLORSPACE_RGB, TRUE, 8, 20, 20);
    gdk_pixbuf_fill(image, 0x00ff00ff);
    GdkCursor *cursor = gdk_cursor_new_from_pixbuf(gtk_widget_get_display(w), image, 3, 5);
    gdk_window_set_cursor(gtk_widget_get_window(w), cursor);
    g_object_unref(cursor); g_object_unref(image);
}
int main(int argc, char **argv) {
    gtk_init(&argc, &argv);
    GtkWidget *window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(window), argc > 1 ? argv[1] : "selection-probe");
    gtk_window_set_decorated(GTK_WINDOW(window), FALSE);
    GtkWidget *area = gtk_event_box_new();
    gtk_container_add(GTK_CONTAINER(window), area);
    gtk_container_add(GTK_CONTAINER(area), gtk_label_new("P copies Chinese text; V reads clipboard and primary; drag a file URI"));
    GtkTargetEntry targets[] = {{"text/uri-list", 0, 0}};
    gtk_drag_source_set(area, GDK_BUTTON1_MASK, targets, 1, GDK_ACTION_COPY);
    gtk_drag_dest_set(area, GTK_DEST_DEFAULT_ALL, targets, 1, GDK_ACTION_COPY);
    g_signal_connect(area, "drag-data-get", G_CALLBACK(provide), NULL);
    g_signal_connect(area, "drag-data-received", G_CALLBACK(receive), NULL);
    g_signal_connect(window, "key-press-event", G_CALLBACK(key), NULL);
    g_signal_connect(area, "realize", G_CALLBACK(realized), NULL);
    g_signal_connect(window, "destroy", G_CALLBACK(gtk_main_quit), NULL);
    gtk_widget_show_all(window);
    gtk_main();
}
