$(function() {
  $('.bulk-allocate-form').each(function () {
    var form = this;
    var totalRule = form.getAttribute('data-total-rule') || 'max-100';
    var inputs = form.querySelectorAll('input.bulk-allocation-input');
    var totalEl = form.querySelector('.allocation-input-table__total-value');
    var warningEl = form.querySelector('.bulk-allocate-form__warning');

    function updateBulkAllocationTotal() {
      var total = 0;
      inputs.forEach(function (el) {
        var value = parseFloat(el.value);
        if (Number.isFinite(value)) {
          total += value;
        }
      });
      total = Number(total.toFixed(4));

      var invalid = totalRule === 'equal-100' ? total !== 100 : total > 100;
      if (totalEl) {
        totalEl.textContent = total + '%';
        totalEl.classList.toggle('error', invalid);
      }
      if (warningEl) {
        warningEl.style.display = invalid ? 'block' : 'none';
      }

      return !invalid;
    }

    inputs.forEach(function (el) {
      if (el === document.activeElement) {
        el.select();
      }
      el.addEventListener('focusin', function () {
        el.select();
      });
      el.addEventListener('input', function () {
        var cleaned = el.value.replace(/[^0-9.]/g, '');
        if (cleaned !== el.value) {
          el.value = cleaned;
        }
        if (updateBulkAllocationTotal()) {
          // fill blank rows with 0 on valid total
          var row = el.closest('tr');
          if (row) {
            row.querySelectorAll('input.bulk-allocation-input')?.forEach(function (input) {
              if (!input.value.length) {
                input.value = 0;
              }
            });
          }
        }
      });
      el.addEventListener('blur', (e) => {if (!el.value.length) el.value = 0})
    });

    updateBulkAllocationTotal();
  });
});
