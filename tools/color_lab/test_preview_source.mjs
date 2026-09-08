// Run with node tools/color_lab/test_preview_source.mjs.
// Pixel-preservation contract for the H5 preview, independent of device APIs.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('../../main/apps/app_server/index.html', import.meta.url), 'utf8');
for (const script of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) {
  new vm.Script(script[1]);
}
const start = html.indexOf('function renderPreviewInkEffect()');
const end = html.indexOf('function schedulePreviewInkRender(', start);
assert(start >= 0 && end > start);
const pixels = [255,255,255,255, 255,0,255,255, 0,255,255,255, 96,96,96,255];
for (const displayMode of ['dither', 'nearest']) {
  const source = { pixels };
  const ctx = {
    clearRect() {}, fillRect() {},
    drawImage(canvas) { this.pixels = [...canvas.pixels]; },
    getImageData() { throw new Error('Source preview must not requantize pixels'); },
    putImageData() { throw new Error('Source preview must not tint white'); },
  };
  const overlay = { getContext: () => ctx };
  let visible = false;
  let hasImages = true;
  const queue = [];
  const scope = vm.createContext({
    displayMode, previewInkRenderToken: 0,
    requestAnimationFrame: fn => queue.push(fn),
    getPreviewInkCanvas: () => overlay,
    hasCompositionImages: () => hasImages,
    exportToCanvas: () => source,
    getCanvasSize: () => [400, 600],
    setPreviewInkVisible: value => { visible = value; },
  });
  vm.runInContext(html.slice(start, end), scope);
  vm.runInContext('renderPreviewInkEffect()', scope);
  queue.shift()();
  assert.equal(visible, true);
  assert.deepEqual(ctx.pixels, pixels);
  assert.equal(ctx.fillStyle, '#ffffff');
  assert.deepEqual([overlay.width, overlay.height], [400,600]);
  hasImages = false;
  vm.runInContext('renderPreviewInkEffect()', scope);
  queue.shift()();
  assert.equal(visible, false);
  assert.deepEqual([overlay.width, overlay.height], [0,0]);
}
// Both upload routes must continue using the same unquantized composition.
for (const name of ['uploadOnly', 'uploadWithDisplay']) {
  const pos = html.indexOf(`async function ${name}(`);
  const next = html.indexOf('\nasync function ', pos + 1);
  const body = html.slice(pos, next < 0 ? html.length : next);
  assert(pos >= 0);
  assert.match(body, /exportToCanvas\(\)/);
  assert.doesNotMatch(body, /exportPreviewInkCanvas\(\)/);
}
console.log('H5 syntax/source-preview pixels/both modes/empty composition/upload-source: pass');
