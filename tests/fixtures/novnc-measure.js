// Test page served alongside the distribution's original noVNC modules.
// No export endpoint: results remain in this page's visible readonly textarea.
import RFB from './core/rfb.js';

const ui = Object.fromEntries(['connection', 'label', 'x', 'y', 'w', 'h',
  'armed', 'reset', 'status', 'readiness', 'screen', 'results'].map(id => [id, document.getElementById(id)]));
const observations = [];
let trial = null;
let connected = false;
let quiet = null;
const rfb = new RFB(ui.screen, `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/websockify`, {shared:true});
rfb.scaleViewport = true;
rfb.resizeSession = false;

function publish() {
  ui.results.value = JSON.stringify({schemaVersion:1,
    metric:'pointer-down-to-first-roi-pixel-change',
    limitations:['requestAnimationFrame sampling, not presentation timestamps',
      'ROI must be visually checked against intended response',
      'pixel readback adds browser overhead; unrelated ROI updates invalidate trial'],
    observations}, null, 2);
}
function finish(outcome, latency) {
  observations.push({case:trial.label, outcome, elapsedMs:latency,
    canvas:trial.canvas, roi:trial.roi, startUtc:trial.startUtc});
  trial = null;
  ui.status.textContent = `${observations.length} samples; ${outcome} ${latency.toFixed(1)} ms`;
  if (observations.length >= 100) ui.armed.checked = false;
  publish();
}
rfb.addEventListener('connect', () => { connected = true; ui.connection.textContent = 'Connected to VM'; });
rfb.addEventListener('disconnect', () => {
  connected = false; ui.armed.checked = false; ui.connection.textContent = 'Disconnected; reload to reconnect';
  if (trial) finish('disconnected', performance.now() - trial.start);
});

function region() {
  const canvas = ui.screen.querySelector('canvas');
  const roi = ['x','y','w','h'].map(key => Number(ui[key].value));
  const [x,y,w,h] = roi;
  if (!canvas || !roi.every(Number.isInteger) || x < 0 || y < 0 || w < 1 || h < 1 ||
      w*h > 256*256 || x+w > canvas.width || y+h > canvas.height) return null;
  return {canvas,roi,key:[canvas.width,canvas.height,...roi].join(','),
    pixels:canvas.getContext('2d').getImageData(x,y,w,h).data};
}
function differs(a,b) {
  if (a.length !== b.length) return true;
  for (let i=0;i<a.length;i+=16) {
    if (Math.abs(a[i]-b[i])+Math.abs(a[i+1]-b[i+1])+Math.abs(a[i+2]-b[i+2]) > 24) return true;
  }
  return false;
}
function settle() {
  const now = performance.now();
  const current = connected && ui.armed.checked && !trial ? region() : null;
  if (!current) {
    quiet = null; ui.readiness.textContent = trial ? 'Measuring' : 'Not armed';
  } else {
    if (!quiet || current.key !== quiet.key || differs(current.pixels,quiet.pixels)) {
      quiet = {...current,since:now};
    }
    ui.readiness.textContent = now-quiet.since >= 500 ? 'Ready: ROI stable 500 ms' : 'Waiting for stable ROI';
  }
  requestAnimationFrame(settle);
}
requestAnimationFrame(settle);

ui.screen.addEventListener('pointerdown', event => {
  const start = event.timeStamp;
  if (!connected || !ui.armed.checked || event.button !== 0 || trial || observations.length >= 100) return;
  const canvas = ui.screen.querySelector('canvas');
  if (!canvas || event.target !== canvas) return;
  const roi = ['x','y','w','h'].map(key => Number(ui[key].value));
  const [x,y,w,h] = roi;
  if (!roi.every(Number.isInteger) || x < 0 || y < 0 || w < 1 || h < 1 ||
      w*h > 256*256 || x+w > canvas.width || y+h > canvas.height) {
    ui.status.textContent = 'Invalid ROI (max 65536 pixels)'; return;
  }
  const context = canvas.getContext('2d');
  const before = context.getImageData(x,y,w,h).data;
  trial = {start, startUtc:new Date().toISOString(),
    label:ui.label.value.slice(0,80), canvas:[canvas.width,canvas.height], roi};
  const key = [canvas.width,canvas.height,...roi].join(',');
  if (!quiet || quiet.key !== key || performance.now()-quiet.since < 500 || differs(before,quiet.pixels)) {
    finish('unsettled',0); quiet = null; return;
  }
  quiet = null;
  ui.status.textContent = 'Waiting for visible ROI change';
  const activeTrial = trial;
  function observe() {
    if (trial !== activeTrial) return;
    const elapsed = performance.now() - trial.start;
    if (canvas.width !== trial.canvas[0] || canvas.height !== trial.canvas[1]) {
      finish('canvas-resized', elapsed); return;
    }
    const after = context.getImageData(x,y,w,h).data;
    let changed = 0;
    // Sample every fourth pixel, threshold 32 to ignore individual pixel noise.
    for (let i=0;i<after.length;i+=16) {
      if (Math.abs(after[i]-before[i])+Math.abs(after[i+1]-before[i+1])+Math.abs(after[i+2]-before[i+2]) > 24) changed++;
    }
    if (changed >= Math.min(32, Math.ceil(w*h/4))) finish('changed', elapsed);
    else if (elapsed >= 3000) finish('timeout', elapsed);
    else requestAnimationFrame(observe);
  }
  requestAnimationFrame(observe);
}, true);
ui.reset.addEventListener('click', () => {
  ui.armed.checked = false; trial = null; observations.length = 0;
  ui.status.textContent = 'Not recording'; publish();
});
publish();
