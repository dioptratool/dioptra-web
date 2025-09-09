/* ========================================================================
 * Bootstrap: dropdown.js v3.4.1
 * https://getbootstrap.com/docs/3.4/javascript/#dropdowns
 * ========================================================================
 * Copyright 2011-2019 Twitter, Inc.
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 * ======================================================================== */


+function ($) {
  'use strict';

  // DROPDOWN CLASS DEFINITION
  // =========================

  var backdrop = '.dropdown-backdrop'
  var toggle   = '[data-toggle="dropdown"]'
  var Dropdown = function (element) {
    $(element).on('click.bs.dropdown', this.toggle)
  }

  Dropdown.VERSION = '3.4.1'

  function getParent($this) {
    var selector = $this.attr('data-target')

    if (!selector) {
      selector = $this.attr('href')
      selector = selector && /#[A-Za-z]/.test(selector) && selector.replace(/.*(?=#[^\s]*$)/, '') // strip for ie7
    }

    var $parent = selector !== '#' ? $(document).find(selector) : null

    return $parent && $parent.length ? $parent : $this.parent()
  }

  function clearMenus(e) {
    if (e && e.which === 3) return
    $(backdrop).remove()
    $(toggle).each(function () {
      var $this         = $(this)
      var $parent       = getParent($this)
      var relatedTarget = { relatedTarget: this }

      if (!$parent.hasClass('open')) return

      if (e && e.type == 'click' && /input|textarea/i.test(e.target.tagName) && $.contains($parent[0], e.target)) return

      $parent.trigger(e = $.Event('hide.bs.dropdown', relatedTarget))

      if (e.isDefaultPrevented()) return

      $this.attr('aria-expanded', 'false')
      $parent.removeClass('open').trigger($.Event('hidden.bs.dropdown', relatedTarget))
    })
  }

  Dropdown.prototype.toggle = function (e) {
    var $this = $(this)

    if ($this.is('.disabled, :disabled')) return

    var $parent  = getParent($this)
    var isActive = $parent.hasClass('open')

    clearMenus()

    if (!isActive) {
      if ('ontouchstart' in document.documentElement && !$parent.closest('.navbar-nav').length) {
        // if mobile we use a backdrop because click events don't delegate
        $(document.createElement('div'))
          .addClass('dropdown-backdrop')
          .insertAfter($(this))
          .on('click', clearMenus)
      }

      var relatedTarget = { relatedTarget: this }
      $parent.trigger(e = $.Event('show.bs.dropdown', relatedTarget))

      if (e.isDefaultPrevented()) return

      $this
        .trigger('focus')
        .attr('aria-expanded', 'true')

      $parent
        .toggleClass('open')
        .trigger($.Event('shown.bs.dropdown', relatedTarget))
    }

    return false
  }

  Dropdown.prototype.keydown = function (e) {
    if (!/(38|40|27|32)/.test(e.which) || /input|textarea/i.test(e.target.tagName)) return

    var $this = $(this)

    e.preventDefault()
    e.stopPropagation()

    if ($this.is('.disabled, :disabled')) return

    var $parent  = getParent($this)
    var isActive = $parent.hasClass('open')

    if (!isActive && e.which != 27 || isActive && e.which == 27) {
      if (e.which == 27) $parent.find(toggle).trigger('focus')
      return $this.trigger('click')
    }

    var desc = ' li:not(.disabled):visible a'
    var $items = $parent.find('.dropdown-menu' + desc)

    if (!$items.length) return

    var index = $items.index(e.target)

    if (e.which == 38 && index > 0)                 index--         // up
    if (e.which == 40 && index < $items.length - 1) index++         // down
    if (!~index)                                    index = 0

    $items.eq(index).trigger('focus')
  }


  // DROPDOWN PLUGIN DEFINITION
  // ==========================

  function Plugin(option) {
    return this.each(function () {
      var $this = $(this)
      var data  = $this.data('bs.dropdown')

      if (!data) $this.data('bs.dropdown', (data = new Dropdown(this)))
      if (typeof option == 'string') data[option].call($this)
    })
  }

  var old = $.fn.dropdown

  $.fn.dropdown             = Plugin
  $.fn.dropdown.Constructor = Dropdown


  // DROPDOWN NO CONFLICT
  // ====================

  $.fn.dropdown.noConflict = function () {
    $.fn.dropdown = old
    return this
  }


  // APPLY TO STANDARD DROPDOWN ELEMENTS
  // ===================================

  $(document)
    .on('click.bs.dropdown.data-api', clearMenus)
    .on('click.bs.dropdown.data-api', '.dropdown form', function (e) { e.stopPropagation() })
    .on('click.bs.dropdown.data-api', toggle, Dropdown.prototype.toggle)
    .on('keydown.bs.dropdown.data-api', toggle, Dropdown.prototype.keydown)
    .on('keydown.bs.dropdown.data-api', '.dropdown-menu', Dropdown.prototype.keydown)

}(jQuery);

