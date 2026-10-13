/**
 * Warn before leaving a page with unsaved form edits (replaces the
 * jquery.are-you-sure plugin).
 *
 * Each matching form records its fields' values when this runs. While any
 * field differs from its recorded value the form has the `dirty` class
 * (allocate-bulk.js and corrections.js read it), and leaving the page asks
 * the browser to confirm. Submitting or resetting the form clears it.
 *
 * Field events are delegated through jQuery so that values set by script
 * and announced with `$(field).trigger('change')` are tracked too.
 */
const FIELDS = 'input:not([type="submit"]):not([type="button"]), select, textarea';
const FIELD_EVENTS = 'change keyup input';
const DIRTY = 'dirty';
const originals = new WeakMap();

function fieldValue(field) {
  if (!field.name) return null;
  if (field.matches(':disabled')) return 'disabled';
  if (field.type === 'checkbox' || field.type === 'radio') return field.checked;
  if (field.tagName === 'SELECT') return [...field.selectedOptions].map((option) => option.value).join('');
  return field.value;
}

function isDirty(form) {
  return [...form.querySelectorAll(FIELDS)].some(
    (field) => originals.has(field) && fieldValue(field) !== originals.get(field),
  );
}

function watchForm(form) {
  form.querySelectorAll(FIELDS).forEach((field) => originals.set(field, fieldValue(field)));
  form.classList.remove(DIRTY);

  $(form)
    .on(FIELD_EVENTS, FIELDS, () => form.classList.toggle(DIRTY, isDirty(form)))
    .on('submit reset', () => form.classList.remove(DIRTY));
}

let unloadWarningInstalled = false;

export function warnOnUnsavedChanges(selector, message) {
  document.querySelectorAll(selector).forEach(watchForm);

  if (!unloadWarningInstalled) {
    unloadWarningInstalled = true;
    window.addEventListener('beforeunload', (event) => {
      if (!document.querySelector(`form.${DIRTY}`)) return;
      // Browsers show their own text; the message only matters to legacy ones.
      event.preventDefault();
      event.returnValue = message;
    });
  }
}
