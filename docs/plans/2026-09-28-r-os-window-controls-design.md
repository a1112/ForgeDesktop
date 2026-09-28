# R-OS-inspired ForgeDesktop window controls

Date: 2026-09-28. The user approved implementing both ordinary window controls
and R-OS's maximized-window Fusion Mode on the KWin/Plasma ForgeDesktop route.
This extends the approved KWin/Plasma design and does not change the default
login session.

## Source behavior and approaches

R-OS `Window.tsx` uses a compact titlebar with right-aligned minimize,
maximize/restore and close controls, titlebar drag/double-click and a window
menu. `TopBar.tsx` moves the active maximized window's title and three controls
into the top bar. The reference uses white/gray text, dark translucent
surfaces, blue selection and red close hover. Its application tabs are internal
web-app state and cannot be extracted from arbitrary native applications.

1. **Selected:** a Forge Aurorae window decoration, the existing Plasma panel
and a Forge Plasma window-control widget backed by Plasma's task model. Use
KWin's own maximize, minimize, close, interactive move and tiling requests.
   This preserves native window behavior and isolates the Forge visual layer.
2. Replace Plasma with a custom Qt shell. This gives direct layout control but
   duplicates mature panel, task and session integration.
3. Fork KWin/Plasma. This offers the most exact visual control but makes every
   upstream update a substantial maintenance and security task.

## Ordinary window state

Install an original MIT-licensed Aurorae SVG decoration with a 32-pixel dark
titlebar, white/gray title, right-aligned 48-pixel minimize, maximize/restore
and close targets, subtle hover, and red destructive hover. Keep KWin's normal
titlebar double-click, drag, context menu, edge resize, focus and tile actions.
Avoid live blur and continuous animation in the 2-vCPU software-rendered VM.
The decoration applies only to windows for which KWin draws server-side frames;
applications that draw their own controls remain application-owned.

## Fusion state and control flow

For an active, fully maximized, non-fullscreen, ordinary task on the current
output, the top panel presents its title and enabled minimize, restore and close
buttons. A Plasma 6 widget reads `org.kde.taskmanager`'s `TasksModel` roles and
uses its request methods, never a shell command or a generic DBus window-control
service. The widget acts only on the model's current `activeTask` and rechecks
the active/maximized/capability roles at click time; it does not retain a stale
window ID. Empty, desktop, minimized, fullscreen, modal and unsupported tasks
have no Fusion controls. Controls have accessible labels and keyboard focus.

The corresponding KWin user setting removes the server-side frame of maximized
windows. The panel keeps its own screen reservation. The widget uses KWin's
`CanSetNoBorder`/`HasNoBorder` roles as eligibility hints; whether those roles
distinguish client-drawn headers is an explicit VM validation gate. If a client
still draws its own title buttons, Fusion controls must be disabled for that
client rather than displaying duplicate close targets. A failed/unknown model
state leaves KWin's native window decoration available. Restore returns to the
ordinary decoration. Fullscreen hides the panel through normal Plasma behavior.

The R-OS top-bar drag-to-restore gesture is accepted only if the task model's
interactive-move request works correctly after restore in the pinned VM; a
failed probe leaves the ordinary KWin `Meta`+drag path. The initial version
does not invent cross-application tabs or a hover-only snap-layout protocol.
KWin's native quick tiling and titlebar menu remain available.

## Packaging, security and acceptance

Extend the closed ForgeDesktop bundle allowlist and validators to cover the
Aurorae files and Plasma widget, with exact asset license records. ForgeOS pins
the new bundle digest before any image install. The existing XFCE and Smithay
sessions, user data and daily VM overlay remain recoverable. Test a disposable
KWin overlay first and do not switch the default session.

Automated checks reject missing buttons, invalid SVG, unsafe external SVG
references, off-scope files, malformed widget metadata and widened commands.
Guest acceptance covers Thunar, terminal, Firefox, a Qt window and XWayland:
normal buttons, hover, titlebar drag/double-click/menu, maximize/Fusion,
restore, minimize, close, task switching, KWin snap, shell restart, CSD
fallback, 1280x800 and scaled output. Capture screenshots and compare idle PSS
and CPU with the recorded v4 baseline. M3-M5 and default-switch gates remain
pending until their separate acceptance criteria pass.

## Upstream basis

- https://develop.kde.org/docs/plasma/aurorae/
- https://develop.kde.org/docs/plasma/widget/
- https://api.kde.org/legacy/plasma/plasma-workspace/html/classTaskManager_1_1TasksModel.html
- https://raw.githubusercontent.com/KDE/plasma-workspace/master/libtaskmanager/abstracttasksmodel.h
