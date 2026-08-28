$(function() {
    $('button[data-transactions-href]').on('click', function(e) {
        var $button = $(e.currentTarget);
        if (!$button.hasClass('transactions-loaded')) {
            $button.addClass('transactions-loaded');
            var href = $button.data('transactions-href');
            var $tbody = $button.closest('tbody.analysis-table__tbody');
            $.get(href).then(function(transactionRows) {
                var targetSelector = $button.data('transactions-target');
                var $target = $(targetSelector);
                $target.html(transactionRows);
                if (window.AnalysisTableNestedCheckboxes && $tbody.length) {
                    window.AnalysisTableNestedCheckboxes.initLoadedTransactions($tbody);
                }
            });
        }
    });
});
