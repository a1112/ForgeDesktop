// SPDX-License-Identifier: MIT
// Exact-source target: plasma-desktop/kscreenlocker 6.7.3. Runtime gate pending.
// Inherit the complete upstream root, including PAM flow, keyboard layout,
// accessibility, messages, multi-screen behavior and viewVisible contract.
import QtQuick
import "/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen" as Upstream

Upstream.LockScreen {
    Text {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 24
        text: "R-OS"
        color: "#60a5fa"
        font.pixelSize: 22
        font.weight: Font.DemiBold
        // Branding does not accept input or cover the authentication controls.
        Accessible.ignored: true
    }
}
