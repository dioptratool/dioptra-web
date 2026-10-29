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
 * Options are added, removed, reordered and renamed (through a nested panel) inline. Labels must
 * be unique regardless of case; the option count limits come from the form's data attributes,
 * rendered from the model constants, and the server checks all of it again.
 *
 * Deleting a field or option that analyses hold a value for, or changing such a field's type,
 * first opens the impact panel (data-impact-url), which lists the affected analyses and resolves
 * {confirmed: true} from its Yes button; cancelling or closing it leaves the draft as it was.
 */
(function () {
  'use strict';

  var CHOICE_TYPES = ['multiple_choice', 'single_choice'];
  var TYPE_LABELS = {
    free_text: 'Free Text',
    multiple_choice: 'Multiple Choice',
    single_choice: 'Single Choice',
    number: 'Number'
  };
  var NUMBER_TYPE_LABELS = {
    integer: 'Integer',
    decimal: 'Decimal',
    percentage: 'Percentage',
    currency: 'Currency'
  };
  var UNADDED_OPTION_WARNING = 'The option label you typed has not been added and will be lost. Continue without adding it?';

  function uid() {
    return Math.random().toString(16).slice(2) + Date.now().toString(16);
  }

  function escapeHtml(text) {
    return $('<span>').text(text == null ? '' : String(text)).html();
  }

  // Labels are compared trimmed and case-insensitively, as the server and its constraint do.
  function sameLabel(a, b) {
    return String(a).trim().toLowerCase() === String(b).trim().toLowerCase();
  }

  function duplicateLabelMessage(label) {
    return label.trim() + ': option labels must be unique.';
  }

  // The inline message slot under the option controls; empty hides it.
  function showError($error, message) {
    $error.find('em').text(message || '');
    $error.prop('hidden', !message);
  }

  // The list's type cell: a Number field shows its sub-type, as MetadataEditorWidget renders it.
  function typeLabel(field) {
    if (field.field_type === 'number' && NUMBER_TYPE_LABELS[field.number_type]) {
      return NUMBER_TYPE_LABELS[field.number_type];
    }
    return TYPE_LABELS[field.field_type] || '';
  }

  function fragmentDraft() {
    var raw = new URLSearchParams(window.location.hash.replace(/^#/, '')).get('draft');
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (error) { return null; }
  }

  function withDraft(url, draft) {
    return url + '#draft=' + encodeURIComponent(JSON.stringify(draft));
  }

  // Opens the impact panel for a change to stored values and runs onConfirmed when its Yes button
  // resolves it; a cancel or close resolves nothing. Without an impact URL (a new intervention)
  // nothing is stored, but the callers never ask then: nothing of a new intervention is in use.
  function confirmImpact(impactUrl, params, onConfirmed) {
    if (!impactUrl) return;
    Panels.open(impactUrl + '&' + new URLSearchParams(params).toString()).then(function (result) {
      if (result && result.confirmed) onConfirmed();
    });
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
    var impactUrl = $root.attr('data-impact-url');
    var maxFields = parseInt($root.attr('data-max-fields'), 10);
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
            '<span class="metadata-editor__type">' + escapeHtml(typeLabel(field)) + '</span>' +
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
      if (!field.in_use) return discardField(field);
      confirmImpact(impactUrl, { field: field.key, action: 'delete_field' }, function () { discardField(field); });
    }

    function discardField(field) {
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
    var $error = $form.find('.metadata-options__error');
    var draft = fragmentDraft();
    // The sibling labels travel in the fragment so a rename cannot repeat one of them.
    var taken = draft && Array.isArray(draft.taken) ? draft.taken.filter(function (label) { return typeof label === 'string'; }) : [];
    if (!bound && draft && typeof draft.label === 'string') $label.val(draft.label);
    function validate() {
      var label = $label.val().trim();
      var duplicate = !!label && taken.some(function (other) { return sameLabel(other, label); });
      showError($error, duplicate ? duplicateLabelMessage(label) : '');
      $save.prop('disabled', !label || duplicate);
    }
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
    var $optionError = $form.find('.metadata-options__error');
    var optionUrl = $form.attr('data-option-url');
    var impactUrl = $form.attr('data-impact-url');
    var minOptions = parseInt($form.attr('data-min-options'), 10);
    var maxOptions = parseInt($form.attr('data-max-options'), 10);
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
    var typeChangeConfirmed = false;

    function typeSignature() { return ($type.val() || '') + '|' + ($type.val() === 'number' ? ($numberType.val() || '') : ''); }
    function isChoice() { return CHOICE_TYPES.indexOf($type.val()) >= 0; }

    function labelTaken(label, except) {
      return options.some(function (other) { return other !== except && sameLabel(other.label, label); });
    }

    function syncOptions() {
      showError($optionError, '');
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
      $form.find('.metadata-options__add').toggle(options.length < maxOptions);
    }

    function editOption(option) {
      var taken = options.filter(function (other) { return other !== option; }).map(function (other) { return other.label; });
      Panels.open(withDraft(optionUrl, { label: option.label, taken: taken })).then(function (result) {
        if (!result || typeof result.label !== 'string') return;
        if (labelTaken(result.label, option)) return showError($optionError, duplicateLabelMessage(result.label));
        option.label = result.label;
        syncOptions();
      });
    }

    function removeOption(option) {
      if (!option.in_use) return discardOption(option);
      confirmImpact(
        impactUrl,
        { field: $key.val(), option: option.key, action: 'delete_option' },
        function () { discardOption(option); }
      );
    }

    function discardOption(option) {
      options = options.filter(function (existing) { return existing !== option; });
      syncOptions();
    }

    function addOption() {
      var label = $optionInput.val().trim();
      if (!label || options.length >= maxOptions) return;
      if (labelTaken(label)) return showError($optionError, duplicateLabelMessage(label));
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
      if (isChoice()) valid = valid && options.length >= minOptions;
      $save.prop('disabled', !valid);
    }

    // The option input is deliberately untracked (the form allows abandonment because the controls
    // are filled from the fragment), so the panels framework never sees a label that was typed but
    // not added. Warn before Save or a reject (Cancel, close, veil, Escape) silently drops it; once
    // the user agrees, the label is cleared so a resubmit after the impact panel does not ask again.
    function confirmDiscardingPendingOption() {
      if (!$optionInput.val().trim()) return true;
      if (!window.confirm(UNADDED_OPTION_WARNING)) return false;
      $optionInput.val('');
      return true;
    }

    $type.on('change', function () { updateSections(); validate(); });
    $numberType.on('change', validate);
    $name.on('input', validate);
    $optionInput.on('input', function () {
      showError($optionError, '');
      $optionAdd.prop('disabled', !$optionInput.val().trim());
    });
    $optionInput.on('keydown', function (event) {
      if (event.key === 'Enter') { event.preventDefault(); addOption(); }
    });
    $optionAdd.on('click', function (event) { event.preventDefault(); addOption(); });
    $form.on('submit', function (event) {
      if (!confirmDiscardingPendingOption()) { event.preventDefault(); return; }
      // A type change retires the stored values: confirm it on the impact panel, then resubmit.
      if (inUse && typeSignature() !== originalType && !typeChangeConfirmed) {
        event.preventDefault();
        confirmImpact(impactUrl, { field: $key.val(), action: 'change_type' }, function () {
          typeChangeConfirmed = true;
          form.requestSubmit();
        });
      }
    });
    if (window.Panels && Panels.current) {
      Panels.current.on('beforeReject', function (event) {
        if (!confirmDiscardingPendingOption()) event.preventDefault();
      });
    }

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
