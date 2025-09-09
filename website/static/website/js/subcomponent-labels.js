value_to_html_element_id = (str) => {
    // Takes a string and returns a modified string that follows HTML element
    // ID naming conventions.
    //
    // NOTE: The logic must match the logic in the value_to_html_element_id
    //       function found in website/utils/value_to_html_element_id.py
    return str.toLowerCase().replace(/([^a-zA-Z\d]+)/g, '-')
}

trigger_change = (el, revert = false) => {
    // find the containing .form-group and put a bird on it
    const $formgroup = $(el).closest('.form-group')

    if ($formgroup.length == 0)
        return

    if (!revert)
        $formgroup.addClass('changed').trigger('panel:inputchanged')
    else
        $formgroup.removeClass('changed').trigger('panel:inputchanged')
}

arraysEqual = (a, b) => {
    if (a === b) return true
    if (a == null || b == null) return false
    if (a.length !== b.length) return false

    for (var i = 0; i < a.length; ++i) {
        if (a[i] !== b[i]) return false
    }
    return true
}


const renderResult = (objInfo, preventAddRemove = false) => {
    var html = []
    var klass = 'panels-relation-widget--result'
    let prevent_add_remove = preventAddRemove

    if (objInfo.hasOwnProperty('image_url')) klass += ' has-image'
    if (objInfo.hasOwnProperty('level')) klass += ' mptt-level-'.concat(objInfo.level)
    if (objInfo.hasOwnProperty('parent_id')) klass += ' mptt-parent-'.concat(objInfo.parent_id)

    html.push(`
        <li class="${klass}" data-id="${objInfo.label}" data-ctype-id="${objInfo.ctype_id}" 
        data-prevent-add-remove="${prevent_add_remove}">
        <span class="handle">☰</span>
    `)

    if (objInfo.hasOwnProperty('image_url')) {
        html.push(`<span class="image" style="background-image: url(${objInfo.image_url})"></span>`)
    }

    html.push(`
        <span class="verbose-name">${objInfo.verbose_name}</span>
        <span class="title" title="${objInfo.label}">${objInfo.label}</span>
        <span class="operations">
    `)

    if (objInfo.hasOwnProperty('change_url')) {
        html.push(`<a href="${objInfo.change_url}" class="operation-edit">Edit</a>`)
    }
    if (!preventAddRemove) {
        html.push(`<a href="#" class="operation-remove">Delete</a>`)
    }

    html.push(`</span></li>`)


    let $li = $(html.join(''))

    $li.data('obj-info', objInfo)

    const $remove_link = $li.find(`a.operation-remove`)
    const $edit_link = $li.find(`a.operation-edit`)

    $remove_link.on('click', (event) => {
        event.preventDefault()
        on_label_remove(event)
    })
    $edit_link.on('click', (event) => {
        event.preventDefault()
        on_label_edit(event)
    }
    )

    return $li
}

update_label = (el, result) => {
    if (!result.new_label) return

    const li = el.parent("span").parent("li")
    const objInfo = li.data("obj-info")
    const prevent_add_remove = li.data("prevent-add-remove")
    const $subcomponent_labels = $('#subcomponent_labels')
    const subcomponent_labels_json = JSON.parse($subcomponent_labels.val())
    const subcomponent_labels_old = JSON.parse($('#subcomponent_labels_old').val())
    subcomponent_labels_json[objInfo.label_idx] = result.new_label
    $subcomponent_labels.val(JSON.stringify(subcomponent_labels_json))
    const newObjInfo = {
        label: result.new_label,
        label_idx: objInfo.label_idx,
        change_url: `/subcomponents/label/change/${objInfo.label_idx}/${result.new_label}`
    }

    li.replaceWith(renderResult(newObjInfo, prevent_add_remove))

    trigger_change($('#subcomponent-label-type-fields'), arraysEqual(subcomponent_labels_json, subcomponent_labels_old))
}

on_label_edit = (event) => {
    // this opens a child Panel, and waits for the child Panel to call Panel.resolve()
    // which calls update_label() with the updated values
    const el = $(event.target)

    event.preventDefault()
    Panels.open(el.attr("href")).then((v) => update_label(el, v))
}

