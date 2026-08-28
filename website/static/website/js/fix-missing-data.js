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
            $bulkCheckboxes.trigger('change');
            if (window.AnalysisTableNestedCheckboxes) {
                window.AnalysisTableNestedCheckboxes.selectAllInForm($form, true);
            }
            updateBulkAssignButtonState();
        }

        function selectNone() {
            $bulkCheckboxes.prop('checked', false);
            $bulkCheckboxes.prop('indeterminate', false);
            $bulkCheckboxes.trigger('change');
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
            Panels.open(url).then(function() {
                window.location.reload();
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

});