/*!
 * jQuery Plugin: Are-You-Sure (Dirty Form Detection)
 * https://github.com/codedance/jquery.AreYouSure/
 *
 * Copyright (c) 2012-2014, Chris Dance and PaperCut Software http://www.papercut.com/
 * Dual licensed under the MIT or GPL Version 2 licenses.
 * http://jquery.org/license
 *
 * Author:  chris.dance@papercut.com
 * Version: 1.9.0
 * Date:    13th August 2014
 */
(function($) {
  
  $.fn.areYouSure = function(options) {
      
    var settings = $.extend(
      {
        'message' : 'You have unsaved changes!',
        'dirtyClass' : 'dirty',
        'change' : null,
        'silent' : false,
        'addRemoveFieldsMarksDirty' : false,
        'fieldEvents' : 'change keyup propertychange input',
        'fieldSelector': ":input:not(input[type=submit]):not(input[type=button])"
      }, options);

    var getValue = function($field) {
      if ($field.hasClass('ays-ignore')
          || $field.hasClass('aysIgnore')
          || $field.attr('data-ays-ignore')
          || $field.attr('name') === undefined) {
        return null;
      }

      if ($field.is(':disabled')) {
        return 'ays-disabled';
      }

      var val;
      var type = $field.attr('type');
      if ($field.is('select')) {
        type = 'select';
      }

      switch (type) {
        case 'checkbox':
        case 'radio':
          val = $field.is(':checked');
          break;
        case 'select':
          val = '';
          $field.find('option').each(function(o) {
            var $option = $(this);
            if ($option.is(':selected')) {
              val += $option.val();
            }
          });
          break;
        default:
          val = $field.val();
      }

      return val;
    };

    var storeOrigValue = function($field) {
      $field.data('ays-orig', getValue($field));
    };

    var checkForm = function(evt) {

      var isFieldDirty = function($field) {
        var origValue = $field.data('ays-orig');
        if (undefined === origValue) {
          return false;
        }
        return (getValue($field) != origValue);
      };

      var $form = ($(this).is('form')) 
                    ? $(this)
                    : $(this).parents('form');

      // Test on the target first as it's the most likely to be dirty
      if (isFieldDirty($(evt.target))) {
        setDirtyStatus($form, true);
        return;
      }

      $fields = $form.find(settings.fieldSelector);

      if (settings.addRemoveFieldsMarksDirty) {              
        // Check if field count has changed
        var origCount = $form.data("ays-orig-field-count");
        if (origCount != $fields.length) {
          setDirtyStatus($form, true);
          return;
        }
      }

      // Brute force - check each field
      var isDirty = false;
      $fields.each(function() {
        $field = $(this);
        if (isFieldDirty($field)) {
          isDirty = true;
          return false; // break
        }
      });
      
      setDirtyStatus($form, isDirty);
    };

    var initForm = function($form) {
      var fields = $form.find(settings.fieldSelector);
      $(fields).each(function() { storeOrigValue($(this)); });
      $(fields).unbind(settings.fieldEvents, checkForm);
      $(fields).bind(settings.fieldEvents, checkForm);
      $form.data("ays-orig-field-count", $(fields).length);
      setDirtyStatus($form, false);
    };

    var setDirtyStatus = function($form, isDirty) {
      var changed = isDirty != $form.hasClass(settings.dirtyClass);
      $form.toggleClass(settings.dirtyClass, isDirty);
        
      // Fire change event if required
      if (changed) {
        if (settings.change) settings.change.call($form, $form);

        if (isDirty) $form.trigger('dirty.areYouSure', [$form]);
        if (!isDirty) $form.trigger('clean.areYouSure', [$form]);
        $form.trigger('change.areYouSure', [$form]);
      }
    };

    var rescan = function() {
      var $form = $(this);
      var fields = $form.find(settings.fieldSelector);
      $(fields).each(function() {
        var $field = $(this);
        if (!$field.data('ays-orig')) {
          storeOrigValue($field);
          $field.bind(settings.fieldEvents, checkForm);
        }
      });
      // Check for changes while we're here
      $form.trigger('checkform.areYouSure');
    };

    var reinitialize = function() {
      initForm($(this));
    }

    if (!settings.silent && !window.aysUnloadSet) {
      window.aysUnloadSet = true;
      $(window).bind('beforeunload', function() {
        $dirtyForms = $("form").filter('.' + settings.dirtyClass);
        if ($dirtyForms.length == 0) {
          return;
        }
        // Prevent multiple prompts - seen on Chrome and IE
        if (navigator.userAgent.toLowerCase().match(/msie|chrome/)) {
          if (window.aysHasPrompted) {
            return;
          }
          window.aysHasPrompted = true;
          window.setTimeout(function() {window.aysHasPrompted = false;}, 900);
        }
        return settings.message;
      });
    }

    return this.each(function(elem) {
      if (!$(this).is('form')) {
        return;
      }
      var $form = $(this);
        
      $form.submit(function() {
        $form.removeClass(settings.dirtyClass);
      });
      $form.bind('reset', function() { setDirtyStatus($form, false); });
      // Add a custom events
      $form.bind('rescan.areYouSure', rescan);
      $form.bind('reinitialize.areYouSure', reinitialize);
      $form.bind('checkform.areYouSure', checkForm);
      initForm($form);
    });
  };
})(jQuery);



