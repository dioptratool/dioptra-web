(function () {

  $(function () {


    var checkboxes = $('input[type="checkbox"][name$="_overridden"]');
    console.log(checkboxes);

    function handleFieldLabelOverrideCheckbox(evt) {
      var $element = $(this);
      console.log($element);
      var labelFieldName = $element.attr('name').replace('_overridden', '');
      var textInput = $('input[name="' + labelFieldName + '"]');
      var isOverridden = $element.is(":checked")
      if (isOverridden) {
        textInput.show()
      } else {
        textInput.hide()
      }
    }

    checkboxes.on('change', handleFieldLabelOverrideCheckbox)
      .trigger('change');
  });

})();