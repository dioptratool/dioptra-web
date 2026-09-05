$(function() {
  $(':input[data-flatpickr]').each(function(i, input) {
    var $input = $(input);
    var options = $input.data('flatpickr');
    // Bounds are ISO dates, independent of the input's display format. Use local Date objects:
    // Flatpickr parses bounds before setting up month names, and Date.parse treats ISO as UTC.
    ['minDate', 'maxDate'].forEach(function(key) {
      var value = options[key];
      if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
        var parts = value.split('-').map(Number);
        options[key] = new Date(parts[0], parts[1] - 1, parts[2]);
      }
    });
    var flatpickr = $input.flatpickr(options);

    // Only close calendar on escape if cal is open, not entire panel
    $input.on('keyup', disableEscape);

    var flatpickrPopup = document.querySelector('.flatpickr-calendar');
    if (flatpickrPopup) {
      flatpickrPopup.addEventListener('keyup', disableEscape);
    }

    function disableEscape(e) {

      // Check for ESC key press
      if (e.keyCode === 27) {
        e.stopPropagation();  
        flatpickr.close();
      }
    }

    // Close flatpickr on focuousout if not element in calendar or input
    // Workaround to ckeditor clicks and focus not closing calendar
    $('.flatpickr-calendar, .flatpickr-input').focusout(function(e) {
      var newFocus = $(e.relatedTarget);

      if (!newFocus.closest('.flatpickr-calendar').length && !newFocus.hasClass('flatpickr-input')) {
        flatpickr.close();
      }
    }); 

    // ensure flatpickr is open if enter is pressed on input
    $input.on('keydown', function(e){
      console.log('input keydown');
      if (e.keyCode === 13) {
        flatpickr.open();    
      }
    });    
  });
});