function getDioptraCurrencySymbol() {
  var configEl = document.getElementById('dioptra-currency')
  console.log(configEl)
  if (configEl) {
    var config = JSON.parse(configEl.innerHTML)
    console.log(config)
    if (config.symbol) {
      return config.symbol
    }
  }
  return '$'
}
$(function() {
  // Open flatpickr on click of calendar icon
  $('.form__date-icon').on('click', function(e){
    $(this).closest('.form__date').find('.flatpickr-input').focus();
  });


  $('input[name="upload-type"]').on('click', function(e){
    const formType = $(this).val()
    $(this).closest('form').find(`.form-group:not([data-section])`).addClass('active')
    $(this).closest('form').find(`[data-section]`).removeClass('active')
    $(this).closest('form').find(`[data-section="${formType}"]`).addClass('active')
  });

  // Increment and decrement number input on click
  $('.form__number-toggle--decrease').on('click', function(e){
    e.preventDefault();
    var input = $(this).closest('.form__number').find('input[type="number"]').not(':disabled')
   if (input.length) {
      input[0].stepDown();
    }
  }); 
  $('.form__number-toggle--increase').on('click', function(e){
    e.preventDefault();
    var input = $(this).closest('.form__number').find('input[type="number"]').not(':disabled')
    if (input.length) {
      input[0].stepUp();
    }
  });

  // print selected file by file input
  // disable button if no file is present
  function checkFile($fileInput, fileName) {
    var $formFile = $fileInput.closest('.form__file');
    if (fileName) {
      $formFile.find('.form__file-names').html(''); // Clear the previous value.
      $formFile.find('.form__file-names').append('<div class="form__file-name">' + fileName + '</div>');
      $formFile.addClass('form__file--selected');
      $formFile.find('.form__file-button').text('Choose a different file');
    }
    if ($fileInput.closest('form').find('.form__file-button--upload').length) {
      var $formFileUploadButton = $fileInput.closest('form').find('.form__file-button--upload');
      if ($fileInput.val()) {
        $formFileUploadButton.removeAttr('disabled');
      }
      else {
        $formFileUploadButton.attr('disabled', 'true');
      }
    }   
  }

  $('.form__file input[type="file"]').each(function( index ) {
    var fileName = '';
    if (this.files[0]) {
      var fileName = this.files[0].name;
    }
    checkFile($(this), fileName);
  });

  $('.form__file input[type="file"]').change(function(e){
    var fileName = e.target.files[0].name;
    checkFile($(this), fileName);
  });

  $('[data-click-confirm]').on('click', function(e) {
    var message = $(e.currentTarget).data('click-confirm');
    if (!window.confirm(message)) {
      e.preventDefault();
    }
  });

  $('form.warn-unsaved-changes').areYouSure(
    {'message': 'There are unsaved changes on this step. Are you sure you want to leave? Click Leave to move away without saving. Click Cancel to stay on the step and save your work.'}
  );


});




$(function() {

  $('form[data-show-loading-on-submit]').on('submit', function(e) {
    $('body').addClass('loading');
  });

});

