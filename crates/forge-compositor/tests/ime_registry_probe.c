#include <wayland-client.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
static bool text_input, input_method, virtual_keyboard, xwayland_shell;
static void global(void *data, struct wl_registry *r, uint32_t name, const char *iface, uint32_t version) {
    (void)data; (void)r; (void)name; (void)version;
    if (!strcmp(iface, "zwp_text_input_manager_v3")) text_input = true;
    if (!strcmp(iface, "zwp_input_method_manager_v2")) input_method = true;
    if (!strcmp(iface, "zwp_virtual_keyboard_manager_v1")) virtual_keyboard = true;
    if (!strcmp(iface, "xwayland_shell_v1")) xwayland_shell = true;
}
static void removed(void *d, struct wl_registry *r, uint32_t n) { (void)d; (void)r; (void)n; }
int main(void) {
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) return 2;
    struct wl_registry *registry = wl_display_get_registry(display);
    const struct wl_registry_listener listener = {global, removed};
    wl_registry_add_listener(registry, &listener, NULL);
    if (wl_display_roundtrip(display) < 0) return 3;
    printf("ordinary-client:text-input=%d,input-method=%d,virtual-keyboard=%d\n", text_input, input_method, virtual_keyboard);
    printf("ordinary-client:xwayland-shell=%d\n", xwayland_shell);
    wl_registry_destroy(registry);
    wl_display_disconnect(display);
    return text_input && !input_method && !virtual_keyboard && !xwayland_shell ? 0 : 1;
}
