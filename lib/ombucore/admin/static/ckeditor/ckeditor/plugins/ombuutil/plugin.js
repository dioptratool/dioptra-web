/**
 * Plugin to interface with Asset files.
 *
 * Problems:
 *
 * The default object selector uses `showRelatedObjectLookup()` (in
 * RelatedObjectLookups.js) to show the pop-up.  But the pop-up links are
 * hardcoded with `dismissRelatedLookupPopup(win, "chosenId")` so it's not
 * possible to have custom handlers or to return extra info about the object.
 */
(function() {

  CKEDITOR.plugins.add('ombuutil', {});

  function unpackWidgetSettings(widget, settingsAttrName, defaultSettings) {
    defaultSettings = defaultSettings || {};

    var settingsJson = widget.element.getAttribute(settingsAttrName) || '{}';
    var attrSettings = JSON.parse(settingsJson) || {};

    var settings = jQuery.extend({}, defaultSettings, attrSettings);

    for (key in settings) {
      if (settings.hasOwnProperty(key)) {
        widget.setData(key, settings[key]);
      }
    }
    return settings;
  }

  function packWidgetSettings(widget, settingsAttrName) {
    var settings = {};
    for (key in widget.data) {
      if (widget.data.hasOwnProperty(key)) {
        settings[key] = widget.data[key];
      }
    }
    if (settings.hasOwnProperty('classes')) {
        delete settings['classes'];
    }
    widget.element.setAttribute(settingsAttrName, JSON.stringify(settings));
    return settings;
  }

  function addPageStylesheet(url) {
      var link = document.createElement('link');
      link.type = 'text/css';
      link.rel = 'stylesheet';
      link.href = url;
      document.head.appendChild(link);
  }

  CKEDITOR.ombuutil = CKEDITOR.ombuutils || {
    unpackWidgetSettings: unpackWidgetSettings,
    packWidgetSettings: packWidgetSettings,
    addPageStylesheet: addPageStylesheet
  };

})();
