document.addEventListener('DOMContentLoaded', function() {
  var form = document.getElementById('bookingForm');
  if (!form) return;

  form.addEventListener('submit', function(e) {
    var ar = document.documentElement.lang === 'ar';
    var lang = ar ? 'ar' : 'en';
    var errors = [];

    var carId = document.getElementById('car_id_input');
    if (!carId || !carId.value.trim()) {
      errors.push(ar ? 'يرجى اختيار سيارة.' : 'Please select a vehicle.');
    }

    var manager = document.querySelector('select[name="manager_name"]');
    if (!manager || !manager.value.trim()) {
      errors.push(ar ? 'يرجى اختيار المدير المعتمد.' : 'Please select an approving manager.');
    }

    var departure = document.getElementById('planned_departure');
    if (!departure || !departure.value.trim()) {
      errors.push(ar ? 'يرجى إدخال تاريخ المغادرة.' : 'Please enter departure date and time.');
    }

    if (lang === 'en') {
      var dest = document.querySelector('input[name="destination"]');
      var purpose = document.querySelector('textarea[name="purpose"]');
      if (!dest || !dest.value.trim()) errors.push('Please enter a destination.');
      if (!purpose || !purpose.value.trim()) errors.push('Please enter the purpose of the trip.');
    } else {
      var destAr = document.querySelector('input[name="destination_ar"]');
      var purposeAr = document.querySelector('textarea[name="purpose_ar"]');
      if (!destAr || !destAr.value.trim()) errors.push('يرجى إدخال الوجهة.');
      if (!purposeAr || !purposeAr.value.trim()) errors.push('يرجى إدخال الغرض من الرحلة.');
    }

    if (errors.length > 0) {
      e.preventDefault();
      e.stopImmediatePropagation();

      var existing = document.getElementById('js-validation-errors');
      if (existing) existing.remove();

      var box = document.createElement('div');
      box.id = 'js-validation-errors';
      box.className = 'flash flash-error';
      box.style.cssText = 'margin-bottom:1rem;padding:0.75rem 1rem;border-radius:6px;';
      box.innerHTML = errors.map(function(err) {
        return '<div>• ' + err + '</div>';
      }).join('');

      form.parentNode.insertBefore(box, form);
      box.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return false;
    }
  });
});