on_label_remove = (event) => {
    const el = $(event.target)
    const $parent = $(el).closest('li')
    const value = $parent.attr('data-id')
    const $subcomponent_labels = $('#subcomponent_labels')
    const subcomponent_labels_json = JSON.parse($subcomponent_labels.val())
    const subcomponent_labels_old = JSON.parse($('#subcomponent_labels_old').val())

    // Only needed when removing a subcomponent label that's been just added
    // and not yet saved.
    $parent.remove()

    // update the $subcomponent_labels input
    subcomponent_labels_json.splice(subcomponent_labels_json.indexOf(value), 1)
    $subcomponent_labels.val(JSON.stringify(subcomponent_labels_json))

    trigger_change($('#subcomponent-label-type-fields'), arraysEqual(subcomponent_labels_json, subcomponent_labels_old))
}

on_label_reorder = (el) => {
    const $results = $(el).find('.panels--reorder--results')
    const old_value = JSON.parse($('#subcomponent_labels_old').val())
    const new_value = JSON.parse($('#subcomponent_labels').val())
    const revert = arraysEqual(new_value, old_value)

    if (!revert) {
        $results.children('li').each(function (i, li) {
            let objInfo = $(li).data('obj-info')
            let prevent_add_remove = $(li).data('prevent-add-remove')


            objInfo.label_idx = i
            objInfo.change_url = `/subcomponents/label/change/${i}/${objInfo.label}`
            let $li = $(renderResult(objInfo, prevent_add_remove))
            $li.replaceWith($li)
        })
    }

    trigger_change($(el), revert)
}

on_add_label_link = (el) => {
    const $input = $('#add-label-input')
    const $link = $('#add-label-link')
    const $widget = $('#add-label-widget')

    $input.val('') // clear the text input
    $link.hide()
    $widget.show()
    $input.focus()
}

on_add_label_btn = (el) => {
    const $subcomponent_labels = $('#subcomponent_labels')
    const $subcomponent_labels_widget = $('#add-label-widget')
    const $subcomponent_labels_select = $('#subcomponent-labels-added')
    const subcomponent_labels_json = JSON.parse($('#subcomponent_labels').val())
    const subcomponent_labels_old = JSON.parse($('#subcomponent_labels_old').val())
    const $add_link = $('#add-label-link')
    const value = $('#add-label-input').val()
    const id_value = value_to_html_element_id(value)
    const prevent_add_remove = false // We are adding something here so this is inherently false

    const objInfo = {
        label: value,
        label_idx: subcomponent_labels_json.length,
        change_url: `/subcomponents/label/change/${subcomponent_labels_json.length}/${value}`
    }

    // update widget
    $subcomponent_labels_widget.hide()
    $subcomponent_labels_select.append(renderResult(objInfo, prevent_add_remove))

    // update the subcomponent-labels input
    subcomponent_labels_json.push(value)
    $subcomponent_labels.val(JSON.stringify(subcomponent_labels_json))

    $add_link.show()

    trigger_change($(el), arraysEqual(subcomponent_labels_old, subcomponent_labels_json))
}

on_cancel_add_label_btn = (el) => {
    const $widget = $('#add-label-widget')
    const $link = $('#add-label-link')

    $widget.hide()
    $link.show()
}

on_add_label_input_change = (el) => {
    const value = $('#add-label-input')
    const $button = $('#add-label-btn')

    $button.prop('disabled', value.length == 0)
}

setupPanelsReorder = ($el) => {
    const $results = $el.find('.panels--reorder--results')
    const $store = $el.parent().find('.panels--store')
    const sort = $el.hasClass("sortable")

    // upcast existing values
    $results.find('li').each(function (i, li) {
        let objInfo = $(li).data('obj-info')
        let prevent_add_remove = $(li).data('prevent-add-remove')
        let $li = renderResult(objInfo, prevent_add_remove)
        $(li).replaceWith($li)
    })

    Sortable.create($results[0], {
        sort: sort,
        handle: '.handle',
        store: {
            get: (sortable) => {
                const order = JSON.parse($store.val())
                return order ? order : []
            },
            set: (sortable) => {
                const order = sortable.toArray()
                $store.val(JSON.stringify(order))
                $el.trigger('change')
            }
        }
    })
}

// Event handlers
$(() => {
    $('.panels--reorder').each((i, el) => { setupPanelsReorder($(el)) })
    $('#subcomponent-labels-container').on('change', (event) => { on_label_reorder(event.target) })
    $('#add-label-link').on('click', (event) => { on_add_label_link(event.target) })
    $('#add-label-btn').on('click', (event) => { on_add_label_btn(event.target) })
    $('#add-label-input').on('input', (event) => { on_add_label_input_change(event.target) })
    $('#cancel-add-label-btn').on('click', (event) => { on_cancel_add_label_btn(event.target) })
})