$(function() {
  $('.analysis-table__category-toggle').on('click', function(e){
    e.preventDefault();
    $(this).closest('.analysis-table__category').toggleClass('analysis-table__category--active');
  }); 

  $('.analysis-table__transactions-toggle').on('click', function(e) {
    e.preventDefault();
    $(this).closest('tbody').find('.analysis-table__transaction-row').toggleClass('analysis-table__transaction-row--active')
    $(this).closest('tbody').toggleClass('analysis-table__tbody--transactions-active')
  });

  $('.analysis-table__category-edit').on('click', function(e) {
    e.preventDefault();
    $(this).closest('tbody').find('.analysis-table__edit-row').toggleClass('analysis-table__edit-row--active');
    $(this).closest('tbody').toggleClass('analysis-table__tbody--edit-active')
  });

  $('.analysis-table__category--unconfirmed').first().addClass("analysis-table__category--active");

  $('.analysis-table__category-edit--note').on('click', function(e) {
    $('.analysis-table__category-footer-action').hide();
    $('.analysis-table__actions').hide();
  });

  $('.analysis-table__set-contribution input[type="checkbox"]').on('change', function(e) {
    $(this).closest('label').toggleClass('checked')
  });
});
$(function() {

    var $form = $('form#fix-missing-data');
    if ($form.length) {
        initFixMissingData($form);
    }

    $('.analysis-fix-data__select-no-value').on('change', function(e){
        $(this).removeClass('analysis-fix-data__select-no-value');
    });

    function initFixMissingData($form) {

        var $selectAllCheckbox = $form.find('input[type="checkbox"].select-all');
        var $bulkCheckboxes = $form.find('input[type="checkbox"].bulk-checkbox');
        var $bulkAssignItems = $form.find('button.bulk-assign-items');
        var bulkUrl = $bulkAssignItems.attr('data-href');

        $selectAllCheckbox.on('change', function() {
            if ($selectAllCheckbox.prop('checked')) {
                selectAll();
            }
            else {
                selectNone();
            }
        });

        $bulkAssignItems.on('click', function(e) {
            e.preventDefault();
            assignCheckedItems();
        });

        $bulkCheckboxes.on('change', function() {
            if (getCheckedConfigIds().length == 0) {
                $bulkAssignItems.prop('disabled', true);
            }
            else {
                $bulkAssignItems.prop('disabled', false);
            }
        });

        // Only enable the bulk checkbox once the page is done fully loading.
        $selectAllCheckbox.prop('disabled', false);

        function selectAll() {
            $bulkCheckboxes.prop('checked', true);
            $bulkCheckboxes.trigger('change');
        }

        function selectNone() {
            $bulkCheckboxes.prop('checked', false);
            $bulkCheckboxes.trigger('change');
        }

        function assignCheckedItems() {
            var configIds = getCheckedConfigIds();
            var queryString = '?config_ids=' + configIds.join(',');
            var url = bulkUrl + queryString;
            Panels.open(url).then(function() {
                window.location.reload();
            });
        }

        function getCheckedConfigIds() {
            return $bulkCheckboxes
                .filter(':checked')
                .toArray()
                .map(function(checkboxEl) {
                    return parseInt(checkboxEl.value, 10);
                })
        }
    }

});

$(function() {

    $('form.categorize-cost_type-bulk-form').each(function () {
        setupBulkForm($(this))
    });


    function setupBulkForm($form) {
        var $selectAllCheckbox = $form.find('input[type="checkbox"].select-all');
        var $bulkCheckboxes = $form.find('input[type="checkbox"].bulk-checkbox');
        var $bulkAssignItems = $form.find('button.bulk-assign-items');
        var bulkUrl = $bulkAssignItems.attr('data-href');

        $selectAllCheckbox.on('change', function () {
            if ($selectAllCheckbox.prop('checked')) {
                selectAll();
            } else {
                selectNone();
            }
        });

        $bulkAssignItems.on('click', function (e) {
            e.preventDefault();
            const confirmation = e.target.closest('.bulk-assign-items').getAttribute('data-dialog-confirm')

            // check for changed values, show confirm dialog if there are
            const tableForm = e.target.closest('form')
            const allocationInputs = tableForm.querySelectorAll('input.analysis-table__subcomponent-allocate-input')
            const unsavedChanges = Array.from(allocationInputs).filter((input) => input.hasAttribute('data-changed')).length
            if (confirmation && unsavedChanges) {
                if (!confirm(confirmation)) {
                    e.stopPropagation();
                    return;
                }    
            }
            assignCheckedItems();
        });

        $bulkCheckboxes.on('change', function () {
            if (getCheckedConfigIds().length == 0) {
                $bulkAssignItems.prop('disabled', true);
            } else {
                $bulkAssignItems.prop('disabled', false);
            }
        });

        // Only enable the bulk checkbox once the page is done fully loading.
        $selectAllCheckbox.prop('disabled', false);

        function selectAll() {
            $bulkCheckboxes.prop('checked', true);
            $bulkCheckboxes.trigger('change');
        }

        function selectNone() {
            $bulkCheckboxes.prop('checked', false);
            $bulkCheckboxes.trigger('change');
        }

        function assignCheckedItems() {
            var configIds = getCheckedConfigIds();
            var queryString = '?config_ids=' + configIds.join(',');
            var url = bulkUrl + queryString;

            $(window).off('beforeunload');
                        Panels.open(url).then(function () {
                window.location = window.location.href;
            });
        }

        function getCheckedConfigIds() {
            return $bulkCheckboxes
              .filter(':checked')
              .toArray()
              .map(function (checkboxEl) {
                  return parseInt(checkboxEl.value, 10);
              })
        }


    }
})

