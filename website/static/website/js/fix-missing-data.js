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
