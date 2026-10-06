/**
 * Initialise Tagify on every TagEditorWidget input.
 *
 * The widget passes its options as JSON in `data-tageditor` (mode, whitelist, enforceWhitelist,
 * dropdown, placeholder, tagTextProp, ...). The posted value is always the comma-joined list of
 * tag values, which is what the forms parse.
 *
 * Runs on DOM ready (panels load their form media in the head) and again on load for pages that
 * add inputs late; an input is only initialised once.
 */
(function () {
  function init() {
    document.querySelectorAll('input[data-tageditor]').forEach(function (input) {
      if (input.dataset.tagifyReady) {
        return;
      }
      input.dataset.tagifyReady = 'true';
      var options = {};
      try {
        options = JSON.parse(input.dataset.tageditor || '{}') || {};
      } catch (error) {
        options = {};
      }
      options.originalInputValueFormat = function (valuesArr) {
        return valuesArr.map(function (item) { return item.value; }).join(',');
      };
      new Tagify(input, options);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  window.addEventListener('load', init);
})();
