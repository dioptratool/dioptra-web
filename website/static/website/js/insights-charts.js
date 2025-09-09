$(function() {

    function initializeInsightsChart(canvas) {
        var ctx = canvas.getContext('2d');
        var $canvas = $(canvas);
        var data = $canvas.data('insights-chart-data');
        var numItems = data.length;
        var maxValue = data.reduce(function(highest, dataPoint) {
            return Math.max(highest, dataPoint.output_cost_all, dataPoint.output_cost_direct_only);
        }, 0);
        var myChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(pick('label')),
                datasets: [{
                    label: $canvas.data('direct-only-text'),
                    data: data.map(pick('output_cost_direct_only')),
                    backgroundColor: data.map(function(item) {
                        return item.highlight ? '#1b77d4' : '#9CC6F2';
                    }),
                    borderColor: new Array(numItems).fill('#FFFFFF'),
                    borderWidth:2,
                    barPercentage: 1.0,
                    categoryPercentage: 1.0,
                },
                {
                    label: $canvas.data('all-text'),
                    data: data.map(pick('output_cost_all')),
                    backgroundColor: data.map(function(item) {
                        return item.highlight ? '#46a458' : '#C1E8C8';
                    }),
                    borderColor: new Array(numItems).fill('#FFFFFF'),
                    borderWidth:2,
                    barPercentage: 1.0,
                    categoryPercentage: 1.0,
                }]
            },
            options: {
                indexAxis: 'y',
                maintainAspectRatio: false,
                defaultFontFamily: 'Arial',
                devicePixelRatio: 1.5,
                plugins: {
                    tooltip: {
                        enabled: false
                    },
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        stacked: false,
                        grid: {
                            display: false
                        },
                        ticks: {
                        // Include a dollar sign in the ticks
                            callback: function(value, index, values) {
                                return getDioptraCurrencySymbol() + value;
                                // return '$' + value;
                            },
                            maxTicksLimit: 2,
                            beginAtZero: true,
                            color: '#333',
                            font: {
                                size: 14
                            },
                        },
                        title: {
                            display: true,
                            text: $canvas.data('x-axis-label'),
                            color: '#333'
                        },
                        max: maxValue
                    },
                    y: {
                        ticks: {
                            beginAtZero: true,
                            color: '#333',
                            font: {
                                size: 13.5
                            },
                        },
                        stacked: true,
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }

    $('.insights-chart').each(function(i, canvas) {
        initializeInsightsChart(canvas);
    });
});

$(function() {
    if ($('.insightsPie').length) {
        document.querySelectorAll('.insightsPie')?.forEach((chart) => {

            var ctx = chart.getContext('2d');
            var data = JSON.parse(chart.dataset.pieChartData)
            var myChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    datasets: [{
                        data: data.map(pick('percent_of_total')),
                        backgroundColor: [
                            '#144678',
                            '#2379d1',
                            '#5ed2d9',
                            '#4aa35b',
                            '#ede46d'
                        ].slice(0, data.length),
                    }],
                    labels: data.map(pick('label')),
                },
                options: {
                    indexAxis: 'y',
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        x: {
                            beginAtZero: false,
                            grid: {
                                display: false
                            },
                            ticks: {
                                callback: function (value) {
                                    if (value % 1 === 0) {
                                        return value + "%";
                                    }
                                },
                                font: {
                                    size: 13
                                },
                            },
                            color: '#333',
                        },
                        y: {
                            grid: {
                                display: false
                            },
                            ticks: {
                            callback: function(value) {
                                let label = this.getLabelForValue(value);
                                return formatLabel(label, 50);
                            },
                            font: {
                                size: 13
                            },
                            color: '#333'
                            }
                        }
                    },
                    maintainAspectRatio: false,
                }
            });
            myChart.canvas.parentNode.style.height = (55 * data.length) + 'px';
        });
    }
});

/**
 * When a section of the efficiency progress bar is clicked, we must update its corresponding card with the correct
 * color, value, and metric type description
 *
 * The correct elements are found by using the outputMetric slug and matching to its corresponding HTML id's
 * Search id="{{ metric.output_metric_slug }}_..."
 */
