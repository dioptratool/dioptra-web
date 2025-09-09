
function setupPanelForm($form) {
  handleTaggitAutosuggestChange($form);
  handleCKEditorChange($form);
  handleAnyUrlChange($form);
  setupInputChangeHandlers($form);
  var confirmAbandonmentMessage = $form.attr('data-confirm-abandonment-message');

  // Clearn any 'changed' classes
  $form.find('.form-group.changed').removeClass('changed');

  // Find and disable submit buttons on page load; Enable them if user
  // makes any changes.
  var $submitButton = $form.find('[disable-when-form-unchanged]');
  $submitButton.prop('disabled', true);

  $form.on('panel:inputchanged', function(e) {
    var formHasChanges = !!$form.find('.form-group.changed').length;
    $submitButton.prop('disabled', !formHasChanges);
  });

  function confirmAbandonment(e) {
    var hasChanges = !!$form.find('.form-group.changed').length;
    var hasErrors = !!$form.find('.help-block.errors').length;
    if ((hasChanges || hasErrors) && confirmAbandonmentMessage) {
      var abandonChanges = confirm(confirmAbandonmentMessage);
      if (!abandonChanges) {
        e.preventDefault();
      }
    }
  }

  // Warn user on navigation away from edit/create panel to a localization panel
  $('#localization_link').on('click', confirmAbandonment);

  if (Panels.hasOwnProperty('current')) { // It's in a panel.
    // Reset the event handlers when the page loads so the abandonment
    // confirmation doesn't run multiple times if the form fails to validate
    // multiple times in a row.
    Panels.current.removeListeners('beforeReject');
    Panels.current.on('beforeReject', confirmAbandonment);
  }

  var $deleteButton = $form.find('a.panels-delete-btn');
  $deleteButton.on('click', function(e) {
    e.preventDefault();
    Panels.open($deleteButton.attr('href')).then(Panels.current.resolve);
  });

}

/**
 * Autosuggest and the django package are frustrating and we can't hook into
 * them easily. Use polling to watch if the value changes.
 */
function handleTaggitAutosuggestChange($form) {
  var $autosuggestFormGroups = $form.find('input[id*="__tagautosuggest"]').parents('.form-group');

  $autosuggestFormGroups.each(function(i, formGroup) {
    var $formGroup = $(formGroup);
    var $valueInput = $formGroup.find('input[type="hidden"].as-values');
    $formGroup.find('input').addClass('notrackchange');
    var startingValue = $valueInput.val();
    var lastValue = startingValue;

    setInterval(updateChanged, 300);

    function updateChanged() {
      var value = $valueInput.val();
      if (value == lastValue) {
        // pass.
      }
      else if (value == startingValue) {
        $formGroup.removeClass('changed');
        $formGroup.trigger('panel:inputchanged');
      }
      else {
        $formGroup.addClass('changed');
        $formGroup.trigger('panel:inputchanged');
      }
      lastValue = value;
    }

  });
}

function handleCKEditorChange($form) {
  if (!window.hasOwnProperty('CKEDITOR')) {
    return;
  }
  $form.find('textarea[data-type="ckeditortype"]').addClass('notrackchange');
  for (var key in CKEDITOR.instances) {
    if (CKEDITOR.instances.hasOwnProperty(key)) {
      var instance = CKEDITOR.instances[key];
      instance.on('change', ckeditorChangeHandler);
    }
  }

  function ckeditorChangeHandler(e) {
    var editor = e.editor;
    var $formGroup = $(editor.element.$).parents('.form-group');
    $formGroup
      .toggleClass('changed', editor.checkDirty())
      .trigger('panel:inputchanged');
  }
}

function handleAnyUrlChange($form) {
  var $typeWrappers = $form.find('ul.any_urlfield-url_type');

  $typeWrappers.each(function(i, typeWrapperEl) {
    handleField($(typeWrapperEl).parents('.form-group'));
  });

  function handleField($formGroup) {
    var startingVal = getValue($formGroup);
    var lastVal  = startingVal;

    var requiredFields = !!$formGroup.find(':input[required]').length;

    $formGroup
      .find(':input')
      .addClass('notrackchange')
      .on('change keyup', update);

    update();

    function update() {
      var val = getValue($formGroup);
      if (val == lastVal) {
        // pass.
      }
      else if (val == startingVal) {
        $formGroup.removeClass('changed');
        $formGroup.trigger('panel:inputchanged');
      }
      else {
        $formGroup.addClass('changed');
        $formGroup.trigger('panel:inputchanged');
      }
      lastVal = val;

      // Change which element is required.
      if (requiredFields) {
        $formGroup
          .find(':input')
          .not('[type="radio"]')
          .removeAttr('required');
        getActivePane($formGroup).find(':input').attr('required', 'required');
      }
    }
  }

  function getValue($formGroup) {
    var $typeRadios = $formGroup.find('input[type="radio"]');
    var typeVal = $typeRadios.filter(':checked').val();
    var $pane = getActivePane($formGroup);
    return typeVal + ':' + $pane.find(':input').val();
  }

  function getActivePane($formGroup) {
    var $typeRadios = $formGroup.find('input[type="radio"]');
    var typeVal = $typeRadios.filter(':checked').val();
    var $pane = $formGroup.find('.any_urlfield-url-' + typeVal.replace(/[^a-z0-9-_]/, ''));
    return $pane;
  }

}

