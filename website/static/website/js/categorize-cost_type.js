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
            updateBulkAssignButtonState();
        });

        $form.on('change.bulkAssign', 'input.transaction-checkbox', function () {
            updateBulkAssignButtonState();
        });

        // Only enable the bulk checkbox once the page is done fully loading.
        $selectAllCheckbox.prop('disabled', false);

        function selectAll() {
            $bulkCheckboxes.prop('checked', true);
            $bulkCheckboxes.prop('indeterminate', false);
            if (window.AnalysisTableNestedCheckboxes) {
                window.AnalysisTableNestedCheckboxes.selectAllInForm($form, true);
            }
            updateBulkAssignButtonState();
        }

        function selectNone() {
            $bulkCheckboxes.prop('checked', false);
            $bulkCheckboxes.prop('indeterminate', false);
            if (window.AnalysisTableNestedCheckboxes) {
                window.AnalysisTableNestedCheckboxes.selectNoneInForm($form);
            }
            updateBulkAssignButtonState();
        }

        function assignCheckedItems() {
            var queryString = window.AnalysisTableNestedCheckboxes
                ? window.AnalysisTableNestedCheckboxes.buildBulkQueryString($form)
                : '?config_ids=' + $bulkCheckboxes.filter(':checked').map(function () {
                    return parseInt(this.value, 10);
                }).get().join(',');
            var url = bulkUrl + queryString;

            $(window).off('beforeunload');
            Panels.open(url).then(function () {
                window.location = window.location.href;
            });
        }

        function updateBulkAssignButtonState() {
            if (window.AnalysisTableNestedCheckboxes) {
                window.AnalysisTableNestedCheckboxes.updateBulkAssignButton($form);
                return;
            }

            $bulkAssignItems.prop('disabled', $bulkCheckboxes.filter(':checked').length === 0);
        }
    }
})
