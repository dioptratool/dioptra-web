/**
 * In-app corrections (Feature 91): the bulk Edit button and the Allocate unsaved-changes guard.
 *
 * Single-row edit links are ordinary `data-panels-trigger` links with `data-panels-reload-on`,
 * handled by the panels layer. This script adds:
 *
 * - `button.correction-bulk-edit`: POSTs the current selection to the selection endpoint and
 *   opens the panel URL it answers with (a Select All can be thousands of ids, so the ids never
 *   travel in a query string).
 * - On Allocate (`.analysis-table[data-unsaved-prompt-url]`), while an allocation form has unsaved
 *   changes, an edit action first opens the confirmation panel (Save and continue / Discard /
 *   Cancel). Save and continue posts the dirty forms, reloads, and reopens the edit panel; its URL
 *   is parked in sessionStorage across the reload.
 */
;(function ($) {
  var PENDING_PANEL_KEY = 'dioptra.corrections.pendingPanel';

  // The same outcome handling as the panels layer's trigger links.
  function openPanel(url) {
    Panels.open(url).then(
      function (event) {
        if (event && event.redirect_to) {
          $(window).off('beforeunload');
          window.location = event.redirect_to;
        } else if (event && event.operation === 'saved') {
          $(window).off('beforeunload');
          window.location.reload();
        }
      },
      function () {}
    );
  }

  function dirtyForms() {
    return $('form.warn-unsaved-changes')
      .filter(function () {
        return $(this).hasClass('dirty') || $(this).find('[data-changed]').length > 0;
      })
      .get();
  }

  function guardedOpen(url) {
    var table = document.querySelector('.analysis-table[data-unsaved-prompt-url]');
    var forms = dirtyForms();
    if (!table || !forms.length) {
      openPanel(url);
      return;
    }
    Panels.open(table.dataset.unsavedPromptUrl).then(
      function (event) {
        if (event && event.choice === 'save') {
          saveThenReopen(forms, url);
        } else if (event && event.choice === 'discard') {
          openPanel(url);
        }
      },
      function () {}
    );
  }

  // Post each dirty form the way its Save button would. `fetch` is used for this one call
  // because only `response.redirected` tells a successful save (302 to the page) from a
  // validation re-render (200); on failure the form is submitted normally so its errors show.
  function saveThenReopen(forms, url) {
    var index = 0;

    function next() {
      if (index >= forms.length) {
        try {
          window.sessionStorage.setItem(PENDING_PANEL_KEY, url);
        } catch (error) {
          // Storage unavailable: the user reopens the panel by hand after the reload.
        }
        $(window).off('beforeunload');
        window.location.reload();
        return;
      }
      var form = forms[index++];
      // Not `form.action`: the allocation form contains buttons named "action".
      var action = new URL(form.getAttribute('action') || window.location.href, window.location.href);
      fetch(action.toString(), { method: 'POST', body: new FormData(form), credentials: 'same-origin' })
        .then(function (response) {
          if (response.ok && response.redirected) {
            next();
          } else {
            $(window).off('beforeunload');
            form.submit();
          }
        })
        .catch(function () {
          $(window).off('beforeunload');
          form.submit();
        });
    }

    next();
  }

  function openBulkPanel(button) {
    var $form = $(button).closest('form');
    var helper = window.AnalysisTableNestedCheckboxes;
    var payload = helper ? helper.buildSelectionPayload($form, button.dataset.selectionKind) : null;
    if (!payload) {
      return;
    }
    var data = {
      kind: button.dataset.selectionKind,
      step: button.dataset.selectionStep,
      ids: payload.ids,
      cost_line_item_ids: payload.cost_line_item_ids,
    };
    if (button.dataset.costType) {
      data.cost_type = button.dataset.costType;
    }

    button.disabled = true;
    $.ajax({
      type: 'POST',
      url: button.dataset.selectionUrl,
      data: data,
      traditional: true, // ids=1&ids=2, as request.POST.getlist expects
      dataType: 'json',
      headers: { 'X-CSRFToken': $form.find('input[name="csrfmiddlewaretoken"]').val() },
    })
      .then(function (response) {
        button.disabled = false;
        guardedOpen(response.url);
      })
      .fail(function (error) {
        button.disabled = false;
        window.alert('The selection could not be opened. Reload the page and try again.');
        if (window.console) {
          console.error(error);
        }
      });
  }

  // Runs before the panels layer's own (body-delegated) trigger handler; when the allocation
  // form is dirty it takes over the click so the prompt can be shown first.
  document.addEventListener(
    'click',
    function (e) {
      var link = e.target.closest ? e.target.closest('a[data-panels-trigger]') : null;
      if (!link || e.metaKey || !link.closest('.analysis-table[data-unsaved-prompt-url]')) {
        return;
      }
      if (!dirtyForms().length) {
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      var popover = link.closest('[popover]');
      if (popover && typeof popover.hidePopover === 'function') {
        popover.hidePopover();
      }
      guardedOpen(link.href);
    },
    true
  );

  $(function () {
    $('body').on('click', 'button.correction-bulk-edit', function (e) {
      e.preventDefault();
      openBulkPanel(this);
    });
  });

  // After a Save and continue reload, reopen the edit panel. `load` runs after every ready
  // handler, so the panels layer has defined `Panels` by then.
  $(window).on('load', function () {
    var pending = null;
    try {
      pending = window.sessionStorage.getItem(PENDING_PANEL_KEY);
      if (pending) {
        window.sessionStorage.removeItem(PENDING_PANEL_KEY);
      }
    } catch (error) {
      pending = null;
    }
    if (pending && window.Panels) {
      openPanel(pending);
    }
  });
})(jQuery);
