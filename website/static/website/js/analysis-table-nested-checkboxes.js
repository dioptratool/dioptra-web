;(function ($) {
  function getTbody($el) {
    return $el.closest('tbody.analysis-table__tbody');
  }

  function getParentCheckbox($tbody) {
    return $tbody.find('> tr:first-child input.bulk-checkbox');
  }

  function getTransactionCheckboxes($tbody) {
    return $tbody.find('input.transaction-checkbox');
  }

  function updateParentState($tbody) {
    var $parent = getParentCheckbox($tbody);
    var $transactions = getTransactionCheckboxes($tbody);

    if (!$parent.length || !$transactions.length) {
      return;
    }

    var checkedCount = $transactions.filter(':checked').length;
    var total = $transactions.length;

    if (checkedCount === 0) {
      $parent.prop({ checked: false, indeterminate: false });
    } else if (checkedCount === total) {
      $parent.prop({ checked: true, indeterminate: false });
    } else {
      $parent.prop({ checked: false, indeterminate: true });
    }
  }

  function syncChildrenToParent($tbody) {
    var $parent = getParentCheckbox($tbody);
    var $transactions = getTransactionCheckboxes($tbody);

    if (!$parent.length || !$transactions.length) {
      return;
    }

    if ($parent.prop('checked')) {
      $transactions.prop('checked', true);
      $parent.prop('indeterminate', false);
    } else if (!$parent.prop('indeterminate')) {
      $transactions.prop('checked', false);
    }
  }

  function getCheckedConfigIds($form) {
    return $form
      .find('input.bulk-checkbox:checked')
      .filter(function () {
        return !this.indeterminate;
      })
      .map(function () {
        return parseInt(this.value, 10);
      })
      .get();
  }

  function getCheckedTransactionIds($form) {
    return $form
      .find('input.transaction-checkbox:checked')
      .map(function () {
        return parseInt(this.value, 10);
      })
      .get();
  }

  function hasBulkSelection($form) {
    return getCheckedConfigIds($form).length > 0 || getCheckedTransactionIds($form).length > 0;
  }

  function buildBulkQueryString($form) {
    var params = [];
    var configIds = getCheckedConfigIds($form);
    var transactionIds = getCheckedTransactionIds($form);

    if (configIds.length) {
      params.push('config_ids=' + configIds.join(','));
    }
    if (transactionIds.length) {
      params.push('transaction_ids=' + transactionIds.join(','));
    }

    return params.length ? '?' + params.join('&') : '?';
  }

  function updateBulkAssignButton($form) {
    $form.find('button.bulk-assign-items').prop('disabled', !hasBulkSelection($form));
  }

  function initForm($form) {
    $form.off('.nestedCheckboxes');

    $form.on('change.nestedCheckboxes', 'input.bulk-checkbox', function () {
      var $tbody = getTbody($(this));
      syncChildrenToParent($tbody);
      updateBulkAssignButton($form);
    });

    $form.on('change.nestedCheckboxes', 'input.transaction-checkbox', function () {
      updateParentState(getTbody($(this)));
      updateBulkAssignButton($form);
    });
  }

  window.AnalysisTableNestedCheckboxes = {
    initForm: initForm,
    initLoadedTransactions: function ($tbody) {
      syncChildrenToParent($tbody);
      updateParentState($tbody);
      updateBulkAssignButton($tbody.closest('form'));
    },
    selectAllInForm: function ($form, checked) {
      $form.find('input.transaction-checkbox').prop('checked', checked);
      $form.find('input.bulk-checkbox').prop('indeterminate', false);
    },
    selectNoneInForm: function ($form) {
      window.AnalysisTableNestedCheckboxes.selectAllInForm($form, false);
    },
    getCheckedConfigIds: getCheckedConfigIds,
    getCheckedTransactionIds: getCheckedTransactionIds,
    hasBulkSelection: hasBulkSelection,
    buildBulkQueryString: buildBulkQueryString,
    updateBulkAssignButton: updateBulkAssignButton,
  };

  $(function () {
    $('form.categorize-cost_type-bulk-form, form.allocate-bulk-form, form#fix-missing-data').each(function () {
      initForm($(this));
    });
  });
})(jQuery);
