


$(function () {
  $(function() {

  $('.nested-reorder > ol').each(function(i, ol) {
    initializeHelpMenuNestedSortable($(ol));
  });

  function initializeHelpMenuNestedSortable($ol) {
    $ol.nestedSortable({
      handle: 'div > .handle',
      items: 'li',
      toleranceElement: '> div',
      isTree: true,
      start: dragStart,
      stop: dragStop,
      protectRoot: true,

    });

    var saveHref = $ol.attr('data-href');
    var csrfToken = $ol.attr('data-csrf-token');
    var startPos = {parent: null, pos: null};

    function dragStart(e, data) {
      startPos = getPos(data.item);
    }

    function dragStop(e, data) {
      var endPos = getPos(data.item);
      var hasMoved = !posEquals(startPos, endPos);
      if (hasMoved) {
        saveNewPosition(data.item);
      }
    }

    function saveNewPosition($item) {
      var data = getMoveData($item);
      if (data) {
        data.csrfmiddlewaretoken = csrfToken;
        $.ajax({
            method: 'POST',
            data: data,
        })
        .done(function(data) {
          data.messages.map(function(message) {
            Panels.alert(message, 1000);
          });
        })
        .fail(function(e) {
          alert('An error occured while saving.');
          window.location.reload();
        });
      }
    }

    function getMoveData($item) {
      var pk = $item.attr('data-pk');
      if ($item.prev('li').length) {
        // Nested with previous sibling.
        return {
          node_pk: pk,
          target_pk: $item.prev('li').attr('data-pk'),
          position: 'right'
        }
      }
      else if ($item.parents('li').length) {
        // Nested without previous sibling.
        return {
          node_pk: pk,
          target_pk: $item.parents('li:first').attr('data-pk'),
          position: 'first-child'
        }
      }
      else if ($item.next('li').length) {
        // Root level first item.
        return {
          node_pk: pk,
          target_pk: $item.next('li').attr('data-pk'),
          position: 'left'
        }
      }
      return false;
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


});