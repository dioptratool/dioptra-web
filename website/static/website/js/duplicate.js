$(function() {

  $('input[name="change_analysis_date_range"]').on('change', function(e){
    toggleDateRangeInput()
  });

  function toggleDateRangeInput() {
    if ($('input[name="change_analysis_date_range"]:checked').val() === 'change') {
      $('input[name="start_date"]').closest('.form-group').show()
      $('input[name="end_date"]').closest('.form-group').show()
      $('p.change_analysis_date_range-help-text').show()
    } else {
      $('input[name="start_date"]').closest('.form-group').hide()
      $('input[name="end_date"]').closest('.form-group').hide()
      $('p.change_analysis_date_range-help-text').hide()
    }
  }

  toggleDateRangeInput()


});



