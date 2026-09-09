'use strict';
(() => {
  const run = document.getElementById('run-demo');
  const reset = document.getElementById('reset-demo');
  const status = document.getElementById('demo-status');
  const count = document.getElementById('active-count');
  const rows = [document.getElementById('request-one'), document.getElementById('request-two')];
  const states = [document.getElementById('state-one'), document.getElementById('state-two')];
  const progress = [document.getElementById('progress-one'), document.getElementById('progress-two')];
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let timers = [];
  function clear() { timers.forEach(window.clearTimeout); timers = []; }
  function setRow(i, kind, text, width) {
    rows[i].className = `queue-row ${kind}`;
    states[i].textContent = text;
    progress[i].style.transition = 'none';
    progress[i].style.width = width;
  }
  function later(fn, delay) { timers.push(window.setTimeout(fn, delay)); }
  function fill(i, duration) {
    if (motion.matches) return;
    later(() => { progress[i].style.transition = `width ${duration}ms linear`; progress[i].style.width = '100%'; }, 30);
  }
  reset.addEventListener('click', () => {
    clear();
    rows.forEach((_, i) => setRow(i, '', 'Ready', '0%'));
    count.textContent = '0';
    status.textContent = 'Demo reset. Start again to follow two requests.';
    run.disabled = false; run.textContent = 'Run queue demo →'; reset.disabled = true;
    run.focus();
  });
  run.addEventListener('click', () => {
    clear(); run.disabled = true; reset.disabled = false;
    setRow(0, 'active', 'Reading', '0%'); setRow(1, '', 'Ready', '0%');
    count.textContent = '1';
    status.textContent = 'Request A is reading. The single queue slot is occupied.';
    fill(0, 2900);
    later(() => {
      setRow(1, 'waiting', 'Queued', '0%');
      status.textContent = 'Request B has arrived. It waits while A holds the queue.';
    }, 650);
    later(() => {
      setRow(0, 'complete', 'Finished', '100%');
      setRow(1, 'active', 'Inspecting', '0%');
      status.textContent = 'A has finished. B can now inspect the second file.';
      fill(1, 1400);
    }, 3000);
    later(() => {
      setRow(1, 'complete', 'Finished', '100%'); count.textContent = '0';
      status.textContent = 'Both requests finished. Only one backing operation was active at a time.';
      run.disabled = false; run.textContent = 'Replay queue demo ↻';
    }, 4500);
  });
})();
