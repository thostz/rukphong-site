// Rukphong — ให้กราฟ Chart.js ใช้สีตามธีม (สว่าง/มืด) จาก theme.css
(function () {
  function applyChartTheme() {
    if (!window.Chart || !window.Chart.defaults) return;
    var css = getComputedStyle(document.documentElement);
    var v = function (n) { return css.getPropertyValue(n).trim(); };
    var d = window.Chart.defaults;
    d.color = v('--muted');
    d.borderColor = v('--border');
    d.font.family = "'Inter', 'Noto Sans Thai', system-ui, sans-serif";
    d.font.size = 11;
    if (d.elements && d.elements.arc) d.elements.arc.borderColor = v('--surface');
    if (d.elements && d.elements.bar) d.elements.bar.borderRadius = 6;
    if (d.plugins && d.plugins.tooltip) {
      d.plugins.tooltip.backgroundColor = v('--text');
      d.plugins.tooltip.titleColor = v('--surface');
      d.plugins.tooltip.bodyColor = v('--surface');
      d.plugins.tooltip.padding = 10;
      d.plugins.tooltip.cornerRadius = 8;
    }
    if (d.plugins && d.plugins.legend) {
      d.plugins.legend.labels.usePointStyle = true;
      d.plugins.legend.labels.pointStyle = 'circle';
    }
  }
  applyChartTheme();
  document.addEventListener('DOMContentLoaded', applyChartTheme);

  // เปลี่ยนธีมเครื่องระหว่างเปิดหน้าอยู่ → โหลดใหม่ให้กราฟเปลี่ยนสีตาม
  var mq = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
  if (mq && mq.addEventListener) mq.addEventListener('change', function () { location.reload(); });
})();
