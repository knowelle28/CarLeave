document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => { el.style.transition='opacity 0.4s'; el.style.opacity='0'; setTimeout(()=>el.remove(),400); }, 5000);
});
const departureInput = document.getElementById('departure_datetime');
const returnInput = document.getElementById('return_datetime');
if (departureInput && !departureInput.value) {
  const now = new Date(); now.setMinutes(0,0,0); now.setHours(now.getHours()+1);
  const iso = now.toISOString().slice(0,16);
  departureInput.value = iso; departureInput.min = iso;
}
if (departureInput && returnInput) {
  departureInput.addEventListener('change', () => {
    if (returnInput.value && returnInput.value <= departureInput.value) {
      const d = new Date(departureInput.value); d.setHours(d.getHours()+1);
      returnInput.value = d.toISOString().slice(0,16);
    }
    returnInput.min = departureInput.value;
  });
}
