/**
 * Intervention metadata editor.
 *
 * Parent (the intervention form's Metadata tab): keeps the definition draft in a hidden input,
 * renders the field list, reorders it with Sortable and opens a child panel per field. The child
 * returns the edited row through Panels.resolve; nothing is saved until the intervention is.
 *
 * Child (the field panel): the row to edit travels in the URL fragment (#draft=...), never in the
 * request; the controls are filled from it once, unless the server re-rendered a posted form.
 * Anything read from the fragment is untrusted: row text goes through escapeHtml and draft ids
 * are set as attributes through jQuery, never interpolated into markup.
 * Options are added, removed, reordered and renamed (through a nested panel) inline.
 */
(function () {
  'use strict';

  var MAX_OPTIONS = 10;
  var CHOICE_TYPES = ['multiple_choice', 'single_choice'];
  var TYPE_LABELS = {
    free_text: 'Free Text',
    multiple_choice: 'Multiple Choice',
    single_choice: 'Single Choice',
    number: 'Number'
  };
  var DELETE_FIELD_WARNING = 'Are you sure you want to delete this metadata field? All associated data within the analyses using this field will be deleted. This action cannot be undone.';
  var DELETE_OPTION_WARNING = 'Are you sure you want to delete this option? All analysis metadata fields with this option selected will have it removed. This action cannot be undone.';
  var TYPE_CHANGE_WARNING = 'Saving this intervention will discard existing values for this field.';

  function uid() {
    return Math.random().toString(16).slice(2) + Date.now().toString(16);
  }

  function escapeHtml(text) {
    return $('<span>').text(text == null ? '' : String(text)).html();
  }

  function fragmentDraft() {
    var raw = new URLSearchParams(window.location.hash.replace(/^#/, '')).get('draft');
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (error) { return null; }
  }

  function withDraft(url, draft) {
    return url + '#draft=' + encodeURIComponent(JSON.stringify(draft));
  }

  function sortByOrder(items, $list) {
    var order = $list.children().map(function (i, li) { return $(li).attr('data-draft-id'); }).get();
    items.sort(function (a, b) { return order.indexOf(a.draft_id) - order.indexOf(b.draft_id); });
  }

  // ---- parent editor -------------------------------------------------------------------------

  function setupEditor(root) {
    var $root = $(root);
    var $input = $root.find('.metadata-editor__draft');
    var $list = $root.find('.metadata-editor__list');
    var $add = $root.find('.metadata-editor__add');
    var fieldUrl = $root.attr('data-field-url');
    var maxFields = parseInt($root.attr('data-max-fields'), 10) || 20;
    var original = $input.attr('data-original');
    var state;
    try { state = JSON.parse($input.val()); } catch (error) { state = null; }
    if (!state || !Array.isArray(state.fields)) state = { fields: [] };

    function commit() {
      $input.val(JSON.stringify(state));
      render();
      var changed = JSON.stringify(state) !== original;
      $root.closest('.form-group').toggleClass('changed', changed).trigger('panel:inputchanged');
    }

    function render() {
      $list.empty();
      state.fields.forEach(function (field) {
        var $row = $(
          '<li class="metadata-editor__row">' +
            '<span class="metadata-editor__handle" aria-hidden="true">☰</span>' +
            '<span class="metadata-editor__type">' + escapeHtml(TYPE_LABELS[field.field_type] || '') + '</span>' +
            '<span class="metadata-editor__name">' + escapeHtml(field.name) + '</span>' +
            '<span class="metadata-editor__actions">' +
              '<a href="#" class="metadata-editor__edit">Edit</a>' +
              '<a href="#" class="metadata-editor__delete">Delete</a>' +
            '</span>' +
          '</li>'
        );
        $row.attr('data-draft-id', field.draft_id);
        $row.find('.metadata-editor__edit').on('click', function (event) { event.preventDefault(); openField(field); });
        $row.find('.metadata-editor__delete').on('click', function (event) { event.preventDefault(); removeField(field); });
        $list.append($row);
      });
      $add.toggle(state.fields.length < maxFields);
    }

    function openField(field) {
      Panels.open(withDraft(fieldUrl, field)).then(function (result) {
        if (!result || !result.row) return;
        var row = result.row;
        var index = state.fields.findIndex(function (existing) { return existing.draft_id === row.draft_id; });
        if (index >= 0) state.fields[index] = row; else state.fields.push(row);
        commit();
      });
    }

    function removeField(field) {
      if (field.in_use && !window.confirm(DELETE_FIELD_WARNING)) return;
      state.fields = state.fields.filter(function (existing) { return existing.draft_id !== field.draft_id; });
      commit();
    }

    $add.on('click', function (event) {
      event.preventDefault();
      openField({ draft_id: uid(), id: null, key: null, name: '', field_type: '', number_type: null, in_use: false, options: [] });
    });

    if (window.Sortable) {
      Sortable.create($list[0], {
        handle: '.metadata-editor__handle',
        onEnd: function () { sortByOrder(state.fields, $list); commit(); }
      });
    }

    render();
  }

  // ---- child panel ---------------------------------------------------------------------------

  function setupOptionLabelForm($form, bound) {
    var $label = $form.find('[name="label"]');
    var $save = $form.find('.metadata-field-form__save');
    if (!bound) {
      var draft = fragmentDraft();
      if (draft && typeof draft.label === 'string') $label.val(draft.label);
    }
    function validate() { $save.prop('disabled', !$label.val().trim()); }
    $label.on('input', validate);
    validate();
    $label.trigger('focus');
  }

  function setupFieldForm(form) {
    var $form = $(form);
    var bound = $form.attr('data-bound') === 'true';
    if ($form.attr('data-mode') === 'option_label') return setupOptionLabelForm($form, bound);

    var $name = $form.find('[name="name"]');
    var $type = $form.find('[name="field_type"]');
    var $numberType = $form.find('[name="number_type"]');
    var $optionsInput = $form.find('[name="options"]');
    var $draftId = $form.find('[name="draft_id"]');
    var $id = $form.find('[name="id"]');
    var $key = $form.find('[name="key"]');
    var $inUse = $form.find('[name="in_use"]');
    var $save = $form.find('.metadata-field-form__save');
    var $numberSection = $form.find('.metadata-field-form__number');
    var $optionsSection = $form.find('.metadata-field-form__options');
    var $list = $form.find('.metadata-options__list');
    var $optionInput = $form.find('.metadata-options__input');
    var $optionAdd = $form.find('.metadata-options__add-btn');
    var optionUrl = $form.attr('data-option-url');
    var options = [];

    if (!bound) {
      var draft = fragmentDraft();
      if (draft) {
        $draftId.val(draft.draft_id || uid());
        $id.val(draft.id == null ? '' : draft.id);
        $key.val(draft.key || '');
        $inUse.val(draft.in_use ? 'true' : '');
        $name.val(draft.name || '');
        $type.val(draft.field_type || '');
        $numberType.val(draft.number_type || '');
        options = Array.isArray(draft.options) ? draft.options.slice() : [];
      }
    } else {
      try { options = JSON.parse($optionsInput.val() || '[]'); } catch (error) { options = []; }
      if (!Array.isArray(options)) options = [];
    }
    var inUse = /^(true|on|1)$/i.test($inUse.val() || '');
    var originalType = typeSignature();

    function typeSignature() { return ($type.val() || '') + '|' + ($type.val() === 'number' ? ($numberType.val() || '') : ''); }
    function isChoice() { return CHOICE_TYPES.indexOf($type.val()) >= 0; }

    function syncOptions() {
      $optionsInput.val(JSON.stringify(options));
      renderOptions();
      validate();
    }

    function renderOptions() {
      $list.empty();
      options.forEach(function (option) {
        var $row = $(
          '<li class="metadata-options__row">' +
            '<span class="metadata-options__handle" aria-hidden="true">☰</span>' +
            '<span class="metadata-options__label">' + escapeHtml(option.label) + '</span>' +
            '<span class="metadata-options__actions">' +
              '<a href="#" class="metadata-options__edit">Edit</a>' +
              '<a href="#" class="metadata-options__remove">Remove</a>' +
            '</span>' +
          '</li>'
        );
        $row.attr('data-draft-id', option.draft_id);
        $row.find('.metadata-options__edit').on('click', function (event) { event.preventDefault(); editOption(option); });
        $row.find('.metadata-options__remove').on('click', function (event) { event.preventDefault(); removeOption(option); });
        $list.append($row);
      });
      $form.find('.metadata-options__add').toggle(options.length < MAX_OPTIONS);
    }

    function editOption(option) {
      Panels.open(withDraft(optionUrl, { label: option.label })).then(function (result) {
        if (!result || typeof result.label !== 'string') return;
        option.label = result.label;
        syncOptions();
      });
    }

    function removeOption(option) {
      if (option.in_use && !window.confirm(DELETE_OPTION_WARNING)) return;
      options = options.filter(function (existing) { return existing !== option; });
      syncOptions();
    }

    function addOption() {
      var label = $optionInput.val().trim();
      if (!label || options.length >= MAX_OPTIONS) return;
      options.push({ draft_id: uid(), id: null, key: null, label: label, in_use: false });
      $optionInput.val('');
      $optionAdd.prop('disabled', true);
      syncOptions();
      $optionInput.trigger('focus');
    }

    function updateSections() {
      $numberSection.prop('hidden', $type.val() !== 'number');
      $optionsSection.prop('hidden', !isChoice());
    }

    function validate() {
      var valid = !!$name.val().trim() && !!$type.val();
      if ($type.val() === 'number') valid = valid && !!$numberType.val();
      if (isChoice()) valid = valid && options.length > 0;
      $save.prop('disabled', !valid);
    }

    $type.on('change', function () { updateSections(); validate(); });
    $numberType.on('change', validate);
    $name.on('input', validate);
    $optionInput.on('input', function () { $optionAdd.prop('disabled', !$optionInput.val().trim()); });
    $optionInput.on('keydown', function (event) {
      if (event.key === 'Enter') { event.preventDefault(); addOption(); }
    });
    $optionAdd.on('click', function (event) { event.preventDefault(); addOption(); });
    $form.on('submit', function (event) {
      if (inUse && typeSignature() !== originalType && !window.confirm(TYPE_CHANGE_WARNING)) event.preventDefault();
    });

    if (window.Sortable) {
      Sortable.create($list[0], {
        handle: '.metadata-options__handle',
        onEnd: function () { sortByOrder(options, $list); syncOptions(); }
      });
    }

    if (!$draftId.val()) $draftId.val(uid());
    $optionsInput.val(JSON.stringify(options));
    updateSections();
    renderOptions();
    validate();
  }

  $(function () {
    $('[data-metadata-editor]').each(function (i, element) { setupEditor(element); });
    $('[data-metadata-field-form]').each(function (i, element) { setupFieldForm(element); });
  });
})();
