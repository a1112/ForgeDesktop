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

The Forge Dark Aurorae SVG frame/buttons and the Fusion Plasma widget are
original MIT assets drawn from the R-OS interaction description, not copied
R-OS source or images. The button dimensions, dark surfaces, pale glyphs and
red close hover follow the observed interaction pattern. Their runtime uses
the already pinned KWin and plasma-workspace packages; no new binary library
is bundled. R-OS application tabs are not replicated for arbitrary clients.

New build dependencies are the existing pinned Arch snapshot 2026/08/01:
Qt6 base 6.11.1-1, declarative 6.11.1-3, wayland 6.11.1-1, svg 6.11.1-1;
GIO/glib2 2.88.3-1, GCC 16.1.1, CMake/Ninja. Package signature/digest receipts
are held with the M0 builder records. No new Rust crate is added. Qt's dynamic
libraries retain their upstream LGPL/GPL/commercial terms (see installed Qt
package licensing); GLib/GIO are LGPL-2.1-or-later. Shell code is MIT like this
repository. ForgeOS must ship the dependency/license inventory with artifacts.

The 2026-10-07 visual update adds original MIT GTK 3/4 CSS, Plasma style
metadata/color files and panel/task SVG geometry. Its graphite palette and
traffic-light controls follow the approved shared design contract. It copies
no Apple, R-OS, KDE or GTK stylesheets, icons, fonts or bitmap assets. Plasma
falls back to the installed upstream Breeze theme for widgets beyond the
original panel/task frames. GTK styles use built-in toolkit glyphs and contain
no external resource references. The candidate session exports GTK_THEME only
when installed and without replacing a user override; no home state is written.
Qt, GTK, Plasma and installed application icons retain their upstream licenses.
No new binary dependency or package closure is added. Theme installation and
source tests do not certify visual behavior in the exact pinned desktop.
