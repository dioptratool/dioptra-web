/**
 * Plugin to interface with ombumess Image asset files.
 *
 * Problems:
 *
 * The default object selector uses `showRelatedObjectLookup()` (in
 * RelatedObjectLookups.js) to show the pop-up.  But the pop-up links are
 * hardcoded with `dismissRelatedLookupPopup(win, "chosenId")` so it's not
 * possible to have custom handlers or to return extra info about the object.
 */
(function() {

  var template = new CKEDITOR.template(['',
      '{preview}',
      '<span style="display: {captionDisplay};" class="caption">{caption}</span>',
  ''].join(''));

  var defaultSettings = {
    objInfo: {},
    caption: '',
    align: 'center'
  };


  CKEDITOR.plugins.add('ombuimage', {
    requires: 'widget,ombuutil',
    icons: 'ombuimage',
    init: function(editor) {

      var util = CKEDITOR.ombuutil;

      // Register Dialog.
      CKEDITOR.dialog.add('ombuimage', this.path + 'dialogs/dialog.js')

      // Add the stylesheet.
      var pluginDirectory = this.path;
      editor.addContentsCss(pluginDirectory + 'styles/ombuimage.css');

      editor.widgets.add('ombuimage', {
        button: 'Image',
        template: '<div data-ombuimage=""></div>',
        allowedContent: 'div[data-ombuimage];',
        requiredContent: 'div[data-ombuimage]',
        dialog: 'ombuimage',
        upcast: function(element) {
          return element && element.name == 'div' && element.attributes['data-ombuimage'];
        },
        init: function() {
          // Populate widget data from DOM.
          var widget = this;
          var settings = util.unpackWidgetSettings(widget, 'data-ombuimage', defaultSettings);
        },
        data: function() {
          // Move widget data into DOM.
          var widget = this;
          var settings = util.packWidgetSettings(widget, 'data-ombuimage');
          var templateVars = {
            preview: settings.objInfo.image_url ? '<img src="' + settings.objInfo.image_url + '" />' : '',
            caption: settings.caption,
            captionDisplay: settings.caption.length ? 'block' : 'none'
          };
          widget.element.setHtml(template.output(templateVars));

          widget.wrapper.addClass('ombuimage-wrapper');
          widget.wrapper.addClass('ombuassets-image');
          widget.wrapper.removeClass('ombuassets-image-align-left');
          widget.wrapper.removeClass('ombuassets-image-align-right');
          widget.wrapper.removeClass('ombuassets-image-align-center');
          widget.wrapper.addClass('ombuassets-image-align-' + settings.align);
          widget.wrapper.setAttribute('data-ombuimage-align', settings.align);
        }
      });

    }
  });

})();
