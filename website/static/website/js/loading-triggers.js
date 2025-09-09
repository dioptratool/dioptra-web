$(function() {

  $('form[data-show-loading-on-submit]').on('submit', function(e) {
    $('body').addClass('loading');
  });

});
