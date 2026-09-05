$(function() {
  $('.bulk-allocate-form').each(function () {
    var form = this;
    var totalRule = form.getAttribute('data-total-rule') || 'max-100';
    var inputs = form.querySelectorAll('input.bulk-allocation-input');
    var totalEl = form.querySelector('.allocation-input-table__total-value');
    var warningEl = form.querySelector('.bulk-allocate-form__warning');
    var suggestButton = form.querySelector('.program-cost-suggest-button');
    var suggestionEl = form.querySelector('.program-cost-suggestion');
    var suggestionError = form.querySelector('.program-cost-suggestion-error');
    var suggestionRequested = form.querySelector('[name="suggestion_requested"]');
    var initialSuggestion = form.getAttribute('data-initial-suggestion');

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
        el.classList.remove('bulk-allocation-input--suggested');
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
      el.addEventListener('blur', function () {
        if (!el.value.length) el.value = 0;
        updateBulkAllocationTotal();
      });
      if (initialSuggestion !== null && initialSuggestion !== '') {
        el.classList.add('bulk-allocation-input--suggested');
      }
    });

    if (suggestButton) {
      form.addEventListener('submit', function (event) {
        if (suggestButton.disabled) event.preventDefault();
      });
      suggestButton.addEventListener('click', async function () {
        var url = new URL(form.getAttribute('data-suggestion-url'), window.location.href);
        var configIds = Array.from(form.querySelectorAll('[name="config_ids"]')).map(el => el.value);
        url.searchParams.set('config_ids', configIds.join(','));
        url.searchParams.set('suggestion', '1');
        suggestButton.disabled = true;
        inputs.forEach(el => { el.disabled = true; });
        form.querySelectorAll('[type="submit"]').forEach(button => { button.disabled = true; });
        suggestionEl.setAttribute('aria-busy', 'true');
        suggestionError.hidden = true;
        try {
          var response = await fetch(url, {cache: 'no-store', credentials: 'same-origin'});
          if (!response.ok) throw new Error('Suggestion request failed');
          var data = await response.json();
          suggestionEl.innerHTML = data.html;
          suggestionEl.hidden = false;
          suggestionRequested.value = 'True';
          if (data.allocation !== null) {
            inputs.forEach(function (el) {
              el.value = data.allocation;
              el.classList.add('bulk-allocation-input--suggested');
              $(el).trigger('change');
              $(el).closest('.form-group').addClass('changed');
            });
            $(form).trigger('panel:inputchanged');
          }
          updateBulkAllocationTotal();
        } catch (error) {
          suggestionError.textContent = form.getAttribute('data-suggestion-error');
          suggestionError.hidden = false;
        } finally {
          suggestButton.disabled = false;
          inputs.forEach(el => { el.disabled = false; });
          suggestionEl.removeAttribute('aria-busy');
          $(form).trigger('panel:inputchanged');
        }
      });
    }

    updateBulkAllocationTotal();
  });
});
