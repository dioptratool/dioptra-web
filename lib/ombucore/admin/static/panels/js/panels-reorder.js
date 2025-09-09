;(function() {

function setupPanelsReorder($el) {
  var $select = $el.find('select');
  var $results = $el.find('.panels--reorder--results');

  Sortable.create($results[0], {
    handle: ".handle",
    onUpdate: updateResultOrder
  });

  function updateResultOrder(e) {
    $select.find('option').remove();
    $results.find('li').each(function(i, li) {
      var objInfo = $(li).data('obj-info');
      $select.append(renderOption(objInfo));
    });
    $select.trigger('change');
  }

  function renderOption(objInfo) {
    return '<option value="' + objInfo.id + '" selected="selected">' + objInfo.title + '</option>';
  }
}

$(function() {

  $('.panels--reorder').each(function(i, el) {
    setupPanelsReorder($(el));
  });

});

})();
