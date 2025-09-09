$(function() {
  $(':input[data-flatpickr]').each(function(i, input) {
    var $input = $(input);
    var options = $input.data('flatpickr');
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
