# Restore the original R-OS native controls

The user explicitly selected restoration of the original R-OS layout, after
rejecting macOS traffic controls. Root verified the web baseline `80a7a2d`;
native `0e2b4fe~1` already uses right `IAX` (minimize/maximize/close), 48x32
Aurorae buttons and title-first 40px Fusion buttons inside its left applet.
Restore the web's whole-panel placement with title-only on the left and a
control-only applet after clock/system tray on the far right. Keep graphite surfaces,
32px title height, 12px window corners, real KWin actions and i18n.

1. Replace old traffic assertions with right-layout/visible-glyph assertions.
   Add producer rejection of old layout and activation migration/user-choice
   preservation/idempotence tests. Demonstrate RED before behavior changes.
2. Restore Aurorae and Fusion glyph controls, keep capability/CSD checks. Style
   GTK3/4 title buttons; initialize missing GtkSettings only in the explicit
   ordinary-user native style action. Only migrate the exact prior Forge pair.
3. Update the closed activation-script hash, retain source/receipt/mode bounds,
   package a fresh reviewable candidate and reject modified content. Root owns
   the ForgeOS consumer hash update and Web controls. No new dependencies.
   Add the closed `contents/config/main.xml` role asset and MIT inventory entry.
   Execute fresh layout and fixed migration scripts against the public Plasma
   scripting boundary: only the exact old seven-item 32px non-floating/non-hiding
   top panel may split; custom layout/roles and the Dock remain intact. Zero
   north-panel side margins without changing south-panel icon geometry.
4. Root coordinates matching guest GUI acceptance and final image staging.
   Check ordinary/Fusion controls, hover, focus, close/minimize/restore, user
   custom layouts, CSD fallback, 100/150/200% scale and recovery. Unit/source
   qualification is not new runtime evidence. Do not launch VMs or switch the
   daily session here, and commit only after Root completes integration.

GTK CSS cannot move controls by itself. Applications that override
GtkSettings/decoration layout, Firefox/Electron and libadwaita retain their own
chrome; report that scope rather than claiming a forced universal layout.

Verification: original controls RED preceded restoration; the far-right follow-up
produced five expected failures before implementation (missing final controls,
missing migration/role bindings, absent closed config, six-pixel top side inset).
The resulting producer suite has 90 tests, one platform skip, passing. Node runs
the actual layout/migration sources with documented API objects; it does not
render QML or establish real screen-edge hit geometry. Fresh guest screenshots
and live actions remain a separate integration gate owned by Root.
