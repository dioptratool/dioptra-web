;(function() {


function setupGenericManyToManyWidget($el) {
  var $select = $el.find('select');
  var $results = $el.find('.panels-relation-widget--results');
  var $controlLinks = $el.find('.panels-relation-widget--control a:not(.dropdown-toggle)');

  // Upcast existing values.
  $results.find('li').each(function(i, li) {
    var objInfo = $(li).data('obj-info');
    var $li = renderResult(objInfo);
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
    $results.find('li').each(function(i, li) {
      var objInfo = $(li).data('obj-info');
      $select.append(renderOption(objInfo));
    });
    $select.trigger('change');
  }

  function addResult(objInfo) {
    var vals = $select.val() ? $select.val() : [];
    if (vals.indexOf(idWithCtype(objInfo)) >= 0) {
      // Already added.
      return;
    }
    $results.append(renderResult(objInfo));
    $select.append(renderOption(objInfo));
    $select.trigger('change');
  }

  function updateResult(objInfo) {
    var $option = $select.find('option[value="' + idWithCtype(objInfo) + '"]');
    var $li = $results.find('li[data-id="' + idWithCtype(objInfo) + '"]');
    $option.replaceWith(renderOption(objInfo));
    $li.replaceWith(renderResult(objInfo));
  }


  function removeResult(objInfo) {
    $results.find('li[data-id="' + idWithCtype(objInfo) + '"]').remove();
    $select.find('option[value="' + idWithCtype(objInfo) + '"]').remove();
    $select.trigger('change');
  }

  function controlLinkClick(e) {
    e.preventDefault();
    var $link = $(e.target);
    Panels.open($link.attr('href')).then(
      ifPick('info', addResult), // Resolve.
      noop, // Reject.
      ifPick('info', addResult) // Progress.
    );
  }

  function editClick(e) {
    e.preventDefault();
    var objInfo = $(e.target).parents('.panels-relation-widget--result').data('obj-info');
    if (objInfo) {
      Panels.open(objInfo.change_url).then(
        ifPick('info', updateResult), // Resolve.
        noop, // Reject.
        ifPick('info', updateResult) // Progress.
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
    return '<option value="' + idWithCtype(objInfo) + '" selected="selected">' + objInfo.title + '</option>';
  }
}



function renderResult(objInfo) {
  var html = [];
  var klass = 'panels-relation-widget--result';

  if (objInfo.hasOwnProperty('image_url')) klass += ' has-image';

  html.push('<li class="' + klass + '" data-id="' + idWithCtype(objInfo) + '" data-ctype-id="' + objInfo.ctype_id + '">');
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

  html.push('<a href="#" class="operation-remove">Remove</a>');
  html.push('</span>');
  html.push('</li>');

  var $li = $(html.join(''));
  $li.data('obj-info', objInfo);
  return $li;
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

function idWithCtype(objInfo) {
  return objInfo.ctype_id + '/' + objInfo.id;
}

function pick(key) { return function(obj) {
    if (obj.hasOwnProperty(key)) {
      return obj[key];
    }
    return undefined;
  }
}

function ifPick(key, fn) {
  return function(obj) {
    var result = pick(key)(obj);
    if (result) {
      return fn(result);
    }
  }
}


$(function() {

  $('.generic-many-to-many-widget').each(function(i, el) {
    setupGenericManyToManyWidget($(el));
  });

});

})();
