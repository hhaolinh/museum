(() => {
  const atlas = document.querySelector('[data-atlas]');
  if (!atlas) return;
  const viewport = atlas.querySelector('.atlas-viewport');
  const stage = atlas.querySelector('.atlas-stage');
  const controls = atlas.querySelector('.atlas-controls');
  controls.hidden = false;
  const buttons = [...atlas.querySelectorAll('[data-location]')];
  const panels = [...atlas.querySelectorAll('[data-panel]')];
  let zoom = 1, x = 0, y = 0, drag = null, moved = false;
  function draw() {
    const width = viewport.clientWidth, height = viewport.clientHeight;
    x = Math.min(0, Math.max(width * (1 - zoom), x));
    y = Math.min(0, Math.max(height * (1 - zoom), y));
    stage.style.transform = `translate(${x}px,${y}px) scale(${zoom})`;
    stage.style.setProperty('--pin-scale', 1 / zoom);
    viewport.style.touchAction = zoom > 1 ? 'none' : 'pan-y';
    controls.querySelector('[data-zoom="in"]').disabled = zoom >= 8;
    controls.querySelector('[data-zoom="out"]').disabled = zoom <= 1;
  }
  function select(id, focus = false) {
    panels.forEach(panel => { panel.hidden = panel.dataset.panel !== id; });
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.location === id)));
    const active = panels.find(panel => panel.dataset.panel === id);
    if (focus && zoom > 1) {
      const pin = buttons.find(button => button.classList.contains('atlas-pin') && button.dataset.location === id);
      x = viewport.clientWidth / 2 - parseFloat(pin.style.left) / 100 * viewport.clientWidth * zoom;
      y = viewport.clientHeight / 2 - parseFloat(pin.style.top) / 100 * viewport.clientHeight * zoom;
      draw();
    }
    if (focus && active) active.querySelector('h2').focus({preventScroll: true});
    if (focus && matchMedia('(max-width: 800px)').matches) active?.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  }
  buttons.forEach(button => button.addEventListener('click', () => {
    if (moved) return;
    select(button.dataset.location, true);
  }));
  if (panels.length) select(panels[0].dataset.panel);
  controls.addEventListener('click', event => {
    const button = event.target.closest('[data-zoom]');
    if (!button) return;
    const next = button.dataset.zoom === 'reset' ? 1 : Math.max(1, Math.min(8, zoom * (button.dataset.zoom === 'in' ? 1.6 : 1 / 1.6)));
    const activePin = buttons.find(button => button.classList.contains('atlas-pin') && button.getAttribute('aria-pressed') === 'true');
    if (activePin && button.dataset.zoom === 'in') {
      x = viewport.clientWidth / 2 - parseFloat(activePin.style.left) / 100 * viewport.clientWidth * next;
      y = viewport.clientHeight / 2 - parseFloat(activePin.style.top) / 100 * viewport.clientHeight * next;
    } else {
      x = viewport.clientWidth / 2 - (viewport.clientWidth / 2 - x) * next / zoom;
      y = viewport.clientHeight / 2 - (viewport.clientHeight / 2 - y) * next / zoom;
    }
    zoom = next;
    draw();
  });
  viewport.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    moved = false;
    drag = {id: event.pointerId, clientX: event.clientX, clientY: event.clientY, x, y};
    // Capture only after movement, so a simple tap still reaches the pin button.
  });
  viewport.addEventListener('pointermove', event => {
    if (!drag || drag.id !== event.pointerId || zoom === 1) return;
    const dx = event.clientX - drag.clientX, dy = event.clientY - drag.clientY;
    if (Math.abs(dx) + Math.abs(dy) > 5) {
      moved = true;
      viewport.setPointerCapture(event.pointerId);
      x = drag.x + dx; y = drag.y + dy;
      draw();
    }
  });
  function end() { drag = null; setTimeout(() => { moved = false; }, 0); }
  viewport.addEventListener('pointerup', end);
  viewport.addEventListener('pointercancel', end);
  window.addEventListener('resize', draw);
  draw();
})();
