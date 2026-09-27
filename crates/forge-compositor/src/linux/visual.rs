//! Shared Pixman surface composition for DRM and the nested test backend.
use super::*;
use smithay::{
    backend::renderer::element::{
        Kind, solid::SolidColorRenderElement, surface::render_elements_from_surface_tree,
    },
    input::pointer::CursorImageSurfaceData,
    wayland::compositor::with_states,
};

smithay::render_elements! {
    pub(super) SoftwareElement<=PixmanRenderer>;
    Surface=WaylandSurfaceRenderElement<PixmanRenderer>,
    Cursor=SolidColorRenderElement,
}

impl App {
    pub(super) fn pointer_elements(
        &self,
        renderer: &mut PixmanRenderer,
        origin: Point<i32, Logical>,
        scale: f64,
    ) -> Vec<SoftwareElement> {
        let mut elements = Vec::new();
        let location = self.pointer.to_i32_round() - origin;
        match &self.cursor {
            CursorImageStatus::Surface(surface) if surface.is_alive() => {
                let hotspot = with_states(surface, |states| {
                    states
                        .data_map
                        .get::<CursorImageSurfaceData>()
                        .and_then(|data| data.lock().ok().map(|data| data.hotspot))
                        .unwrap_or_default()
                });
                elements.extend(render_elements_from_surface_tree(
                    renderer,
                    surface,
                    (location - hotspot).to_physical_precise_round(scale),
                    scale,
                    1.0,
                    Kind::Cursor,
                ));
            }
            CursorImageStatus::Hidden => {}
            _ => elements.push(
                SolidColorRenderElement::from_buffer(
                    &self.cursor_fallback,
                    location.to_physical_precise_round(scale),
                    scale,
                    1.0,
                    Kind::Cursor,
                )
                .into(),
            ),
        }
        if let Some(icon) = self.dnd_icon.as_ref().filter(|s| s.is_alive()) {
            elements.extend(render_elements_from_surface_tree(
                renderer,
                icon,
                location.to_physical_precise_round(scale),
                scale,
                1.0,
                Kind::Unspecified,
            ));
        }
        elements
    }
}
