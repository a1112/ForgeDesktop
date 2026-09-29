// SPDX-License-Identifier: MIT
// Pinned Plasma 6 observer. Does not grant access or perform window operations.
function publish(value) {
    callDBus("org.forge.WindowObserver1", "/WindowObserver", "org.forge.WindowObserver1",
        "Observe", JSON.stringify(value));
}
function identifier(window) { return String(window.internalId); }
function eligible(window) { return window && !window.desktopWindow && !window.dock && (!window.specialWindow || window.popupWindow || window.dialog); }
function observe(window) {
    if (!eligible(window)) return;
    var geometry = window.frameGeometry;
    publish({type: "window", id: identifier(window), parent: window.transientFor ? identifier(window.transientFor) : null,
        kind: window.popupWindow ? "popup" : (window.dialog ? "dialog" : "normal"),
        caption: String(window.caption).slice(0,4096), app_id: String(window.desktopFileName).slice(0,1024),
        geometry: {x: Math.round(geometry.x), y: Math.round(geometry.y), width: Math.round(geometry.width), height: Math.round(geometry.height)}});
}
function attach(window) {
    if (!eligible(window)) return;
    observe(window);
    window.frameGeometryChanged.connect(function() { observe(window); });
    window.captionChanged.connect(function() { observe(window); });
    window.closed.connect(function() { publish({type: "closed", id: identifier(window)}); });
}
workspace.windowAdded.connect(attach);
workspace.windowActivated.connect(function(window) {
    if (eligible(window)) publish({type: "active", id: identifier(window)});
});
workspace.windowList().forEach(attach);
