# Native Chinese input in the isolated DRM desktop

2026-09-28, scoped M3.1 runtime observation. The user's daily VM was not
modified. This test used the marked disposable 2-vCPU/4-GiB VM and the M3
multi-output **debug candidate** SHA
`6d32efdd4837b5b99acb2f80aa24215eee0be3ed99d9a56b82845a41ea4c2cda`.
The candidate contains the `ea412a9` input implementation; ongoing quality
review and subsequent fixes must be rebuilt and retested before acceptance.

The test VM's Fcitx profile initially exposed only `keyboard-us`. In that test
account only, it was changed to the same `keyboard-us` plus `pinyin` profile used
by the native nested smoke fixture. The compositor's supervised Fcitx process
had PID 610, UID 1000, parent compositor PID 539. Sending SIGKILL to **that
exact child** produced new Fcitx PID 831 without restarting the compositor.
`fcitx5-remote -s pinyin` succeeded and `fcitx5-remote` reported active state 2.

With virtual head 1 temporarily disconnected to isolate the known dual-output
absolute-pointer defect, noVNC clicked the real Mousepad Dock entry. Mousepad
restored prior unsaved `forge` text. Physical keyboard events `n i h a o` showed
the actual Fcitx `你好` candidate pane immediately below Mousepad's caret:
[candidate window](drm-ime-candidate.jpg). Pressing Space committed `你好` to the
editable document; a second composition committed it again:
[committed text](drm-ime-mousepad.jpg). The caret had been placed before the
last `e`, so the observed text is `forg你好你好e`.

This proves a GTK application can receive native Chinese composition and a
visible candidate pane in the actual DRM session after Fcitx restart. It does
not prove persistence to disk, cross-application clipboard, Qt/Electron on DRM,
screen-edge candidate placement, dual-output pointer mapping, or full M3.1
quality acceptance. The input popup lifecycle review has an outstanding
xdg-popup case under repair.
