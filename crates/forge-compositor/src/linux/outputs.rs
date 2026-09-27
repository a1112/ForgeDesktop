//! Logical output membership and recovery shared by real backend layouts.
use super::*;

pub(super) fn geometry(output: &Output) -> Rectangle<i32, Logical> {
    let mode = output.current_mode().unwrap();
    Rectangle::new(
        output.current_location(),
        mode.size
            .to_f64()
            .to_logical(output.current_scale().fractional_scale())
            .to_i32_round(),
    )
}

impl App {
    pub(super) fn window_output(&self, id: WindowId) -> &Output {
        let g = self.geometry(id);
        let center = Point::from((g.x + g.width as i32 / 2, g.y + g.height as i32 / 2));
        self.outputs
            .iter()
            .find(|o| geometry(o).contains(center))
            .unwrap_or(&self.output)
    }
    pub(super) fn update_output_layout(&mut self, outputs: Vec<Output>) {
        if let Some(primary) = outputs.first() {
            self.output = primary.clone();
            let size = geometry(primary).size;
            self.size = (size.w, size.h);
        }
        self.outputs = outputs;
        let Some(primary) = self.outputs.first().map(geometry) else {
            self.dirty = true;
            return;
        };
        let ids: Vec<_> = self
            .windows
            .iter()
            .filter(|m| m.role.is_none())
            .map(|m| m.id)
            .collect();
        for id in ids {
            let g = self.geometry(id);
            let rectangle =
                Rectangle::new((g.x, g.y).into(), (g.width as i32, g.height as i32).into());
            if !self.outputs.iter().any(|o| geometry(o).overlaps(rectangle)) {
                let _ = self.desktop.set_fullscreen(id, None);
                let _ = self.desktop.set_maximized(id, None);
                let _ = self.desktop.set_geometry(
                    id,
                    Geometry {
                        x: primary.loc.x + 40,
                        y: primary.loc.y + 50,
                        width: g.width.min((primary.size.w - 80).max(64) as u32),
                        height: g.height.min((primary.size.h - 100).max(32) as u32),
                    },
                );
                self.configure(id);
            }
        }
        let roles: Vec<_> = self
            .windows
            .iter()
            .filter(|m| m.role.is_some())
            .filter_map(|m| m.window.toplevel().cloned())
            .collect();
        for role in roles {
            self.update_role(&role);
        }
        self.pointer = self.clamp_pointer(self.pointer);
        self.sync_output_membership();
        self.reconcile_pointer(0);
        self.dirty = true;
    }
    pub(super) fn clamp_pointer(&self, point: Point<f64, Logical>) -> Point<f64, Logical> {
        self.outputs
            .iter()
            .map(|o| {
                let r = geometry(o);
                Point::from((
                    point
                        .x
                        .clamp(f64::from(r.loc.x), f64::from(r.loc.x + r.size.w - 1)),
                    point
                        .y
                        .clamp(f64::from(r.loc.y), f64::from(r.loc.y + r.size.h - 1)),
                ))
            })
            .min_by(|a, b| {
                let da = (a.x - point.x).powi(2) + (a.y - point.y).powi(2);
                let db = (b.x - point.x).powi(2) + (b.y - point.y).powi(2);
                da.total_cmp(&db)
            })
            .unwrap_or(point)
    }
    pub(super) fn sync_output_membership(&self) {
        for mapped in &self.windows {
            let g = self.geometry(mapped.id);
            let r = Rectangle::new((g.x, g.y).into(), (g.width as i32, g.height as i32).into());
            let root = mapped.window.toplevel().unwrap().wl_surface();
            for output in &self.outputs {
                if mapped.has_buffer && geometry(output).overlaps(r) {
                    output.enter(root);
                } else {
                    output.leave(root);
                }
            }
        }
    }
}
