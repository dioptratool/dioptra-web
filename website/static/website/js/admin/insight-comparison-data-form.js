$(function() {
    var $intervention = $('[name="intervention"]');
    var interventionParameterMapping = $intervention.data('intervention-parameter-mapping');
    var interventionOutputMetricMapping = $intervention.data('intervention-output-metric-mapping');

    $intervention
        .on('change', interventionChanged)
        .trigger('change');

    function hideAllParameters() {
        $('[name^="parameter"]')
            .parents('.form-group')
            .addClass('hidden');
    }

    function hideOutputMetricCosts() {
        $('[name^="output_cost"]')
            .parents('.form-group')
            .addClass('hidden');
    }

    function interventionChanged() {
        var intervention = $intervention.val();
        hideAllParameters();
        hideOutputMetricCosts();
        if (intervention) {
            // Flatten the parameters array
            var parameters = (interventionParameterMapping[intervention] || []).reduce(function(acc, arr) {
                return acc.concat(arr);
            }, []);

            var outputMetricCosts = interventionOutputMetricMapping[intervention];
            var selectors = [];

            selectors = parameters.reduce(function(acc, parameterName) {
                acc.push('[name="parameter__' + parameterName + '"]');
                return acc;
            }, selectors);

            selectors = outputMetricCosts.reduce(function(acc, outputMetricName) {
                acc.push('[name="output_cost__all__' + outputMetricName + '"]');
                acc.push('[name="output_cost__direct_only__' + outputMetricName + '"]');
                return acc
            }, selectors);

            var $inputs = $(selectors.join(', '));
            $inputs.parents('.form-group').removeClass('hidden');
        }
    }
});
