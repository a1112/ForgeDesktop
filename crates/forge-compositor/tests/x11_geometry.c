#define _POSIX_C_SOURCE 200809L
#include <X11/Xlib.h>
#include <stdio.h>
#include <time.h>

static void settle(Display *display) {
    XSync(display, False);
    struct timespec delay = {.tv_sec = 0, .tv_nsec = 300000000};
    nanosleep(&delay, NULL);
}
static int size_is(Display *display, Window window, int width, int height) {
    XWindowAttributes attributes;
    XGetWindowAttributes(display, window, &attributes);
    printf("X11 geometry:%dx%d expected:%dx%d\n", attributes.width, attributes.height, width, height);
    return attributes.width == width && attributes.height == height;
}
int main(void) {
    Display *display = XOpenDisplay(NULL);
    if (!display) return 2;
    Window window = XCreateSimpleWindow(display, DefaultRootWindow(display), 0, 0, 640, 480, 0, 0, 0x00ff00);
    settle(display);
    // A ConfigureRequest may arrive before MapRequest. The WM must honor it.
    XResizeWindow(display, window, 128, 160);
    settle(display);
    XMapWindow(display, window);
    settle(display);
    int ok = size_is(display, window, 128, 160);
    XResizeWindow(display, window, 192, 224);
    settle(display);
    ok &= size_is(display, window, 192, 224);
    XDestroyWindow(display, window);
    XCloseDisplay(display);
    return ok ? 0 : 1;
}