$(function() {
    $('button[data-transactions-href]').on('click', function(e) {
        var $button = $(e.currentTarget);
        if (!$button.hasClass('transactions-loaded')) {
            $button.addClass('transactions-loaded');
            var href = $button.data('transactions-href');
            $.get(href).then(function(transactionRows) {
                var targetSelector = $button.data('transactions-target');
                $(targetSelector).html(transactionRows);
            });
        }
    });
});

function setupFilterListForm($filterList) {

  var $form = $filterList.find('.filter-list-form');
  var $addFilterDropdown = $form.find('.add-filter-dropdown');
  var $dropdownMenuItems = $addFilterDropdown.find('.dropdown-menu-items');
  var $filterResults = $form.find('.filter-results');
  var $clearAll = $form.find('a.clear-all');
  var $clearSearchPhrase = $form.find('.clear-search-phrase');
  var loadedFormData = $form.serialize();

  // Wire up dropdown items to show filter form elements.
  $form.find('[data-filter-target]').click(function(e) {
    e.preventDefault();
    e.stopPropagation();
    var filterName = $(e.target).attr('data-filter-target');
    showFilterInDropdown(filterName);
  });

  $form.find('[name="order_by"]').on('change', submitForm);

  // Prevent clicks in dropdown content from closing the dropdown.
  $form
    .find('.dropdown-menu')
    .on('click.bs.dropdown.data-api', function (e) { e.stopPropagation() });

  // Reset the dropdown to the filter list when the dropdown closes.
  $addFilterDropdown.on('hidden.bs.dropdown', resetFilterDropdown);

  // When the search input’s clear affordance is clicked, empty its value and
  // submit the filter form.
  $clearSearchPhrase.on('click', function(e) {
    e.preventDefault();
    $form.find('[name="search"]').val('');
    submitForm();
  });

  // Initialize filter results.
  $form
    .find('[data-filter]')
    .each(function(i, filterEl) { initFilter(filterEl); });

  // Hide the filter dropdown if there are no filters left to add.
  if (!$dropdownMenuItems.find('li:not(.hidden)').length) {
    $addFilterDropdown.hide();
  }

  if ($filterResults.find('.filter-result').length) {
    $clearAll.removeClass('hidden');
    $form.addClass('filter-list-form-active');
  }

  $form.on('submit', function() {
    // If the form hasen't changed it won't actually make a request if the
    // action is `#` so only show the filtering wheel if something actually
    // changed.
    var currentFormData = $form.serialize();
    if (currentFormData !== loadedFormData) {
      setFiltering();
    }
  });
  $filterList.find('.pagination a').on('click', setFiltering);

  $filterResults.find('a.clear-filter').on('click', function(e) {
    e.preventDefault();
    var filterName = $(e.target).attr('data-filter-name');
    var filterValue = $(e.target).attr('data-filter-value')
    clearFilter(filterName, filterValue);
    submitForm();
  });

  $clearAll.on('click', function(e) {
    e.preventDefault();
    clearAllFilters();
    submitForm();
  });


  function clearAllFilters() {
    $filterResults
      .find('.filter-result')
      .map(function(i, el) {
        var $result = $(el);
        var filterName = $result.find('[data-filter-name]').attr('data-filter-name');
        var filterValue = $result.find('[data-filter-value]').attr('data-filter-value');
        clearFilter(filterName, filterValue);
      });
    $form.find('[name="search"]').val('');
    submitForm();
  }

  function showFilterInDropdown(filterName) {
    $dropdownMenuItems.addClass('hidden');
    $form
      .find('[data-filter="' + filterName + '"]')
      .removeClass('hidden');
  }

  function resetFilterDropdown() {
    $dropdownMenuItems.removeClass('hidden');
    $form
      .find('.add-filter-dropdown')
      .find('[data-filter]')
      .addClass('hidden');
  }

  function clearFilter(filterName, filterValue) {
    $filterResults
      .find('[data-filter-name="' + filterName + '"][data-filter-value="' + filterValue+ '"]')
      .parents('.filter-result')
      .remove();

    var $filter = $form.find('[data-filter="' + filterName + '"]');

    // Select
    if ($filter.find('select').length > 0) {
      $filter.find('select').val('');
    }
    // Checkboxes, Radios.
    else if ($filter.find(':input[value="' + filterValue + '"]')) {
      var $input = $filter.find(':input[value="' + filterValue + '"]');
      if ($input.is(':checked')) {
        $input.removeAttr('checked');
      }
      else {
        $input.val('');
      }
    }
    // Text Fields.
    else {
      $filter.find(':input').val('');
    }

    if (!$filterResults.find('.filter-result').length) {
      $clearAll.hide();
    }
  }

  /**
   * If the filter has a value, it is added to the filter results and the item
   * in the dropdown is hidden.
   */
  function initFilter(filterEl) {
    var $el = $(filterEl);
    var $input = $el.find(':input');
    var inputType = $input.prop('type');

    if (inputType === 'select-one') {
      var val = $input.val();

      if (val) {
        var displayVal = $input.find('[value="' + val + '"]').text();
        var label = $el.find('label').text();
        addResult(label, val, displayVal, $input.attr('name'));
        hideDropdownMenuItem($el.attr('data-filter'));
      }
      else {
        $input.on('change', submitForm);
      }
    }
    else if (inputType === 'checkbox') {

        $el.find(':checked').each(function(i, checkbox) {
          var $checkbox = $(checkbox);
          var label = $checkbox.parents('[data-filter]').find('.control-label').text()
          var val = $checkbox.val();
          var displayVal = $checkbox.parents('label').text();
          var name = $checkbox.attr('name');
          addResult(label, val, displayVal, name);
        });

    }
    else if (inputType == 'radio') {

      var $radioChecked = $el.find(':checked');
      var val = $radioChecked.val();

      if (val) {
        var displayVal = $radioChecked.next().text();
        var label = $radioChecked[0].name;
        addResult(label, val, displayVal, $input.attr('name'));
        hideDropdownMenuItem($el.attr('data-filter'));
      }

      $input.on('change', submitForm);

    }
    else if ($input.attr('data-flatpickr') != undefined) {
      var val = $input.first().val();
      if (val) {
        var date = new Date(val);
        var displayVal = flatpickr.formatDate(date, 'M J, Y h:i K');
        var label = $el.find('label').text();
        addResult(label, val, displayVal, $input.attr('name'));
        hideDropdownMenuItem($el.attr('data-filter'));
      }
    }

  }

  function hideDropdownMenuItem(name) {
      $dropdownMenuItems
        .find('[data-filter-target="' + name + '"]')
        .parents('li')
        .addClass('hidden');
  }

  function addResult(label, value, displayValue, name) {
    var html = filterResultHtml(label, value, displayValue, name);
    if ($filterResults.find('.filter-result').length > 0) {
      $filterResults.find('.filter-result').last().after(html);
    }
    else {
      $filterResults.prepend(html);
    }
  }

  function filterResultHtml(label, value, displayValue, name) {
    return [
      '<div class="filter-result">',
        '<div class="label">' + label + ':</div>',
        '<div class="value">' + displayValue + '</div>',
        '<a href="#" class="clear-filter close" data-filter-value="' + value + '" data-filter-name="' + name + '" title="Remove">×</a>',
      '</div>',
    ''].join('');
  }

  function submitForm() {
    $form.trigger('submit');
  }

  function setFiltering() {
    $filterList.addClass('filtering');
  }

  function inputHasValue($input) {
    return ($input.val() && $input.val().length);
  }

}


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

});
// Modals
$(function() {
  var KEYCODE_ESC = 27;

  // Keep focus in navigation
  // Adapted from https://github.com/udacity/ud891/blob/gh-pages/lesson2-focus/07-modals-and-keyboard-traps/solution/el.js

  // Find the modal and its overlay
  var modals = document.getElementsByClassName('help__modal');
  Array.prototype.forEach.call(modals, function(el, index, array){

    // Listen for and trap the keyboard
    el.addEventListener('keydown', trapTabKey);

    // Find all focusable children
    var focusableElementsString = 'a[href], area[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), iframe, object, embed, [tabindex="0"], [contenteditable]';
    var focusableElements = el.querySelectorAll(focusableElementsString);
    // Convert NodeList to Array
    focusableElements = Array.prototype.slice.call(focusableElements);

    var firstTabStop = focusableElements[0];
    var lastTabStop = focusableElements[focusableElements.length - 1];

    var helpButton = $(el).closest('.help').find('.help__button')[0];
    var helpClose = $(el).closest('.help').find('.help__close')[0];
    helpButton.addEventListener('click', openNavigation);
    helpClose.addEventListener('click', closeNavigation);

    function openNavigation() {
      $('.help').removeClass('help__modal--open');
      $(el).closest('.help').addClass('help__modal--open');
      $(el).closest('.help').find('.help__close')[0].focus();
      $('html').on('keyup.navigation', onlyKeyCode(KEYCODE_ESC, closeNavigation));
    }

    function closeNavigation() {
      $('.help__modal').closest('.help').removeClass('help__modal--open');  
      $('html').off('.navigation');
      helpButton.focus();
    }

    function trapTabKey(e) {
      // Check for TAB key press
      if (e.keyCode === 9) {

        // SHIFT + TAB
        if (e.shiftKey) {
          if (document.activeElement === firstTabStop) {
            e.preventDefault();
            lastTabStop.focus();
          }

        // TAB
        } else {
          if (document.activeElement === lastTabStop) {
            e.preventDefault();
            firstTabStop.focus();
          }
        }
      }
    }
  });

  function calculatePosition() {
    var position;
    var windowWidth;
    var leftPosition;

    $('.help').each(function(){
      position = $(this).offset();
      windowWidth = $(window).outerWidth();

      if ((position.left > (windowWidth / 2))) {
        $(this).addClass('help--right');
      }
      else {
        $(this).removeClass('help--right');
      }
    });
  }

  $(document).ready(function(){
    calculatePosition();
  });

  $(window).resize(function() {
    setTimeout(function(){ calculatePosition(); }, 200);
  }); 

  $('.analysis-table__category-toggle').on('click', function(e){
    calculatePosition();
  });
});

