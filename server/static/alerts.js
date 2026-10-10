// SPDX-License-Identifier: GPL-3.0-or-later
(() => {
  const panel = document.getElementById('teacherAlerts');
  const badge = document.getElementById("navAlertCount");
  if (!panel && !badge) return;
  let pending = false;
  const status = document.getElementById('alertPollingStatus');
  const refresh = async () => {
    if (pending || document.hidden || (panel && panel.contains(document.activeElement))) return;
    pending = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch('/teacher-alerts', {credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
      if (!response.ok || response.redirected) throw new Error('Prijava ali povezava');
      const html = await response.text();
      const parsed = new DOMParser().parseFromString(html, "text/html");
      if (panel) panel.innerHTML = html;
      const count = parsed.querySelector('[data-open-count]')?.dataset.openCount || '0';
      document.title = count === '0' ? 'SimulIDE učitelj' : `SimulIDE · ${count} novih opozoril`;
      if (badge) badge.textContent = count;
      if (status) status.textContent = 'Opozorila posodobljena ob ' + new Date().toLocaleTimeString('sl-SI') + '.';
    } catch (_) {
      if (status) status.textContent = 'Opozoril ni bilo mogoče osvežiti. Preveri povezavo ali prijavo; osveži stran.';
    } finally { clearTimeout(timeout); pending = false; }
  };
  refresh(); setInterval(refresh, 20000);
})();
