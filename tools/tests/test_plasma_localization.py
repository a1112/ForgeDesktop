"""Translation lookup and the localized artifact trust boundary."""

import gettext
import io
from pathlib import Path
import unittest

from tools.build_plasma_bundle import eligible_path, validate_session_entry


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ("plasma/plasmoids/org.forge.windowcontrols/contents/locale/zh_CN/"
           "LC_MESSAGES/plasma_applet_org.forge.windowcontrols.mo")
DESTINATION = "usr/share/" + CATALOG


class PlasmaLocalizationTests(unittest.TestCase):
    def test_chinese_catalog_translates_controls_and_preserves_title_placeholder(self):
        path = ROOT / CATALOG
        self.assertTrue(path.is_file(), "Chinese catalogue is not shipped")
        translation = gettext.GNUTranslations(io.BytesIO(path.read_bytes()))
        expected = {
            "Window controls": "窗口控制",
            "Active window: %1": "当前窗口：%1",
            "Minimize active window": "最小化当前窗口",
            "Restore active window": "还原当前窗口",
            "Close active window": "关闭当前窗口",
        }
        for source, chinese in expected.items():
            self.assertEqual(translation.gettext(source), chinese)
        self.assertEqual(translation.gettext("Untranslated fallback"),
                         "Untranslated fallback")

    def test_only_the_reviewed_catalogue_path_is_eligible(self):
        self.assertTrue(eligible_path(DESTINATION))
        for path in (DESTINATION.replace("zh_CN", "unreviewed"),
                     DESTINATION.replace(".mo", ".py"),
                     DESTINATION.replace("windowcontrols.mo", "other.mo")):
            self.assertFalse(eligible_path(path))

    def test_localized_session_display_fields_do_not_change_commands(self):
        entry = (ROOT / "plasma/session/forgedesktop-kwin.desktop").read_bytes()
        localized = (entry.decode("utf-8")
                     + "Name[zh_CN]=ForgeDesktop 桌面（KWin）\n"
                     + "Comment[zh_CN]=ForgeOS 的 KWin 与 Plasma Wayland 桌面\n")
        # Remove shipped translations to exercise both old and new receipts.
        localized = "\n".join(line for line in localized.splitlines()
                              if not line.startswith(("Name[zh_CN]=", "Comment[zh_CN]=")))
        localized += ("\nName[zh_CN]=ForgeDesktop 桌面（KWin）\n"
                      "Comment[zh_CN]=ForgeOS 的 KWin 与 Plasma Wayland 桌面\n")
        validate_session_entry(localized.encode())
        with self.assertRaises(ValueError):
            validate_session_entry((localized + "Exec[zh_CN]=/bin/sh\n").encode())
        with self.assertRaises(ValueError):
            validate_session_entry(localized.replace(
                "Exec=/usr/libexec/forge-desktop/forge-kwin-session",
                "Exec=/bin/sh").encode())


if __name__ == "__main__":
    unittest.main()
