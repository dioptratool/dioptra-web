$(function() {
  // Open flatpickr on click of calendar icon
  $('.form__date-icon').on('click', function(e){
    $(this).closest('.form__date').find('.flatpickr-input').focus();
  });


  $('input[name="upload-type"]').on('click', function(e){
    const formType = $(this).val()
    $(this).closest('form').find(`.form-group:not([data-section])`).addClass('active')
    $(this).closest('form').find(`[data-section]`).removeClass('active')
    $(this).closest('form').find(`[data-section="${formType}"]`).addClass('active')
  });

  // Increment and decrement number input on click
  $('.form__number-toggle--decrease').on('click', function(e){
    e.preventDefault();
    var input = $(this).closest('.form__number').find('input[type="number"]').not(':disabled')
   if (input.length) {
      input[0].stepDown();
    }
  }); 
  $('.form__number-toggle--increase').on('click', function(e){
    e.preventDefault();
    var input = $(this).closest('.form__number').find('input[type="number"]').not(':disabled')
    if (input.length) {
      input[0].stepUp();
    }
  });

  // print selected file by file input
  // disable button if no file is present
  function checkFile($fileInput, fileName) {
    var $formFile = $fileInput.closest('.form__file');
    if (fileName) {
      $formFile.find('.form__file-names').html(''); // Clear the previous value.
      $formFile.find('.form__file-names').append('<div class="form__file-name">' + fileName + '</div>');
      $formFile.addClass('form__file--selected');
      $formFile.find('.form__file-button').text('Choose a different file');
    }
    if ($fileInput.closest('form').find('.form__file-button--upload').length) {
      var $formFileUploadButton = $fileInput.closest('form').find('.form__file-button--upload');
      if ($fileInput.val()) {
        $formFileUploadButton.removeAttr('disabled');
      }
      else {
        $formFileUploadButton.attr('disabled', 'true');
      }
    }   
  }

  $('.form__file input[type="file"]').each(function( index ) {
    var fileName = '';
    if (this.files[0]) {
      var fileName = this.files[0].name;
    }
    checkFile($(this), fileName);
  });

  $('.form__file input[type="file"]').change(function(e){
    var fileName = e.target.files[0].name;
    checkFile($(this), fileName);
  });

  $('[data-click-confirm]').on('click', function(e) {
    var message = $(e.currentTarget).data('click-confirm');
    if (!window.confirm(message)) {
      e.preventDefault();
    }
  });

  $('form.warn-unsaved-changes').areYouSure(
    {'message': 'There are unsaved changes on this step. Are you sure you want to leave? Click Leave to move away without saving. Click Cancel to stay on the step and save your work.'}
  );


});



