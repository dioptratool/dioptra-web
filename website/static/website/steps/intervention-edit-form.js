$(function() {
    var $intervention = $('[name="intervention"]');
    var mapping = $intervention.data('mapping');
    var $changeWarning = $('.js-intervention-change-warning');
    var iovFields = ['Conditional Cash Transfer', 'Providing Business Grants', 'Unconditional Cash Transfer']

    $intervention
        .on('change', interventionChanged)
        .trigger('change');


    function hideAllParameters() {
        $('[name^="parameter"]')
            .parents('.form-group')
            .addClass('hidden')
            .removeAttr('required')
            .removeAttr('style');
    }

    function hideOutputCountSource() {
        $('[name="output_count_source"]')
            .parents('.form-group')
            .addClass('hidden');
    }

    function interventionChanged() {
        var interventionID = $intervention.val();
        if ($changeWarning.length) {
            // Compare against the instance's saved intervention (data-initial),
            // not the first rendered value, so the warning survives form
            // re-renders after validation errors.
            $changeWarning.toggleClass('hidden', String(interventionID) === String($changeWarning.data('initial')));
        }
        hideAllParameters();
        hideOutputCountSource();
        if (interventionID) {
            // retrieve lists of parameters grouped by intervention and output metric
            const metrics = mapping[interventionID]
            let allParams = []
            let order = 1
            metrics.forEach((parameters) => {
                parameters.forEach((param) => {
                    if (allParams.indexOf(param) < 0) {
                        allParams = allParams.concat(param)
                    }
                    // set parameter field order
                    const field = document.querySelector('[name="parameter__' + param + '"]')
                    field?.closest('.form-group')?.setAttribute('style', `order: ${order++};`)
                })
            })
            
            let required = []
            // Set first output metric as required
            required = required.concat(metrics[0])

            allParams.forEach((parameter) => {
                const field = document.querySelector('[name="parameter__' + parameter + '"]');
                let asterisk = field?.closest('.form-group')?.querySelector('label > em');
                // create required asterisk if missing
                if (!asterisk) {
                    const asteriskMarkup = '<em><sup title="This is a required field">*</sup></em>'
                    const label = field?.closest('.form-group')?.querySelector('label')
                    label.innerHTML += asteriskMarkup
                    asterisk = label.querySelector('em')
                }
                if (required.includes(parameter)) {
                    field?.setAttribute('required', true);
                    asterisk?.classList.remove('hidden');
                } else {
                    field?.removeAttribute('required');
                    asterisk?.classList.add('hidden');
                }
                field?.closest('.form-group')?.classList.remove('hidden');
            });

            // show output count source field if intervention is not IOV
            if ($.inArray($('[name="intervention"] option:selected').text(), iovFields) === -1) {
                $('[name="output_count_source"]')
                .parents('.form-group')
                .removeClass('hidden');
            }
        }
    }
});