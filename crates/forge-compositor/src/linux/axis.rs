use smithay::{
    backend::input::{Axis, AxisRelativeDirection, AxisSource},
    input::pointer::AxisFrame,
};

#[derive(Clone, Copy)]
pub(super) struct AxisInput {
    pub pixels: Option<f64>,
    pub v120: Option<f64>,
    pub direction: AxisRelativeDirection,
}
impl Default for AxisInput {
    fn default() -> Self {
        Self {
            pixels: None,
            v120: None,
            direction: AxisRelativeDirection::Identical,
        }
    }
}

/// Horizontal then vertical, preserving omitted axes versus explicit stops.
pub(super) fn frame(time: u32, source: AxisSource, input: [AxisInput; 2]) -> AxisFrame {
    let mut frame = AxisFrame::new(time).source(source);
    for (axis, input) in [Axis::Horizontal, Axis::Vertical].into_iter().zip(input) {
        let pixels = input
            .pixels
            .or_else(|| input.v120.map(|value| value * 15.0 / 120.0));
        frame = frame.relative_direction(axis, input.direction);
        if let Some(value) = pixels {
            frame = frame.value(axis, value);
        }
        if let Some(value) = input.v120 {
            frame = frame.v120(axis, value.round() as i32);
        }
        if source == AxisSource::Finger && input.pixels == Some(0.0) {
            frame = frame.stop(axis);
        }
    }
    frame
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn two_axis_high_resolution_wheel_preserves_source_units_and_direction() {
        let result = frame(
            42,
            AxisSource::Wheel,
            [
                AxisInput {
                    pixels: Some(-3.75),
                    v120: Some(-30.0),
                    direction: AxisRelativeDirection::Inverted,
                },
                AxisInput {
                    pixels: None,
                    v120: Some(60.0),
                    ..Default::default()
                },
            ],
        );
        assert_eq!(result.time, 42);
        assert_eq!(result.source, Some(AxisSource::Wheel));
        assert_eq!(result.axis, (-3.75, 7.5));
        assert_eq!(result.v120, Some((-30, 60)));
        assert_eq!(
            result.relative_direction,
            (
                AxisRelativeDirection::Inverted,
                AxisRelativeDirection::Identical
            )
        );
        assert_eq!(result.stop, (false, false));
    }
    #[test]
    fn finger_zero_stops_only_the_reported_axis() {
        let result = frame(
            7,
            AxisSource::Finger,
            [
                AxisInput::default(),
                AxisInput {
                    pixels: Some(0.0),
                    ..Default::default()
                },
            ],
        );
        assert_eq!(result.source, Some(AxisSource::Finger));
        assert_eq!(result.stop, (false, true));
        assert_eq!(result.v120, None);
        let diagonal = frame(
            8,
            AxisSource::Finger,
            [
                AxisInput {
                    pixels: Some(1.25),
                    ..Default::default()
                },
                AxisInput {
                    pixels: Some(-2.5),
                    ..Default::default()
                },
            ],
        );
        assert_eq!(diagonal.axis, (1.25, -2.5));
        assert_eq!(diagonal.stop, (false, false));
    }
    #[test]
    fn continuous_zero_does_not_invent_finger_stop_or_wheel_steps() {
        let result = frame(
            3,
            AxisSource::Continuous,
            [
                AxisInput {
                    pixels: Some(0.0),
                    ..Default::default()
                },
                AxisInput {
                    pixels: Some(0.125),
                    ..Default::default()
                },
            ],
        );
        assert_eq!(result.source, Some(AxisSource::Continuous));
        assert_eq!(result.axis, (0.0, 0.125));
        assert_eq!(result.stop, (false, false));
        assert_eq!(result.v120, None);
    }
}
