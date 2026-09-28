# Native shell visual provenance

Reference only: `L:/project/R-OS/R-OS-Web/components/os/TopBar.tsx` and `Dock.tsx`
inspected 2026-09-27. No repository license was located for those assets, so no
source, bitmap, wallpaper, icon geometry or stylesheet was copied.

`shell/qml/Desktop.qml` and `Action.qml` are original QML: a static dark gradient,
two rounded geometric background shapes, a 38px top bar, compact rounded Dock,
app grid/search, task controls and four workspace selectors. Flat translucent
colors and native Qt software rendering; no browser engine, blur, continuous
animation or dynamic wallpaper. Transitions currently have zero duration.
Unknown app icons are original colored rounded tiles with an initial. Real
application icons are loaded from installed packages at runtime, not bundled
or relicensed by ForgeDesktop. GTK/Qt app interiors remain their native themes.

The KWin candidate's `plasma/look-and-feel/` package is original MIT text and
SVG. Its navy palette and two rotated rounded shapes derive from the original
ForgeDesktop QML above. It contains no R-OS files or copied KDE assets. The
layout script uses documented Plasma panel/widget and wallpaper APIs; Breeze
Dark, Breeze icons and window decoration come from the pinned upstream Arch
packages under their own licenses. The theme is optional and does not rewrite
existing user settings during bundle installation.

New build dependencies are the existing pinned Arch snapshot 2026/08/01:
Qt6 base 6.11.1-1, declarative 6.11.1-3, wayland 6.11.1-1, svg 6.11.1-1;
GIO/glib2 2.88.3-1, GCC 16.1.1, CMake/Ninja. Package signature/digest receipts
are held with the M0 builder records. No new Rust crate is added. Qt's dynamic
libraries retain their upstream LGPL/GPL/commercial terms (see installed Qt
package licensing); GLib/GIO are LGPL-2.1-or-later. Shell code is MIT like this
repository. ForgeOS must ship the dependency/license inventory with artifacts.
