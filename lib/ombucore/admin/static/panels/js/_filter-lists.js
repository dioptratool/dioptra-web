$(function() {

  var $filterList = $('.filter-list');
  if ($filterList.length) {
    $filterList.each(function(i, filterListEl) {
      var $filterList = $(filterListEl);
      if ($filterList.find('.filter-list-form').length) {
        setupFilterListForm($filterList);
      }
    });
  }

  var $markTriggers = $('.mark-trigger');
  $markTriggers.on('click', function(e) {
      var $el = $(e.currentTarget);
      var wasMarked = $el.hasClass('marked');
      $markTriggers.removeClass('marked');
      $el.addClass('marked');

      if (wasMarked && $el.parents('.grid-media').length) {
          $el.find('.operations-links a:first-child').trigger('click');
      }
  });

  $markTriggers.find('.operations-links a[data-panels-trigger]').on('click', function(e) {
      e.stopPropagation();
      panelTriggerHandler(e);
  });

  $markTriggers.find('.operations-close').on('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      $markTriggers.removeClass('marked');
  });

  // Makes list items click on the name twice trigger the first operation. 
  $markTriggers.find('.operations-primary').on('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      $primaryLink = $(this).next('.operations-links').find('a:first-child');
      $primaryLink.trigger('click');
  });

  var $selectButton = $('.panels-select-btn');
  if ($selectButton.length) {
      $markTriggers.on('click', function(e) {
          var hasMarked = !!$markTriggers.filter('.marked').length;
          $selectButton.prop('disabled', !hasMarked);
      });

      $markTriggers.find('.operations-select').on('click', function(e) {
          e.preventDefault();
          e.stopPropagation();
          $selectButton.trigger('click');
      });

      $selectButton.on('click', function(e) {
          e.preventDefault();
          $marked = $markTriggers.filter('.marked');
          if (!$marked.length) {
              return;
          }
          var objInfo = $marked.data('obj-info');
          Panels.current.resolve({
              operation: 'selected',
              info: objInfo
          });

      });
  }

  // Custom localization dropdown filter
  $('.locale-dropdown--toggle').on('click', function(e){
    e.preventDefault();
    $(this).next('.locale-dropdown--options').toggleClass('open');
  });

  $('body').click(function(e) {
    if (!$(e.target).closest('.locale-dropdown').length){
      $('.locale-dropdown--options').removeClass('open');
    }
  });   

});
