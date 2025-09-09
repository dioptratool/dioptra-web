;(function() {

function setupPanelsRelationWidgetMultiple($el) {
  var addOnly = $el.hasClass('add-only');
  var $interventionField = $el.find('#id_interventions');
  var $fieldData = JSON.parse($interventionField.val());
  var $results = $el.find('.panels-relation-widget--results');
  var $controlLinks = $el.find('.panels-relation-widget--control a:not(.dropdown-toggle)');

  // Upcast existing values.
  $results.find('li').each(function(i, li) {
    var objInfo = $(li).data('obj-info');
    objInfo.order = i
    if (!objInfo.instance_pk)
      setTempPK(objInfo)
      $(li).data('obj-info', objInfo);
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
    $fieldData = []
    $results.find('li.panels-relation-widget--result').each(function(i, li) {
      var objInfo = $(li).data('obj-info');
      objInfo.order = i
      $fieldData.push(objInfo);
    });
    $interventionField.val(JSON.stringify($fieldData))
    $interventionField.trigger('change');
  }

  function addResult(objInfo) {
    if (!objInfo.instance_pk)
      setTempPK(objInfo)

    if(!$fieldData.find(intervention => objInfo.instance_pk == intervention.instance_pk)) {
      $fieldData.push(objInfo)
      $interventionField.val(JSON.stringify($fieldData))
      $interventionField.trigger('change');
      $results.append(renderResult(objInfo, addOnly));
    }
  }

  function updateResult(objInfo) {
    const entryIndex = $fieldData.findIndex(intervention => objInfo.instance_pk == intervention.instance_pk)
    if (entryIndex > -1) {
      objInfo.order = $fieldData[entryIndex].order
      $fieldData.splice(entryIndex, 1);
      $fieldData.push(objInfo)
      $interventionField.val(JSON.stringify($fieldData))
    }
    var $li = $results.find('li[data-id="' + objInfo.instance_pk + '"]');
    $li.replaceWith(renderResult(objInfo, addOnly));
    $interventionField.trigger('change');
  }


  function removeResult(objInfo) {
    const entryIndex = $fieldData.findIndex(intervention => objInfo.instance_pk == intervention.instance_pk)
    if (entryIndex > -1) {
      $fieldData.splice(entryIndex, 1);
      $interventionField.val(JSON.stringify($fieldData))
    }
    $results.find('li[data-id="' + objInfo.instance_pk + '"]').remove();
    $interventionField.trigger('change');
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
      var queryString = "?data=" + encodeURIComponent(JSON.stringify(objInfo));
      var url = objInfo.change_url + queryString;
      Panels.open(url).then(
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

  function handleResponse(response) {
    switch (response.operation) {
        case 'selected':
          addResult(response.info.intervention);
          break;
        case 'saved':
          updateResult(response.info.intervention);
          break;
        case 'deleted':
          removeResult(response.info)();
          break;
    }
  }

  function setTempPK(objInfo) {
    let tempPK = -1
    while($fieldData.find((intervention) => intervention.instance_pk == tempPK))
      tempPK--
    objInfo.instance_pk = tempPK
    return objInfo
  }

  $('.panel-head-auxiliary a').on("click", openCreateView)
  function openCreateView(event) {
    event.preventDefault();
    Panels.open(event.target.href).then(
        handleResponse, // Resolve.
        noop, // Reject.
        handleResponse // Progress.
      );
  }
}


function renderResult(objInfo, addOnly) {
  addOnly = addOnly | false;
  var html = [];
  var klass = 'panels-relation-widget--result';
  if (objInfo.hasOwnProperty('image_url')) klass += ' has-image';
  if (objInfo.hasOwnProperty('level')) klass += ' mptt-level-'.concat(objInfo.level);
  if (objInfo.hasOwnProperty('parent_id')) klass += ' mptt-parent-'.concat(objInfo.parent_id);

  html.push('<li class="' + klass + '" data-id="' + objInfo.instance_pk + '">');
  html.push('<span class="handle">☰</span>');

  if (objInfo.hasOwnProperty('image_url')) {
      html.push('<span class="image" style="background-image: url(' + objInfo.image_url + ');"></span>');
  }
  html.push('<span class="verbose-name">' + objInfo.verbose_name + '</span>');
  html.push('<span class="title" title="' + objInfo.title + '">' + objInfo.title + '</span>');
  html.push('<span class="subtitle">' + objInfo.intervention_name);
  if (objInfo.params.length) {
      html.push(' / '); // Add a separator before listing parameters
      for (var i = 0; i < objInfo.params.length; i++) {
          if (i > 0) {
              html.push(', ');
          }
      var label = objInfo.params[i].label;
      var value = objInfo.params[i].value;

      // Check if the label is one of the two special values specific to currency
      if (
        label === "Value of Cash Distributed" ||
        label === "Value of Business Grant Amount"
      ) {
        var numberValue = parseFloat(value);
        if (!isNaN(numberValue)) {
          if (objInfo && objInfo.currency) {
              value = numberValue.toLocaleString("en-US", {
                style: "currency",
                currency: objInfo.currency,
              });
            } else {
              // If no currency, just leave it as a plain number
              value = Number(numberValue).toLocaleString('en-US', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2
              });
            }
        }
      } else {
        var numberValue = parseFloat(value);
        if (!isNaN(numberValue)) {
          value = Number(numberValue).toLocaleString('en-US', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2
          });
        }
      }

          html.push(label + ": " + value);
      }
  }
  html.push('</span>');

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

function eventNotMetaKey(fn) {
  return function(e) {
    if (!e.metaKey) {
      fn.apply(null, arguments);
    }
  }
}

$(function() {
  $('.panels-relation-widget--multiple:not([autosort="false"]), .panels-relation-widget--polymorphic').each(function(i, el) {
    setupPanelsRelationWidgetMultiple($(el));
  });
});


})();
