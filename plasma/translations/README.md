# ForgeDesktop translations

English source strings are the fallback. Simplified Chinese uses the standard
Plasma gettext domain `plasma_applet_org.forge.windowcontrols` and package-local
`contents/locale` catalogue. Theme, applet and session display metadata also
include `zh_CN`; executable desktop-entry keys are never translated.

Regenerate the checked-in catalogue on a Linux build host:

```sh
msgfmt --check --check-format -o \
  plasma/plasmoids/org.forge.windowcontrols/contents/locale/zh_CN/LC_MESSAGES/plasma_applet_org.forge.windowcontrols.mo \
  plasma/translations/zh_CN.po
python3 -m unittest discover -s tools/tests -q
```

The build host uses Ubuntu's official gettext 0.23.2-1 package; gettext is a
build tool only. Plasma's existing ki18n runtime loads the catalogue. The
catalogue source and binary are MIT licensed and declared in dependencies.json.

ForgeOS generates `zh_CN.UTF-8` and `en_US.UTF-8`, sets Chinese system/KDE
defaults, and preserves per-user choices. Change languages using Plasma
**System Settings → Region & Language**, apply, and log out/in. Upstream KDE,
GTK and Firefox translations are supplied by their signed Arch packages.

Reference: https://develop.kde.org/docs/plasma/widget/translations-i18n/
