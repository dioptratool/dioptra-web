$(function() {
  const updateBulkAllocationTotal = () => {
    let total = 0.0;
    
    $('.bulk-subcomponent-allocate-form input[id^="id_subcomponent_allocation"]').each(function(i, el) {
      if ($(el).val()) {
        total += parseInt($(el).val())
      }
    });

    $('.bulk-subcomponent-allocate-form__total-value').text(total + '%')
    if (total > 100) {
      $('.bulk-subcomponent-allocate-form__exceed-warning').show()
    } else {
      $('.bulk-subcomponent-allocate-form__exceed-warning').hide()
    }
  }

  $('.bulk-subcomponent-allocate-form input[id^="id_subcomponent_allocation"]').each(function(i, el) {
    if (el === document.activeElement) {
      el.select()
    }
    el.addEventListener('focusin', (e) => {
      el.select()
    })
    el.addEventListener('input', (e) => {
      updateBulkAllocationTotal()
    })
  });
});
