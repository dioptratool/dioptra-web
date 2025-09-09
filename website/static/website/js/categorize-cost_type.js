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
