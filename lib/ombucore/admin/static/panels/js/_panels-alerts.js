var PanelsAlerts = (function() {

    var isRoot = (window.parent === window);
    if (!isRoot && window.parent.PanelsAlerts) {
        return window.parent.PanelsAlerts;
    }

    var MESSAGE_TIMEOUT = 8 * 1000;
    var messages = [];
    var $panelsContainer;
    var $rootContainer;

    $(function() {
        $panelsContainer = $('<div id="panels-alerts-container"></div>');
        $panelsContainer.appendTo('body');
        $rootContainer = $('#root-alerts-container').length ? $('#root-alerts-container') : $panelsContainer;

        $panelsContainer.on('click', '.alert .close', alertCloseClick);
        if ($rootContainer.get(0) !== $panelsContainer.get(0)) {
          $rootContainer.on('click', '.alert .close', alertCloseClick);
        }
    });


    return {
        alert: openAlert
    }

    function openAlert(message, container, timeout) {
        var $container = (container == 'root') ? $rootContainer : $panelsContainer
        timeout = timeout || MESSAGE_TIMEOUT;
        var $alert = $(makeAlert(message));
        $container.prepend($alert);
        $container.addClass('open');
        $alert.addClass('in');
        setTimeout($.proxy(closeAlert, null, $alert), timeout);
    }

    function closeAlert($alert) {
        $alert.removeClass('in');
        var $container = $alert.parents('#panels-alerts-container, #root-alerts-container');
        setTimeout(function() {
            $alert.remove();
            if ($container.find('.alert').length == 0) {
                $container.removeClass('open');
            }
        }, 150);
    }

    function alertCloseClick(e) {
      e.preventDefault();
      var $alert = $(e.target).parents('.alert');
      closeAlert($alert);
    }

    function makeAlert(message) {
        var classes = ['alert', 'fade'];
        switch(message.level) {
            case 'error':
                classes.push('alert-danger');
                break;
            default:
                classes.push('alert-' + message.level);
                break;
        }

        if (message.extra_tags) {
            classes.push(message.extra_tags);
        }

        return [
            '<div class="' + classes.join(' ') + '">',
              '<div class="alert-inner">',
                '<button type="button" class="close" data-dismiss="alert" aria-label="Close"><span aria-hidden="true">&times;</span></button>',
                '<div class="alert-level">' + message.level.toUpperCase() + '</div>',
                message.message,
              '</div>',
            '</div>',
        ''].join('');
    }

})();
