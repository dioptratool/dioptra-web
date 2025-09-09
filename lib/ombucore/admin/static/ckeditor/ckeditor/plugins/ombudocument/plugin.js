/**
 * Plugin to interface with ombumess video asset files.
 *
 * Problems:
 *
 * The default object selector uses `showRelatedObjectLookup()` (in
 * RelatedObjectLookups.js) to show the pop-up.  But the pop-up links are
 * hardcoded with `dismissRelatedLookupPopup(win, "chosenId")` so it's not
 * possible to have custom handlers or to return extra info about the object.
 */
(function() {

  var defaultSettings = {
    objInfo: {},
    align: 'left',
  };

  CKEDITOR.plugins.add('ombudocument', {
    requires: 'widget,ombuutil',
    icons: 'ombudocument',
    init: function(editor) {

      var util = CKEDITOR.ombuutil;

      // Register Dialog.
      CKEDITOR.dialog.add('ombudocument', this.path + 'dialogs/dialog.js')

      // Add the stylesheet to the editor.
      var pluginDirectory = this.path;
      editor.addContentsCss(pluginDirectory + 'styles/ombudocument.css');

      // Add the stylesheet to the base page for dialog styles.
      util.addPageStylesheet(pluginDirectory + 'styles/ombudocument.css');

      editor.widgets.add('ombudocument', {
        button: 'Document',
        template: '<div data-ombudocument=""></div>',
        allowedContent: 'div[data-ombudocument]',
        requiredContent: 'div[data-ombudocument]',
        dialog: 'ombudocument',
        upcast: function(element) {
          return element && element.name == 'div' && element.attributes['data-ombudocument'];
        },
        init: function() {
          // Populate widget data from DOM.
          var widget = this;
          var settings = util.unpackWidgetSettings(widget, 'data-ombudocument', defaultSettings);
        },
        data: function() {
          // Move widget data into DOM.
          var widget = this;
          var settings = util.packWidgetSettings(widget, 'data-ombudocument');
          if (settings.objInfo) {
              var previewHtml = ['',
                '<div class="ombudocument-title">' + settings.objInfo.title + '</div>',
                '<div class="ombudocument-type">Document</div>',
            ''].join('');
              widget.element.setHtml(previewHtml);
          }
          widget.wrapper.removeClass('ombuassets-document-align-left');
          widget.wrapper.removeClass('ombuassets-document-align-right');
          if (settings.align) {
            widget.wrapper.addClass('ombuassets-document-align-' + settings.align);
          }
        }
      });

    }
  });

})();
