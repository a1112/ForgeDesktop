/* Isolated M1 integration fixture: an actual GTK Wayland client. */
#include <gtk/gtk.h>
#include <stdio.h>

static void changed(GtkEditable *entry, gpointer unused) {
    (void) unused;
    printf("gtk-entry:%s\n", gtk_entry_get_text(GTK_ENTRY(entry)));
    fflush(stdout);
}
int main(int argc, char **argv) {
    gtk_init(&argc, &argv);
    GtkWidget *window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    GtkWidget *header = gtk_header_bar_new();
    gtk_header_bar_set_title(GTK_HEADER_BAR(header), "ForgeDesktop GTK native probe");
    gtk_header_bar_set_show_close_button(GTK_HEADER_BAR(header), TRUE);
    gtk_window_set_titlebar(GTK_WINDOW(window), header);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 16);
    gtk_container_set_border_width(GTK_CONTAINER(box), 24);
    gtk_container_add(GTK_CONTAINER(window), box);
    gtk_box_pack_start(GTK_BOX(box), gtk_label_new("Real GTK 3 / Wayland / Pixman\nChinese text: 中文输入验证"), FALSE, FALSE, 8);
    GtkWidget *entry = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(entry), "Keyboard input is logged by this fixture");
    gtk_box_pack_start(GTK_BOX(box), entry, FALSE, FALSE, 8);
    gtk_box_pack_start(GTK_BOX(box), gtk_button_new_with_label("Native GTK button"), FALSE, FALSE, 8);
    g_signal_connect(entry, "changed", G_CALLBACK(changed), NULL);
    g_signal_connect(window, "destroy", G_CALLBACK(gtk_main_quit), NULL);
    gtk_widget_show_all(window);
    gtk_widget_grab_focus(entry);
    printf("gtk-ready\n"); fflush(stdout);
    gtk_main();
    return 0;
}
