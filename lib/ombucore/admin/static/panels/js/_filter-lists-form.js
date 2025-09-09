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
    var selector = '[data-filter-name="' + filterName + '"][data-filter-value="' + filterValue + '"]';
    $filterResults
      .find(selector)
      .parents('.filter-result')
      .remove();

    var $filter = $form.find('[data-filter="' + filterName + '"]');


    var isFlatpickr = $filter.find('select').closest('.form-group').find('.flatpickr-calendar').length
    // Select
    if ($filter.find('select').length > 0 && !isFlatpickr) {
      $filter.find('select').val('');
    }
    // Checkboxes, Radios.
    else if ($filter.find(':input[value="' + filterValue + '"]') && !isFlatpickr) {
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
        '<div class="label">' + label + '</div>',
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
