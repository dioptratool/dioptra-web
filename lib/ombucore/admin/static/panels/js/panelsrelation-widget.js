;(function() {

function setupPanelsRelationWidgetSingle($el) {
  var addOnly = $el.hasClass('add-only');
  var $input = $el.find('input');
  var $results = $el.find('.panels-relation-widget--results');
  var $controlLinks = $el.find('.panels-relation-widget--control a:not(.dropdown-toggle)');

  // Upcast existing values.
  $results.find('li').each(function(i, li) {
    var objInfo = $(li).data('obj-info');
    updateResult(objInfo);
  });

  $controlLinks.on('click', controlLinkClick)
  $results.on('click', '.panels-relation-widget--result a.operation-preview', eventNotMetaKey(previewClick));
  $results.on('click', '.panels-relation-widget--result a.operation-edit', eventNotMetaKey(editClick));
  $results.on('click', '.panels-relation-widget--result a.operation-remove', eventNotMetaKey(removeClick));

  function updateResult(objInfo) {
    $input.val(objInfo.id);
    $input.trigger('change');
    var $li = renderResult(objInfo, addOnly);
    $results.empty();
    $results.append($li);
  }

  function clearResult() {
    $input.val('');
    $input.trigger('change');
    $results.empty();
  }


  function handleResponse(response) {
      switch (response.operation) {
          case 'selected':
          case 'saved':
            updateResult(response.info);
            break;
          case 'deleted':
            clearResult();
            break;
      }
  }

  function controlLinkClick(e) {
    e.preventDefault();
    var $link = $(e.target);
    Panels.open($link.attr('href')).then(
      handleResponse, // Resolve.
      noop, // Reject.
      handleResponse // Progress.
    );
  }

  function editClick(e) {
    e.preventDefault();
    var objInfo = $(e.target).parents('.panels-relation-widget--result').data('obj-info');
    if (objInfo) {
      Panels.open(objInfo.change_url).then(
        handleResponse, // Resolve.
        noop, // Reject.
        handleResponse // Progress.
      );
    }
  }

  function previewClick(e) {
    e.preventDefault();
    var objInfo = $(e.target).parents('.panels-relation-widget--result').data('obj-info');
    if (objInfo && objInfo.preview_url) {
      Panels.open(objInfo.preview_url);
    }
  }

  function removeClick(e) {
    e.preventDefault();
    clearResult();
  }

  var exports = {
    updateResult: updateResult,
    clearResult: clearResult
  };
  $input.data('panels-relation-widget', exports);
}


function setupPanelsRelationWidgetMultiple($el) {
  var addOnly = $el.hasClass('add-only');
  var $select = $el.find('select');
  var $results = $el.find('.panels-relation-widget--results');
  var $controlLinks = $el.find('.panels-relation-widget--control a:not(.dropdown-toggle)');

  // Upcast existing values.
  $results.find('li').each(function(i, li) {
    var objInfo = $(li).data('obj-info');
    var $li = renderResult(objInfo, addOnly);
    $(li).replaceWith($li);
  });

  Sortable.create($results[0], {
    handle: ".handle",
    onUpdate: updateResultOrder
  });

  $controlLinks.on('click', controlLinkClick);
  $results.on('click', '.panels-relation-widget--result a.operation-preview', eventNotMetaKey(previewClick));
  $results.on('click', '.panels-relation-widget--result a.operation-edit', eventNotMetaKey(editClick));
  $results.on('click', '.panels-relation-widget--result a.operation-remove', eventNotMetaKey(removeClick));

  function updateResultOrder(e) {
    $select.find('option').remove();
    $results.find('li.panels-relation-widget--result').each(function(i, li) {
      var objInfo = $(li).data('obj-info');
      $select.append(renderOption(objInfo));
    });
    $select.trigger('change');
  }

  function addResult(objInfo) {
    var vals = $select.val() ? $select.val().map(toInt) : [];
    if (vals.indexOf(objInfo.id) >= 0) {
      // Already added.
      return;
    }
    $results.append(renderResult(objInfo, addOnly));
    $select.append(renderOption(objInfo));
    $select.trigger('change');
  }

  function updateResult(objInfo) {
    var $option = $select.find('option[value="' + objInfo.id + '"]');
    if(!$option.length) {
        return addResult(objInfo);
    }
    var $li = $results.find('li[data-id="' + objInfo.id + '"]');
    $option.replaceWith(renderOption(objInfo));
    $li.replaceWith(renderResult(objInfo, addOnly));
  }


  function removeResult(objInfo) {
    $results.find('li[data-id="' + objInfo.id + '"]').remove();
    $select.find('option[value="' + objInfo.id + '"]').remove();
    $select.trigger('change');
  }

  function controlLinkClick(e) {
    e.preventDefault();
    var $link = $(e.target);
    Panels.open($link.attr('href')).then(
        handleResponse, // Resolve.
        noop, // Reject.
        handleResponse // Progress.
    );
  }

  function editClick(e) {
    e.preventDefault();
    var objInfo = $(e.target).parents('.panels-relation-widget--result').data('obj-info');
    if (objInfo) {
      Panels.open(objInfo.change_url).then(
        handleResponse, // Resolve.
        noop, // Reject.
        handleResponse // Progress.
      );
    }
  }

  function previewClick(e) {
    e.preventDefault();
    var objInfo = $(e.target).parents('.panels-relation-widget--result').data('obj-info');
    if (objInfo && objInfo.preview_url) {
      Panels.open(objInfo.preview_url);
    }
  }

  function removeClick(e) {
    e.preventDefault();
    var objInfo = $(e.target).parents('.panels-relation-widget--result').data('obj-info');
    removeResult(objInfo);
  }

  function renderOption(objInfo) {
    return '<option value="' + objInfo.id + '" selected="selected">' + objInfo.title + '</option>';
  }

  function handleResponse(response) {
    switch (response.operation) {
        case 'selected':
          addResult(response.info);
          break;
        case 'saved':
          updateResult(response.info);
          break;
        case 'deleted':
          removeResult(response.info)();
          break;
    }
  }

  var exports = {
    addResult: addResult,
    removeResult: removeResult
  };
  $select.data('panels-relation-widget', exports);
}


function renderResult(objInfo, addOnly) {
  addOnly = addOnly | false;
  var html = [];
  var klass = 'panels-relation-widget--result';

  if (objInfo.hasOwnProperty('image_url')) klass += ' has-image';
  if (objInfo.hasOwnProperty('level')) klass += ' mptt-level-'.concat(objInfo.level);
  if (objInfo.hasOwnProperty('parent_id')) klass += ' mptt-parent-'.concat(objInfo.parent_id);

  html.push('<li class="' + klass + '" data-id="' + objInfo.id + '" data-ctype-id="' + objInfo.ctype_id + '">');
  html.push('<span class="handle">☰</span>');

  if (objInfo.hasOwnProperty('image_url')) {
      html.push('<span class="image" style="background-image: url(' + objInfo.image_url + ');"></span>');
  }

  html.push('<span class="verbose-name">' + objInfo.verbose_name + '</span>');
  html.push('<span class="title" title="' + objInfo.title + '">' + objInfo.title + '</span>');
  html.push('<span class="operations">');

  if (objInfo.hasOwnProperty('preview_url')) {
      html.push('<a href="' + objInfo.preview_url + '" class="operation-preview">Preview</a>');
  }

  if (objInfo.hasOwnProperty('change_url')) {
    html.push('<a href="' + objInfo.change_url + '" class="operation-edit">Edit</a>');
  }

  html.push('<a href="#" class="operation-remove">' + (addOnly ? 'Delete' : 'Remove') + '</a>');
  html.push('</span>');
  html.push('</li>');

  var $li = $(html.join(''));
  $li.data('obj-info', objInfo);
  return $li;
}

function pick(key) {
  return function(obj) {
    return obj[key];
  }
}

function toInt(n) {
  return parseInt(n, 10);
}


function eventNotMetaKey(fn) {
  return function(e) {
    if (!e.metaKey) {
      fn.apply(null, arguments);
    }
  }
}



$(function() {
  $('.panels-relation-widget--single').each(function(i, el) {
    setupPanelsRelationWidgetSingle($(el));
  });

$('.panels-relation-widget--multiple:not([autosort="false"]), .panels-relation-widget--polymorphic').each(function(i, el) {
  setupPanelsRelationWidgetMultiple($(el));
  });
});

})();
