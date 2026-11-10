function setupFilterListForm($filterList) {

  var $form = $filterList.find('.filter-list-form');
  var $addFilterDropdown = $form.find('.add-filter-dropdown');
  var $dropdownMenuItems = $addFilterDropdown.find('.dropdown-menu-items');
  var $filterResults = $form.find('.filter-results');
  var $clearAll = $form.find('a.clear-all');
  var $clearSearchPhrase = $form.find('.clear-search-phrase');
  var loadedFormData = $form.serialize();

  // Facets whose values are typed rather than picked (see data-filter-kind in _filters.html): one
  // result chip per facet, and clearing it empties every input of the facet.
  var TYPED_KINDS = ['text', 'range', 'date-range'];

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
    .on('click', function (e) { e.stopPropagation() });

  // Reset the dropdown to the filter list when the dropdown closes.
  $addFilterDropdown.on('hidden.dropdown', resetFilterDropdown);

  // When the search input’s clear affordance is clicked, empty its value and
  // submit the filter form.
  $clearSearchPhrase.on('click', function(e) {
    e.preventDefault();
    $form.find('[name="search"]').val('');
    submitForm();
  });

  orderNumberRanges();

  // Initialize filter results.
  $form
    .find('[data-filter]')
    .each(function(i, filterEl) { initFilter(filterEl); });

  // Hide the filter dropdown if there are no filters left to add.
  if (!$dropdownMenuItems.find('li.filter__menu-item:not(.hidden)').length) {
    $addFilterDropdown.hide();
  }

  if ($filterResults.find('.filter-result').length) {
    $clearAll.removeClass('hidden');
    $form.addClass('filter-list-form-active');
  }

  $form.on('submit', function() {
    orderNumberRanges();
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
    // Values are imported data (descriptions, custom field values), so compare attributes rather
    // than building a selector out of them.
    $filterResults
      .find('a.clear-filter')
      .filter(function() {
        return $(this).attr('data-filter-name') === filterName
          && $(this).attr('data-filter-value') === filterValue;
      })
      .closest('.filter-result')
      .remove();

    var $filter = facetFor(filterName);
    var kind = $filter.attr('data-filter-kind');

    if (TYPED_KINDS.indexOf(kind) !== -1) {
      namedInputs($filter).val('');
    }
    // Select
    else if ($filter.find('select').length > 0) {
      $filter.find('select').val('');
    }
    // Checkboxes, Radios: untick the one carrying this value.
    else {
      namedInputs($filter)
        .filter(function() { return this.value === filterValue; })
        .prop('checked', false);
    }

    if (!$filterResults.find('.filter-result').length) {
      $clearAll.hide();
    }
  }

  function facetFor(filterName) {
    return $form
      .find('[data-filter]')
      .filter(function() { return $(this).attr('data-filter') === filterName; });
  }

  // The facet's own inputs. A date picker adds unnamed inputs (month, year) inside the facet.
  function namedInputs($facet) {
    return $facet.find(':input[name]');
  }

  // "1234.5" -> "$1,234.50", in the en-US style the cost tables use. Anything that isn't a
  // number is shown as typed.
  function currencyText(value, symbol) {
    var number = Number(value);
    if (value === '' || !isFinite(number)) {
      return value;
    }
    var formatted = Math.abs(number).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
    return (number < 0 ? '-' : '') + (symbol || '') + formatted;
  }

  // A number range entered backwards (To below From) is flipped before it is submitted, so the
  // inputs, the result chip and the URL all read low to high. The server flips it too.
  function orderNumberRanges() {
    $form.find('[data-filter-kind="range"]').each(function() {
      var $inputs = namedInputs($(this));
      var $from = $inputs.eq(0);
      var $to = $inputs.eq(1);
      var from = ($from.val() || '').trim();
      var to = ($to.val() || '').trim();
      if (from !== '' && to !== '' && Number(to) < Number(from)) {
        $from.val(to);
        $to.val(from);
      }
    });
  }

  function rangeText(from, to) {
    if (from && to) {
      return from + ' \u2013 ' + to;
    }
    return from ? 'from ' + from : 'to ' + to;
  }

  // Number ranges read as an inclusive comparison.
  function numberRangeText(from, to) {
    if (from && to) {
      return from + ' \u2013 ' + to;
    }
    return from ? 'At least ' + from : 'At most ' + to;
  }

  /**
   * If the filter has a value, it is added to the filter results and the item
   * in the dropdown is hidden.
   */
  function initFilter(filterEl) {
    var $el = $(filterEl);
    var name = $el.attr('data-filter');
    var kind = $el.attr('data-filter-kind');
    var $inputs = namedInputs($el);
    var $input = $inputs.first();
    var inputType = $input.prop('type');

    if (kind === 'text') {
      var text = ($input.val() || '').trim();
      if (text) {
        addResult($el.find('.control-label').text().trim(), text, text, name);
        hideDropdownMenuItem(name);
      }
    }
    else if (kind === 'range' || kind === 'date-range') {
      var from = ($inputs.eq(0).val() || '').trim();
      var to = ($inputs.eq(1).val() || '').trim();
      if (from || to) {
        var symbol = $inputs.eq(0).attr('data-currency-symbol');
        var rangeLabel;
        if (kind === 'range') {
          rangeLabel = numberRangeText(from && currencyText(from, symbol), to && currencyText(to, symbol));
        }
        else {
          rangeLabel = rangeText(from, to);
        }
        // One chip for the facet; its value is the facet name, so clearing it empties both inputs.
        addResult($el.find('.control-label').text().trim(), name, rangeLabel, name);
        hideDropdownMenuItem(name);
      }
    }
    else if (inputType === 'select-one') {
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
      let val = $radioChecked.val();

      if (val) {
        let displayVal = $radioChecked.next().text();
        let label = $radioChecked[0].name;
        addResult(label, val, displayVal, $input.attr('name'));
        hideDropdownMenuItem($el.attr('data-filter'));
      }

      $input.on('change', submitForm);

    }
    else if ($input.attr('data-flatpickr') != undefined) {
      let val = $input.first().val();
      if (val) {
        var date = new Date(val);
        let displayVal = flatpickr.formatDate(date, 'M J, Y h:i K');
        let label = $el.find('label').text();
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
    var $result = filterResultHtml(label, value, displayValue, name);
    if ($filterResults.find('.filter-result').length > 0) {
      $filterResults.find('.filter-result').last().after($result);
    }
    else {
      $filterResults.prepend($result);
    }
  }

  function filterResultHtml(label, value, displayValue, name) {
    // Built with .text() and .attr(): the values are imported data.
    var $result = $('<div class="filter-result"></div>');
    $('<div class="label"></div>').text(label + ':').appendTo($result);
    $('<div class="value"></div>').text(displayValue).appendTo($result);
    $('<a href="#" class="clear-filter close" title="Remove">\u00d7</a>')
      .attr('data-filter-value', value)
      .attr('data-filter-name', name)
      .appendTo($result);
    return $result;
  }

  function submitForm() {
    $form.trigger('submit');
  }

  function setFiltering() {
    $filterList.addClass('filtering');
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