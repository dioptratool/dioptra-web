/*
 * Sub-component label editor (analysis interventions and intervention-type defaults).
 *
 * Each list item is a component identified by a client-side key, never by its label text,
 * so duplicates, renames and reorders cannot confuse one component with another. Two hidden
 * inputs are kept in step: `subcomponent_labels` (the labels, in order) and
 * `subcomponent_sources` (for each label, the position it had in the saved list, or null
 * for a component added in this session). The server uses the sources to move saved
 * percentages along with their components.
 */
$(() => {
    const maxlabels = 8

    const $labels = $('#subcomponent_labels')
    const $sources = $('#subcomponent_sources')
    const $oldLabels = $('#subcomponent_labels_old')
    const $list = $('#subcomponent-labels-added')
    if (!$labels.length || !$list.length) return

    let nextKey = 0
    const components = [] // [{key, label, source}] in display order
    const byKey = (key) => components.find((component) => component.key === key)

    const arraysEqual = (a, b) => a.length === b.length && a.every((value, i) => value === b[i])

    const trigger_change = (el, revert = false) => {
        // find the containing .form-group and put a bird on it
        const $formgroup = $(el).closest('.form-group')
        if ($formgroup.length == 0) return
        if (!revert)
            $formgroup.addClass('changed').trigger('panel:inputchanged')
        else
            $formgroup.removeClass('changed').trigger('panel:inputchanged')
    }

    const editUrl = $('#subcomponent-labels-container').data('edit-url')
    const changeUrl = (component) => `${editUrl}?label=${encodeURIComponent(component.label)}`

    const write = () => {
        const labels = components.map((component) => component.label)
        const sources = components.map((component) => component.source)
        $labels.val(JSON.stringify(labels))
        $sources.val(JSON.stringify(sources))

        const oldLabels = JSON.parse($oldLabels.val() || '[]')
        const identity = oldLabels.map((_label, i) => i)
        const unchanged = arraysEqual(labels, oldLabels) && arraysEqual(sources, identity)
        trigger_change($('#subcomponent-label-type-fields'), unchanged)
    }

    const render = (component) => {
        const $li = $('<li>', {
            class: 'panels-relation-widget--result',
            'data-id': component.key,
        })
        $li.append($('<span>', { class: 'handle', text: '☰' }))
        $li.append($('<span>', { class: 'verbose-name' }))
        $li.append($('<span>', { class: 'title', title: component.label, text: component.label }))

        const $operations = $('<span>', { class: 'operations' })
        const $edit = $('<a>', { href: '#', class: 'operation-edit', text: 'Edit' })
        $edit.on('click', (event) => {
            event.preventDefault()
            on_label_edit(component)
        })
        $operations.append($edit)
        const $remove = $('<a>', { href: '#', class: 'operation-remove', text: 'Delete' })
        $remove.on('click', (event) => {
            event.preventDefault()
            on_label_remove(component)
        })
        $operations.append($remove)
        $li.append($operations)
        return $li
    }

    const itemFor = (component) => $list.children('li').filter((_i, li) => $(li).attr('data-id') === component.key)

    const on_label_edit = (component) => {
        // Opens a child panel and waits for it to call Panel.resolve() with the new label.
        Panels.open(changeUrl(component)).then((result) => {
            if (!result || !result.new_label) return
            component.label = result.new_label
            itemFor(component).replaceWith(render(component))
            write()
        })
    }

    const on_label_remove = (component) => {
        itemFor(component).remove()
        components.splice(components.indexOf(component), 1)
        if (components.length < maxlabels) $('#add-label-link').show()
        write()
    }

    const on_label_reorder = (sortable) => {
        const ordered = sortable.toArray().map(byKey).filter(Boolean)
        components.splice(0, components.length, ...ordered)
        write()
    }

    const on_add_label_link = () => {
        $('#add-label-input').val('')
        $('#add-label-link').hide()
        $('#add-label-widget').show()
        $('#add-label-input').focus()
    }

    const on_add_label_btn = () => {
        const value = $('#add-label-input').val().trim()
        if (!value.length || components.length >= maxlabels) return

        const component = { key: `c${nextKey++}`, label: value, source: null }
        components.push(component)
        $list.append(render(component))

        if (components.length >= maxlabels) {
            $('#add-label-widget').hide()
            $('#add-label-link').hide()
        } else {
            $('#add-label-input').val('').focus()
        }
        on_add_label_input_change()
        write()
    }

    const on_cancel_add_label_btn = () => {
        $('#add-label-widget').hide()
        $('#add-label-link').show()
    }

    const on_add_label_input_change = () => {
        $('#add-label-btn').prop('disabled', $('#add-label-input').val().trim().length == 0)
    }

    // Upcast the server-rendered items into components.
    $list.children('li').each((_i, li) => {
        const objInfo = $(li).data('obj-info') || {}
        const source = typeof objInfo.source === 'number' ? objInfo.source : null
        const component = { key: `c${nextKey++}`, label: objInfo.label, source: source }
        components.push(component)
        $(li).replaceWith(render(component))
    })
    write()

    const sortable = Sortable.create($list[0], {
        sort: true,
        handle: '.handle',
        onSort: () => on_label_reorder(sortable),
    })

    $('#add-label-link').on('click', (event) => { event.preventDefault(); on_add_label_link() })
    $('#add-label-btn').on('click', (event) => { event.preventDefault(); on_add_label_btn() })
    $('#add-label-input').on('input', on_add_label_input_change)
    $('#add-label-input').on('keydown', (event) => {
        if (event.key == 'Enter') {
            event.preventDefault()
            on_add_label_btn()
        }
    })
    $('#cancel-add-label-btn').on('click', (event) => { event.preventDefault(); on_cancel_add_label_btn() })
})
