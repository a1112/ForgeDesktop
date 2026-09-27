//! Inject input only into the explicitly selected isolated Xvfb test display.
#![forbid(unsafe_code)]
#[cfg(target_os = "linux")]
fn main() -> Result<(), Box<dyn std::error::Error>> {
    use smithay::reexports::x11rb::{
        CURRENT_TIME, NONE, connection::Connection, protocol::xproto::*,
    };
    use std::{thread::sleep, time::Duration};
    if std::env::args().nth(1).as_deref() != Some("--isolated-xvfb")
        || std::env::var("DISPLAY").as_deref() != Ok(":92")
    {
        return Err("this test requires --isolated-xvfb and DISPLAY=:92".into());
    }
    let (conn, screen) = smithay::reexports::x11rb::connect(None)?;
    let root = conn.setup().roots[screen].root;
    let window = conn
        .query_tree(root)?
        .reply()?
        .children
        .into_iter()
        .find(|w| {
            conn.get_property(false, *w, AtomEnum::WM_NAME, AtomEnum::STRING, 0, 200)
                .ok()
                .and_then(|c| c.reply().ok())
                .is_some_and(|r| r.value.starts_with(b"ForgeDesktop - Pixman"))
        })
        .ok_or("test compositor window missing")?;
    conn.set_input_focus(InputFocus::PARENT, window, CURRENT_TIME)?;
    // X11/XKB evdev codes for f,o,r,g,e. No production input-injection protocol.
    let type_word = || -> Result<(), Box<dyn std::error::Error>> {
        for detail in [41, 32, 27, 42, 26] {
            let event = KeyPressEvent {
                response_type: KEY_PRESS_EVENT,
                detail,
                sequence: 0,
                time: 100,
                root,
                event: window,
                child: NONE,
                root_x: 300,
                root_y: 170,
                event_x: 300,
                event_y: 170,
                state: KeyButMask::default(),
                same_screen: true,
            };
            conn.send_event(false, window, EventMask::KEY_PRESS, event)?;
            let mut release = event;
            release.response_type = KEY_RELEASE_EVENT;
            conn.send_event(false, window, EventMask::KEY_RELEASE, release)?;
            conn.flush()?;
            sleep(Duration::from_millis(30));
        }
        Ok(())
    };
    let mode = std::env::args().nth(2);
    if mode.as_deref() == Some("pixel") {
        let a: Vec<_> = std::env::args().skip(3).collect();
        if a.len() != 5 {
            return Err("pixel requires x y r g b".into());
        }
        let x: i16 = a[0].parse()?;
        let y: i16 = a[1].parse()?;
        let expected: [u8; 3] = [a[2].parse()?, a[3].parse()?, a[4].parse()?];
        let bytes = conn
            .get_image(ImageFormat::Z_PIXMAP, window, x, y, 1, 1, u32::MAX)?
            .reply()?
            .data;
        let actual = [bytes[2], bytes[1], bytes[0]];
        if actual != expected {
            return Err(format!("pixel ({x},{y}) expected {expected:?}, got {actual:?}").into());
        }
        println!("pixel ({x},{y}) = {actual:?}");
        return Ok(());
    }
    if mode.as_deref() == Some("key") {
        let detail: u8 = std::env::args().nth(3).ok_or("keycode")?.parse()?;
        let mut event = KeyPressEvent {
            response_type: KEY_PRESS_EVENT,
            detail,
            sequence: 0,
            time: 300,
            root,
            event: window,
            child: NONE,
            root_x: 0,
            root_y: 0,
            event_x: 0,
            event_y: 0,
            state: KeyButMask::default(),
            same_screen: true,
        };
        conn.send_event(false, window, EventMask::KEY_PRESS, event)?;
        conn.flush()?;
        sleep(Duration::from_millis(60));
        event.response_type = KEY_RELEASE_EVENT;
        conn.send_event(false, window, EventMask::KEY_RELEASE, event)?;
        conn.flush()?;
        conn.get_input_focus()?.reply()?;
        sleep(Duration::from_millis(100));
        return Ok(());
    }
    if mode.as_deref() == Some("click") {
        let x: i16 = std::env::args().nth(3).ok_or("x")?.parse()?;
        let y: i16 = std::env::args().nth(4).ok_or("y")?.parse()?;
        let detail: u8 = std::env::args().nth(5).unwrap_or("1".into()).parse()?;
        let motion = MotionNotifyEvent {
            response_type: MOTION_NOTIFY_EVENT,
            detail: Motion::NORMAL,
            sequence: 0,
            time: 200,
            root,
            event: window,
            child: NONE,
            root_x: x,
            root_y: y,
            event_x: x,
            event_y: y,
            state: KeyButMask::default(),
            same_screen: true,
        };
        conn.send_event(false, window, EventMask::POINTER_MOTION, motion)?;
        conn.flush()?;
        sleep(Duration::from_millis(50));
        let mut event = ButtonPressEvent {
            response_type: BUTTON_PRESS_EVENT,
            detail,
            sequence: 0,
            time: 210,
            root,
            event: window,
            child: NONE,
            root_x: x,
            root_y: y,
            event_x: x,
            event_y: y,
            state: KeyButMask::default(),
            same_screen: true,
        };
        conn.send_event(false, window, EventMask::BUTTON_PRESS, event)?;
        conn.flush()?;
        sleep(Duration::from_millis(80));
        event.response_type = BUTTON_RELEASE_EVENT;
        conn.send_event(false, window, EventMask::BUTTON_RELEASE, event)?;
        conn.flush()?;
        conn.get_input_focus()?.reply()?;
        sleep(Duration::from_millis(100));
        return Ok(());
    }
    if mode.as_deref() == Some("focus-cycle") {
        let press = KeyPressEvent {
            response_type: KEY_PRESS_EVENT,
            detail: 50,
            sequence: 0,
            time: 100,
            root,
            event: window,
            child: NONE,
            root_x: 300,
            root_y: 200,
            event_x: 300,
            event_y: 200,
            state: KeyButMask::default(),
            same_screen: true,
        };
        conn.send_event(false, window, EventMask::KEY_PRESS, press)?;
        conn.flush()?;
        sleep(Duration::from_millis(100));
        conn.set_input_focus(InputFocus::POINTER_ROOT, root, CURRENT_TIME)?;
        conn.flush()?;
        sleep(Duration::from_millis(100));
        // Release happened elsewhere; query_keymap is empty upon return.
        conn.set_input_focus(InputFocus::PARENT, window, CURRENT_TIME)?;
        conn.flush()?;
        sleep(Duration::from_millis(100));
        type_word()?;
        return Ok(());
    }
    if !matches!(mode.as_deref(), Some("pointer" | "click-wheel" | "drag")) {
        type_word()?;
    }
    if matches!(
        mode.as_deref(),
        Some("qt" | "focus" | "pointer" | "click-wheel" | "drag")
    ) {
        let motion = |x, y| -> Result<(), Box<dyn std::error::Error>> {
            let event = MotionNotifyEvent {
                response_type: MOTION_NOTIFY_EVENT,
                detail: Motion::NORMAL,
                sequence: 0,
                time: 200,
                root,
                event: window,
                child: NONE,
                root_x: x,
                root_y: y,
                event_x: x,
                event_y: y,
                state: KeyButMask::default(),
                same_screen: true,
            };
            conn.send_event(false, window, EventMask::POINTER_MOTION, event)?;
            conn.flush()?;
            sleep(Duration::from_millis(100));
            Ok(())
        };
        let button = |x, y, pressed, detail| -> Result<(), Box<dyn std::error::Error>> {
            let event = ButtonPressEvent {
                response_type: if pressed {
                    BUTTON_PRESS_EVENT
                } else {
                    BUTTON_RELEASE_EVENT
                },
                detail,
                sequence: 0,
                time: 210,
                root,
                event: window,
                child: NONE,
                root_x: x,
                root_y: y,
                event_x: x,
                event_y: y,
                state: KeyButMask::default(),
                same_screen: true,
            };
            conn.send_event(
                false,
                window,
                if pressed {
                    EventMask::BUTTON_PRESS
                } else {
                    EventMask::BUTTON_RELEASE
                },
                event,
            )?;
            conn.flush()?;
            sleep(Duration::from_millis(100));
            Ok(())
        };
        if mode.as_deref() == Some("pointer") {
            let x = std::env::args().nth(3).unwrap_or("300".into()).parse()?;
            let y = std::env::args().nth(4).unwrap_or("200".into()).parse()?;
            motion(x, y)?;
            return Ok(());
        }
        if mode.as_deref() == Some("drag") {
            let a: Vec<i16> = std::env::args()
                .skip(3)
                .map(|v| v.parse())
                .collect::<Result<_, _>>()?;
            if a.len() != 4 {
                return Err("drag needs x1 y1 x2 y2".into());
            }
            motion(a[0], a[1])?;
            button(a[0], a[1], true, 1)?;
            // Multiple steps exercise the source threshold and target enter/negotiation.
            for n in 1..=10 {
                motion(a[0] + (a[2] - a[0]) * n / 10, a[1] + (a[3] - a[1]) * n / 10)?;
            }
            motion(a[2], a[3] + 1)?;
            sleep(Duration::from_millis(300));
            button(a[2], a[3], false, 1)?;
            return Ok(());
        }
        if mode.as_deref() == Some("click-wheel") {
            for detail in [1, 4] {
                button(300, 200, true, detail)?;
                button(300, 200, false, detail)?;
            }
            return Ok(());
        }
        if mode.as_deref() == Some("focus") {
            motion(820, 568)?;
            button(820, 568, true, 1)?;
            button(820, 568, false, 1)?;
            type_word()?;
            println!("nested two-client click focus input delivered");
            return Ok(());
        }
        motion(300, 75)?;
        button(300, 75, true, 1)?;
        motion(500, 175)?;
        button(500, 175, false, 1)?;
        let old = conn
            .get_image(ImageFormat::Z_PIXMAP, window, 60, 100, 1, 1, u32::MAX)?
            .reply()?
            .data;
        let moved = conn
            .get_image(ImageFormat::Z_PIXMAP, window, 260, 180, 1, 1, u32::MAX)?
            .reply()?
            .data;
        if old[0] > 40 || moved[0] < 200 {
            return Err("Qt titlebar move did not change rendered position".into());
        }
        motion(888, 400)?;
        button(888, 400, true, 1)?;
        motion(988, 400)?;
        button(988, 400, false, 1)?;
        motion(500, 250)?;
        for detail in [4, 7] {
            button(500, 250, true, detail)?;
            button(500, 250, false, detail)?;
        }
        println!("nested Qt move, resize and two-axis wheel input delivered");
    }
    Ok(())
}
#[cfg(not(target_os = "linux"))]
fn main() {
    panic!("isolated Xvfb integration test requires Linux");
}