$('.progress-bar').on('click', setProgressBar)
function setProgressBar(event) {
    const $this = $(this);
    const $barElement = $this.closest('.efficiency-bar-identifier');
    const $itemElement = $this.closest('.efficiency-item');

    const metricType = $this.data('metric-type');
    const outputMetric = $barElement.data('output-metric');

    const $directHelpElement = $(`#${outputMetric}_efficiency-item__direct-help`, $itemElement);
    const $inKindHelpElement = $(`#${outputMetric}_efficiency-item__in_kind-help`, $itemElement);
    const $totalHelpElement = $(`#${outputMetric}_efficiency-item__total-help`, $itemElement);
    const $dynamicCardElement = $(`#${outputMetric}_dynamic-efficiency-card`, $itemElement);

    // Close Help Icon (if it is open)
    $dynamicCardElement.find('.help__close-icon').click();

    if (metricType === 'direct') {
        // Change the associated card's color based on the metricType
        $dynamicCardElement.removeClass('progress-bar-percent-in_kind progress-bar-percent-total').addClass('progress-bar-percent-direct');

        // Change the associated card's help information based on the metricType
        $directHelpElement.show();
        $inKindHelpElement.hide();
        $totalHelpElement.hide();

        // Move the bar's associated caret/pointer
        $barElement.find('.progress-bar-percent-direct').removeClass('hide-caret');
        $barElement.find('.progress-bar-percent-in_kind').addClass('hide-caret');
        $barElement.find('.progress-bar-percent-total').addClass('hide-caret');
    } else if (metricType === 'in_kind') {
        // Change the associated card's color based on the metricType
        $dynamicCardElement.removeClass('progress-bar-percent-direct progress-bar-percent-total').addClass('progress-bar-percent-in_kind');

        // Change the associated card's help information based on the metricType
        $directHelpElement.hide();
        $inKindHelpElement.show();
        $totalHelpElement.hide();

        // Move the bar's associated caret/pointer
        $barElement.find('.progress-bar-percent-direct').addClass('hide-caret');
        $barElement.find('.progress-bar-percent-in_kind').removeClass('hide-caret');
        $barElement.find('.progress-bar-percent-total').addClass('hide-caret');
    } else {
        // Assumed to be metricType === 'total'

        // Change the associated card's color based on the metricType
        $dynamicCardElement.removeClass('progress-bar-percent-in_kind progress-bar-percent-direct').addClass('progress-bar-percent-total');

        // Change the associated card's help information based on the metricType
        $directHelpElement.hide();
        $inKindHelpElement.hide();
        $totalHelpElement.show();

        // Move the bar's associated caret/pointer
        $barElement.find('.progress-bar-percent-direct').addClass('hide-caret');
        $barElement.find('.progress-bar-percent-in_kind').addClass('hide-caret');
        $barElement.find('.progress-bar-percent-total').removeClass('hide-caret');
    }

    // Update the inner HTML of the cost and label elements of the associated card
    const cardData = $barElement.data('bar-chart-data')[metricType];
    const $dynamicCardValueElement = $(`#${outputMetric}_efficiency-item__cost`, $itemElement);
    const $dynamicCardLabelElement = $(`#${outputMetric}_efficiency-item__group-label`, $itemElement);
    $dynamicCardValueElement.html(cardData.aggregate);
    $dynamicCardLabelElement.html(cardData.label);
}


/**
 * This function created the efficiency progress bar by sizing each section based on its percent of the total cost
 * data is initially populated in `_get_bar_chart_data` in website/views/analysis.py
 */
function initProgressBar() {
    const barElements = $('.efficiency-bar-identifier');
    barElements.each(function() {
        const valueShift = 16; // in px
        const $this = $(this);
        const data = $this.data('bar-chart-data');
        for (const [key, valuesObj] of Object.entries(data)) {
            // Fill in width and percent values
            const $valueElement = $this.find(`.progress-bar-value-${key}`);
            const $percentElement = $this.find(`.progress-bar-percent-${key}`);
            const elemWidth = $valueElement.width() ? $valueElement.width() : 32
            $valueElement.css('left', `${valueShift}px`);
            $valueElement.html(valuesObj.value);
            const minRequiredWidth = elemWidth + (2 * valueShift);  // Add valueShift left/right values
            $percentElement.css('width', `${valuesObj.percent}%`);
            $percentElement.css('min-width', `${minRequiredWidth}px`);
        }
    });
}
initProgressBar();

if (!Array.prototype.fill) {
  Object.defineProperty(Array.prototype, 'fill', {
    value: function(value) {

      // Steps 1-2.
      if (this == null) {
        throw new TypeError('this is null or not defined');
      }

      var O = Object(this);

      // Steps 3-5.
      var len = O.length >>> 0;

      // Steps 6-7.
      var start = arguments[1];
      var relativeStart = start >> 0;

      // Step 8.
      var k = relativeStart < 0 ?
        Math.max(len + relativeStart, 0) :
        Math.min(relativeStart, len);

      // Steps 9-10.
      var end = arguments[2];
      var relativeEnd = end === undefined ?
        len : end >> 0;

      // Step 11.
      var final = relativeEnd < 0 ?
        Math.max(len + relativeEnd, 0) :
        Math.min(relativeEnd, len);

      // Step 12.
      while (k < final) {
        O[k] = value;
        k++;
      }

      // Step 13.
      return O;
    }
  });
}

function pick(key) {
  return function(obj) {
    if (obj.hasOwnProperty(key)) {
      return obj[key];
    }
    return undefined;
  }
}

function formatLabel(str, maxwidth){
    var sections = [];
    var words = str.split(" ");
    var temp = "";

    words.forEach(function(item, index){
        if(temp.length > 0)
        {
            var concat = temp + ' ' + item;

            if(concat.length > maxwidth){
                sections.push(temp);
                temp = "";
            }
            else{
                if(index === (words.length-1))
                {
                    sections.push(concat);
                    return;
                }
                else{
                    temp = concat;
                    return;
                }
            }
        }

        if(index === (words.length-1))
        {
            sections.push(item);
            return;
        }

        if(item.length < maxwidth) {
            temp = item;
        }
        else {
            sections.push(item);
        }

    });

    return sections;
}