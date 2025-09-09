$(function() {

  $('.nested-polymorphic-reorder > ol').each(function(i, ol) {
    initializeNestedSortable($(ol));
  });

  function initializeNestedSortable($ol) {
    var $controlLinks = $ol.parent().find('.nested-polymorphic-reorder--control a:not(.dropdown-toggle)');
    var $results = $ol;
    var $treeReorderInput = $ol.prev('.tree-reorder-input').find('input');
    $controlLinks.on('click', controlLinkClick);

    // Use event delegation so we don't have to rebind.
    $results.on('click', 'a.operation-remove', removeClick)
    $results.on('click', 'a.operation-edit', editClick)

    // Initialize the sortable.
    var startPos = {parent: null, pos: null};
    $results.nestedSortable({
      handle: 'div > .handle',
      items: 'li',
      toleranceElement: '> div',
      isTree: true,
      start: dragStart,
      stop: dragStop,
      disableNestingClass: "mjs-nestedSortable-no-nesting"
    });
    $treeReorderInput.attr('value', JSON.stringify($results.nestedSortable('toHierarchy')));


    function buildItem(objInfo) {
      var jsonObjInfo = JSON.stringify(objInfo);
      var listItem = "<li class='tree-node mjs-nestedSortable-leaf' id='menuItem_" + objInfo.id + "' data-id='" + objInfo.id + "' data-allowed-children='" + objInfo.allowed_children + "' data-obj-info='" + jsonObjInfo + "'>" +
                        "<div>" +
                          "<span class='handle ui-sortable-handle'>☰</span>" +
                          "<span class='verbose-name' title='" + objInfo.verbose_name + "'>" + objInfo.verbose_name + "</span>" +
                          "<span class='title' title='" + objInfo.title + "'>" + objInfo.title + " | " + Math.round((objInfo.width/12) * 100).toString() + "%</span>" +
                          "<span class='operations'>" +
                            "<a href='" + objInfo.change_url + "' class='operation-edit'>Edit</a>" +
                            "<a href='#' class='operation-remove'>Delete</a>" +
                          "</span>" +
                        "</div>" +
                      "</li>";
      return listItem;
    }

    function removeClick(e) {
      e.preventDefault();
      var objInfo = $(e.target).parents('li:first').data('obj-info');
      if (objInfo && window.confirm("Are you sure want to delete '" + objInfo.title + "'?\n\nAll nested blocks WILL be deleted.")) {
        $(e.target).parents('li:first').remove();
        updateTreeJson();
      }
    }

    function addResult(objInfo) {
      var listItem = buildItem(objInfo);
      $results.append(listItem);
      updateTreeJson();
    }

    function updateResult(objInfo) {
      var $updatedListItem = $(buildItem(objInfo));
      var $toReplace = $('[data-id=' + objInfo.id + ']');
      $toReplace.children('ol').clone().appendTo($updatedListItem);
      $toReplace.replaceWith($updatedListItem);
    }

    function updateTreeJson() {
      $treeReorderInput.attr('value', JSON.stringify($results.nestedSortable('toHierarchy')));
      $treeReorderInput.trigger('change');
    }

    function controlLinkClick(e) {
      e.preventDefault();
      var $link = $(e.target);
      Panels.open($link.attr('href'))
        .then(
          ifPick('info', addResult), // Resolve.
          noop, // Reject.
          ifPick('info', addResult) // Progress.
        );
    }

    function editClick(e) {
      e.preventDefault();
      e.stopPropagation();
      var $link = $(e.target);
      Panels.open($link.attr('href'))
        .then(
          ifPick('info', updateResult), // Resolve.
          noop, // Reject.
          ifPick('info', updateResult) // Progress.
        );
    }

    function pick(key) {
      return function(obj) {
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

    function dragStart(e, data) {
      startPos = getPos(data.item);
      var itemVerboseName = data.item.data('objInfo').verbose_name;
      $('li.tree-node').not($('[data-allowed-children*="' + itemVerboseName + '"]')).addClass('mjs-nestedSortable-no-nesting');
    }

    function dragStop(e, data) {
      var endPos = getPos(data.item);
      var hasMoved = !posEquals(startPos, endPos);
      if (hasMoved) {
        updateTreeJson($(e.target));
      }
      var itemVerboseName = data.item.data('objInfo').verbose_name;
      $('li.tree-node').not($('[data-allowed-children*="' + itemVerboseName + '"]')).removeClass('mjs-nestedSortable-no-nesting');
    }

    function getPos($item) {
      return {
        parent: $item.parent().get(0),
        pos: $item.prevAll().length
      }
    }

    function posEquals(pos1, pos2) {
      return (pos1.parent == pos2.parent) && (pos1.pos == pos2.pos);
    }

  }

});
