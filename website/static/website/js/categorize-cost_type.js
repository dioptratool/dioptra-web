$(function() {

    $('form.categorize-cost_type-bulk-form').each(function () {
        setupBulkForm($(this))
    });


    function setupBulkForm($form) {
        var $selectAllCheckbox = $form.find('input[type="checkbox"].select-all');
        var $bulkCheckboxes = $form.find('input[type="checkbox"].bulk-checkbox');

        $selectAllCheckbox.on('change', function () {
            if ($selectAllCheckbox.prop('checked')) {
                selectAll();
            } else {
                selectNone();
            }
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

        function updateBulkAssignButtonState() {
            if (window.AnalysisTableNestedCheckboxes) {
                window.AnalysisTableNestedCheckboxes.updateBulkAssignButton($form);
                return;
            }

            $form.find('button.correction-bulk-edit').prop('disabled', $bulkCheckboxes.filter(':checked').length === 0);
        }
    }
})
