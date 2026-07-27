$(function() {
    $('.manage-interventions').on('click', function(e) {
        e.preventDefault();
        var reload = function() { window.location.reload(); };
        // Child panels opened from the changelist don't propagate their saves
        // to this page, so reload whenever the panel closes.
        Panels.open($(this).data('href')).then(reload, reload);
    });
});