$(function() {
  $('.step-help__button').on('click', function(e){
    $(this).closest('.analysis').removeClass('analysis--guidance-collapsed');      
    $(this).attr('aria-expanded', 'true');
    $(this).closest('.step-help').find('.step-help__close').focus();      
  });

  $('.step-help__close').on('click', function(e){
    $(this).closest('.analysis').addClass('analysis--guidance-collapsed');   
    $(this).closest('.step-help').find('step-help__button').attr('aria-expanded', 'false');
    $(this).closest('.step-help').find('.step-help__button').focus();          
  });
});


$(function () {

  function stepGuideHelpState() {
    var cookieName = 'step_guidance_open'
    $('.step-help__button').on('click', function (evt) {
      setCookie(cookieName, 1, 365)
    });
    $('.step-help__close').on('click', function (evt) {
        setCookie(cookieName, 0, 365)
    });
  }

  stepGuideHelpState()

  function getCookie(name) {
    var v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
    return v ? v[2] : null;
  }

  function setCookie(name, value, days) {
    var d = new Date;
    d.setTime(d.getTime() + 24 * 60 * 60 * 1000 * days);
    document.cookie = name + "=" + value + ";path=/;expires=" + d.toGMTString();
  }

  function deleteCookie(name) {
    setCookie(name, '', -1);
  }
})



