# Chinese-default bilingual desktop

The user approved Simplified Chinese as the default and complete Chinese/English
acceptance on 2026-09-28. Use the existing KWin/Plasma desktop and its Region &
Language settings. ForgeDesktop owns its translated UI and metadata; ForgeOS
owns generated locales, image defaults and signed application language packs.

Use KDE's gettext/ki18n mechanism for the Fusion applet, including accessible
names and visible hover tooltips. Ship an original MIT Chinese PO source and
compiled MO catalogue in the closed, digest-pinned bundle. English source
strings are the fallback. Add translated display names to the look-and-feel,
decoration and login entry without changing executable commands. The wallpaper
uses the language-neutral Forge brand. Upstream KDE/GTK translations remain
upstream assets; Firefox receives the matching signed Chinese language pack.

ForgeOS generates zh_CN.UTF-8 and en_US.UTF-8 and sets Chinese system and KDE
defaults. Do not force LC_ALL or override a user's explicit language at each
login. Region & Language saves per-user settings; the next login consistently
applies the language to the desktop and newly launched applications. Preserve
existing home-directory paths and the XFCE recovery session.

Rejected alternatives: replacing English strings with Chinese literals would
prevent switching; a separate Forge language daemon or settings surface would
duplicate existing Plasma functionality. Additional languages can later add
catalogues and locales through the same build and verification path.

Acceptance includes catalogue lookup and placeholder preservation, tamper and
off-scope bundle rejection, generated locales, Chinese default after login,
English switching and return to Chinese, actual GTK/Qt UI, Firefox language,
Fusion tooltip translation and normal window actions. Keep VM state recoverable
with a clean shutdown and overlay backup. No default desktop-session switch or
performance claim is part of this change.

References:
- https://develop.kde.org/docs/plasma/widget/translations-i18n/
- https://wiki.archlinux.org/title/Locale
