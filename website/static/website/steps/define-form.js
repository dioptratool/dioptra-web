$(function() {
    var $interventionDataField = $('#id_intervention_data')
    var $setInterventionsButton = $('.set-interventions')

    $setInterventionsButton.on('click', function(e) {
        e.preventDefault();
        var interventionsUrl = $setInterventionsButton.attr('data-href');
        var interventions = $interventionDataField.val();
        setInterventions();

        function setInterventions() {
            var queryString = "?data=" + encodeURIComponent(interventions);
            var url = interventionsUrl + queryString;
            Panels.open(url).then(
                handleResponse, // Resolve.
                noop, // Reject.
                handleResponse // Progress.
            );        }
    });

    function handleResponse(response) {
        if ($interventionDataField.val() != response.value) {
            $interventionDataField.val(response.value)
            updateInterventionDisplay(response.value)
        }
    }
    function updateInterventionDisplay(data) {
        json_data = JSON.parse(data);
        const interventions = $('.analysis-interventions')
        interventions.empty();
        json_data.forEach(intervention => {
            interventions.append(renderResult(intervention))
        });

        $interventionDataField.closest('form').addClass('dirty')

        if (json_data.length == 0) {
            $setInterventionsButton.html('Add Interventions')
        } else {
            $setInterventionsButton.html('Manage Interventions')
        }
    }

    function renderResult(objInfo, addOnly) {
        addOnly = addOnly | false;
        var html = [];
        var klass = 'analysis-intervention';
      
        html.push('<li class="' + klass + '" data-id="' + objInfo.instance_pk + '">');
        html.push('<h4 class="intervention-title" title="' + objInfo.title + '">' + objInfo.title + '</h4>');
        html.push('<p class="intervention-subtitle">');
        html.push(objInfo.intervention_name + " / ");
        if (objInfo.params.length) {
          html.push(objInfo.params.map((p) => '<span class="parameter">' + p.label + ": " +  Number(p.value).toFixed(2) + '</span>').join(", "));
        }
        html.push('</p>');
        html.push('</li>');
      
        var $elem = $(html.join(''));
        $elem.data('obj-info', objInfo);
        return $elem;
    }
      
});