$(function() {

    function closeEditRow(rowElement) {
        rowElement.closest('.analysis-table__tbody').removeClass('analysis-table__tbody--edit-active')
          .find('.analysis-table__edit-row--active').removeClass('analysis-table__edit-row--active');
        rowElement.removeClass('analysis-table__edit-row--active');
    }

    function showSaveNext() {
        $('.analysis-table__category-footer-action').show();
        $('.analysis-table__actions').show();
    }

    $('.analysis-table__edit-row').each(function () {
        var $editRow = $(this)
        var $cancelButton = $editRow.find('button[value="cancel"]')
        var $saveButton = $editRow.find('button[value="save_cost_line_item_config"]')


        if ($editRow.hasClass('allocate-costs')) {
            var $noteInput = $editRow.find('textarea[name="note"]');
            $saveButton.on('click', function (evt) {
                $(window).off('beforeunload');
                $saveButton.attr('disabled', true)
                evt.preventDefault();

                var endpoint = $saveButton.data('endpoint')
                var noteContent = $noteInput.val()
                var pk = $saveButton.data('object-id')
                var crsf = $editRow.find('input[name="csrfmiddlewaretoken"]').val()
                var data = {
                        id: pk,
                        note: noteContent,
                }

                $.ajax({
                    type: "POST",
                    url: endpoint,
                    data: JSON.stringify(data),
                    contentType: 'application/json; charset=utf-8',
                    dataType: 'json',
                    headers: {
                        'X-CSRFToken': crsf
                    }
                }).then(function (r) {
                    $saveButton.attr('disabled', false)
                    closeEditRow($editRow)
                    var button = $editRow.closest('tbody').find('.analysis-table__edit-cell button').not('.help__button, .help__close');
                    if (noteContent) {
                        button.html('View note').addClass('analysis-table__category-edit--note-active');
                    } else {
                        button.html('Add note').removeClass('analysis-table__category-edit--note-active')
                    }
                    showSaveNext()

                }).fail(function (e) {
                    console.log(e)
                    $saveButton.attr('disabled', false)
                });
                return false
            })
        }

        if ($editRow.hasClass('confirm-categories')) {
            var $cost_typeInput = $editRow.find('select[name="cost_type_id"]');
            var $categoryInput = $editRow.find('select[name="category_id"]');
            $saveButton.on('click', function (evt) {
                evt.preventDefault();
                $saveButton.attr('disabled', true)

                var endpoint = $saveButton.data('endpoint')
                var initialCostType = parseInt($cost_typeInput.closest('form').data('initial-cost_type_id'))
                var initialCategory = parseInt($cost_typeInput.closest('form').data('initial-category_id'))
                var cost_type = parseInt($cost_typeInput.val())
                var category = parseInt($categoryInput.val())
                if (initialCategory === category && cost_type === initialCostType) {
                    $saveButton.attr('disabled', false)
                    closeEditRow($editRow)
                } else {
                    var pk = $saveButton.data('object-id');
                    var crsf = $editRow.find('input[name="csrfmiddlewaretoken"]').val()
                    var data = {
                        id: pk,
                        cost_type_id: cost_type,
                        category_id: category,
                    }
                    $.ajax({
                        type: "POST",
                        url: endpoint,
                        data: JSON.stringify(data),
                        contentType: 'application/json; charset=utf-8',
                        dataType: 'json',
                        headers: {
                            'X-CSRFToken': crsf
                        }
                    }).then(function (r) {
                        $saveButton.attr('disabled', false)
                        closeEditRow($editRow)
                        $editRow.closest('tbody').remove()
                    }).fail(function (e) {
                        console.log(e)
                        $saveButton.attr('disabled', false)
                    });
                }

                return false
            })
        }


        $cancelButton.on('click', function (evt) {
            evt.preventDefault();
            closeEditRow($editRow)
            showSaveNext()
            return false;
        })


    });

});

