$(function() {

    function closeEditRow(rowElement) {
        rowElement.closest('.analysis-table__tbody').removeClass('analysis-table__tbody--edit-active')
          .find('.analysis-table__edit-row--active').removeClass('analysis-table__edit-row--active');
        rowElement.removeClass('analysis-table__edit-row--active');
    }

    function showSaveNext() {
        $('.analysis-table__category-footer-action').show();
        $('.analysis-table__actions').show();
    }

    $('.analysis-table__edit-row').each(function () {
        var $editRow = $(this)
        var $cancelButton = $editRow.find('button[value="cancel"]')
        var $saveButton = $editRow.find('button[value="save_cost_line_item_config"]')


        if ($editRow.hasClass('allocate-costs')) {
            var $noteInput = $editRow.find('textarea[name="note"]');
            $saveButton.on('click', function (evt) {
                $(window).off('beforeunload');
                $saveButton.attr('disabled', true)
                evt.preventDefault();

                var endpoint = $saveButton.data('endpoint')
                var noteContent = $noteInput.val()
                var pk = $saveButton.data('object-id')
                var crsf = $editRow.find('input[name="csrfmiddlewaretoken"]').val()
                var data = {
                        id: pk,
                        note: noteContent,
                }

                $.ajax({
                    type: "POST",
                    url: endpoint,
                    data: JSON.stringify(data),
                    contentType: 'application/json; charset=utf-8',
                    dataType: 'json',
                    headers: {
                        'X-CSRFToken': crsf
                    }
                }).then(function (r) {
                    $saveButton.attr('disabled', false)
                    closeEditRow($editRow)
                    var button = $editRow.closest('tbody').find('.analysis-table__edit-cell button').not('.help__button, .help__close');
                    if (noteContent) {
                        button.html('View note').addClass('analysis-table__category-edit--note-active');
                    } else {
                        button.html('Add note').removeClass('analysis-table__category-edit--note-active')
                    }
                    showSaveNext()

                }).fail(function (e) {
                    console.log(e)
                    $saveButton.attr('disabled', false)
                });
                return false
            })
        }

        if ($editRow.hasClass('confirm-categories')) {
            var $cost_typeInput = $editRow.find('select[name="cost_type_id"]');
            var $categoryInput = $editRow.find('select[name="category_id"]');
            $saveButton.on('click', function (evt) {
                evt.preventDefault();
                $saveButton.attr('disabled', true)

                var endpoint = $saveButton.data('endpoint')
                var initialCostType = parseInt($cost_typeInput.closest('form').data('initial-cost_type_id'))
                var initialCategory = parseInt($cost_typeInput.closest('form').data('initial-category_id'))
                var cost_type = parseInt($cost_typeInput.val())
                var category = parseInt($categoryInput.val())
                if (initialCategory === category && cost_type === initialCostType) {
                    $saveButton.attr('disabled', false)
                    closeEditRow($editRow)
                } else {
                    var pk = $saveButton.data('object-id');
                    var crsf = $editRow.find('input[name="csrfmiddlewaretoken"]').val()
                    var data = {
                        id: pk,
                        cost_type_id: cost_type,
                        category_id: category,
                    }
                    $.ajax({
                        type: "POST",
                        url: endpoint,
                        data: JSON.stringify(data),
                        contentType: 'application/json; charset=utf-8',
                        dataType: 'json',
                        headers: {
                            'X-CSRFToken': crsf
                        }
                    }).then(function (r) {
                        $saveButton.attr('disabled', false)
                        closeEditRow($editRow)
                        $editRow.closest('tbody').remove()
                    }).fail(function (e) {
                        console.log(e)
                        $saveButton.attr('disabled', false)
                    });
                }

                return false
            })
        }


        $cancelButton.on('click', function (evt) {
            evt.preventDefault();
            closeEditRow($editRow)
            showSaveNext()
            return false;
        })


    });

});