function setupInputChangeHandlers($form) {
  // Track changes on form elements.
  var $inputs = $form.find(':input:not(.notrackchange)')
  var startingValues = $inputs.toArray()
                      .reduce(function(values, input) {
                        var $input = $(input);
                        values[$input.attr('name')] = inputVal($input);
                        return values;
                      }, {});

  $inputs.on('change keyup', inputChanged);

  function inputChanged(e) {
    var $input = $(e.target);
    var name = $input.attr('name');
    if (startingValues[name] == inputVal($input)) {
      $input.parents('.form-group').removeClass('changed');
    }
    else {
      $input.parents('.form-group').addClass('changed');
    }

    $input.trigger('panel:inputchanged');
  }

  function inputVal($input) {
    if ($input.attr('type') === 'checkbox') {
      var name = $input.attr('name');
      var $checkboxes = $form.find(':input[name="' + name + '"]');
      return $checkboxes
                .toArray()
                .map(function(checkbox) {
                  var $checkbox = $(checkbox);
                  return $checkbox.is(':checked') ? $checkbox.val() : '';
                })
                .join(',');
    }
    return $input.val();
  }
}

function setupPanelTabs($formTabs) {
  var $tabs = $formTabs.find('.form-tabs-tabs [data-tab]');
  $tabs.on('click', function(e) {
    var $clickedTab = $(this);
    $tabs.removeClass('active');
    $clickedTab.addClass('active');
    $formTabs
      .find('.form-tabs-contents [data-tab]')
      .removeClass('active')
      .filter('[data-tab="' + $clickedTab.attr('data-tab') + '"]')
      .addClass('active');
    $(window).trigger('resize');
  });

  if ($tabs.filter('.error').length) {
    // Open to a tab with an error.
    $tabs.filter('.error').first().click();
  }
  else if (window.location.hash) {
    // Form was opened to a specific tab.
    var hash = window.location.hash.slice().replace('#', '');
    if (hash.length) {
      $tabs.filter('[data-tab="' + hash + '"]').first().click();
    }
  }

  // Make tabs show changed status.
  $formTabs
    .find('.form-tabs-contents [data-tab]')
    .each(function(i, tabContent) {
      var $tabContent = $(tabContent);
      $tabContent.on('panel:inputchanged', function(e) {
        var hasChanged = !!$tabContent.find('.changed').length;
        var tabSlug = $tabContent.attr('data-tab');
        $formTabs.find('.form-tabs-tabs [data-tab="' + tabSlug + '"]').toggleClass('changed', hasChanged)
      });
    });

  var $formTabContents = $formTabs.find('.form-tabs-contents');
  if ($formTabContents.length) {
    onScrollTopAndBottom(
      $('.form-tabs-contents-scroller')[0],
      function atTopCallback(isAtTop) {
        $formTabContents.toggleClass('contents-at-top', isAtTop);
      },
      function atBottomCallback(isAtBottom) {
        $formTabContents.toggleClass('contents-at-bottom', isAtBottom);
      }
    );
  }
}

$(function() {
  var $form = $('form.panel-form');
  if ($form.length) {
    setupPanelForm($form);
  }

  var $formTabs = $('.form-tabs');
  if ($formTabs.length) {
    setupPanelTabs($formTabs);
  }

  // In the nested reorder view of an object with localization,
  // allow user to toggle between different sets of objects in different
  // localizations
  $('.nested-reorder-locale-select').change(function() {
    window.location.replace(window.location.href.split('?')[0] + '?locale=' + $(this).val());
  });

  // In the Localization management view, ask users if they are sure they want to delete an item
  $('.localization-menu--operations-link--delete').on('click', function(e) {
    var choice = confirm('Are you sure you want to delete this item forever?');
    if(!choice) {
      e.preventDefault();
    }
  });
});

// Allow user to hit 'Enter' to add tags using Tags field
function tagsFieldEnter() {
    var $tagsField = $('#id_tags__tagautosuggest');

    $tagsField.on('keydown', function(e) {
        if (e.keyCode == 13) {
            // 'Enter' was pressed; Trigger 'Tab' keydown
            e.preventDefault();
            var new_e = jQuery.Event("keydown");
            new_e.keyCode = 9;
            $(this).trigger(new_e);
        }
    });
}

$(document).ready(function() {
    tagsFieldEnter();
});
