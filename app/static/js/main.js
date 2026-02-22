// Auto-default all datetime-local and date inputs to current time
document.addEventListener('DOMContentLoaded', function() {
  function getNow() {
    const now = new Date();
    now.setSeconds(0, 0);
    const pad = function(n) { return String(n).padStart(2, '0'); };
    return now.getFullYear() + '-' +
           pad(now.getMonth() + 1) + '-' +
           pad(now.getDate()) + 'T' +
           pad(now.getHours()) + ':' +
           pad(now.getMinutes());
  }

  function getToday() {
    const now = new Date();
    const pad = function(n) { return String(n).padStart(2, '0'); };
    return now.getFullYear() + '-' +
           pad(now.getMonth() + 1) + '-' +
           pad(now.getDate());
  }

  document.querySelectorAll('input[type="datetime-local"]').forEach(function(el) {
    if (!el.value) {
      el.value = getNow();
    }
  });

  document.querySelectorAll('input[type="date"]').forEach(function(el) {
    if (!el.value) {
      el.value = getToday();
    }
  });
});