/* selected text on focus */
document.querySelectorAll('input.analysis-table__subcomponent-allocate-input, input.analysis-table__allocated-input').forEach((input) => {
  input.addEventListener('change', (e) => e.target.setAttribute('data-changed', true))
  input.addEventListener('focusin', (e) => e.target.select())
})

// auto resize frozen table rows whenever a table is activated
window.addEventListener('DOMContentLoaded', (e) => {
  document.querySelectorAll('.analysis-table__category-toggle')?.forEach((trigger) => {
    trigger.addEventListener('click', (evt) => {
      setTimeout(() => {// allow time for offsetHeight to update
        const frozenTable = evt.target.closest('.analysis-table__category')?.querySelector('.analysis-table__category-content--freeze-col');
        if (frozenTable) {
          resizeFrozenTableRows(frozenTable)
        }
      }, 200)
    })
  })
  document.querySelector('.analysis-table__category--unconfirmed')?.classList.add('analysis-table__category--active')
  document.querySelectorAll('.analysis-table__category-content--freeze-col')?.forEach((table) => {
    resizeFrozenTableRows(table)
  })
});

function resizeFrozenTableRows(table) {
  const active = table.closest('.analysis-table__category--active')
  table.querySelectorAll('td')?.forEach((cell) => {

    const row = cell.closest('tr')
    if (row && cell.offsetHeight > row.offsetHeight) {
      row.style.height = cell.offsetHeight + 'px'
    }
    const frozenCell = row.querySelector('td:first-child')
    if (!active) {
      frozenCell.style.height = null
      return
    }
    if (cell.offsetHeight > frozenCell.offsetHeight) {
      frozenCell.style.height = cell.offsetHeight + 'px'
    }
  })
}

/* Make tables mouse draggable */
const tableWrapperSelector = '.analysis-table__wrapper'
const tables = document.querySelectorAll(tableWrapperSelector);

const startDragging = (e) => {
  const tableWrapper = e.target.closest(tableWrapperSelector)
  tableWrapper.dataset.mouseDown = true;
  tableWrapper.dataset.startX = e.pageX - tableWrapper.offsetLeft;
  tableWrapper.dataset.scrollLeft = tableWrapper.scrollLeft;
}

const stopDragging = (e) => {
  const tableWrapper = e.target.closest(tableWrapperSelector)
  delete tableWrapper.dataset.mouseDown
}

const move = (e) => {
  const tableWrapper = e.target.closest(tableWrapperSelector)

  e.preventDefault();
  if(!tableWrapper.dataset.mouseDown) { return; }
  const x = e.pageX - tableWrapper.offsetLeft;
  const scroll = x - tableWrapper.dataset.startX;
  tableWrapper.scrollLeft = tableWrapper.dataset.scrollLeft - scroll;
}

tables.forEach(table => {
  // Add the event listeners
  table.addEventListener('mousemove', move, false);
  table.addEventListener('mousedown', startDragging, false);
  table.addEventListener('mouseup', stopDragging, false);
  table.addEventListener('mouseleave', stopDragging, false);
})
