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
