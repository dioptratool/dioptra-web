CKEDITOR.dialog.add('ombudocument', function(editor) {

  var util = CKEDITOR.ombuutil;

  function update(dialog, objInfo) {
    var contentElement = dialog.getContentElement('main', 'document_id');
    var domElement = contentElement.getElement();
    if (objInfo && objInfo.id) {
      contentElement.setValue(objInfo);
      domElement.setHtml('<div class="preview">' + objInfo.title + '</div>');
      domElement.findOne('> *')
          .setStyle('max-width', '100%')
          .setStyle('max-height', '300px');
    }
    else {
      contentElement.setValue(null);
      domElement.setHtml("");
    }
  }

  function validateRequired(missing_msg) {
    return function() {
      if (!this.getValue()) {
        alert(missing_msg);
        return false;
      }
      return true;
    }
  }

  return {
    title: 'Document',
    minWidth: 300,
    minHeight: 'auto',
    contents: [
      {
        id: 'main',
        label: 'document',
        elements: [
          {
            type: 'html',
            html: '<div></div>',
            id: 'document_id',
            setup: function(widget) {
              update(this.getDialog(), widget.data.objInfo);
            },
            commit: function(widget) {
              widget.setData('objInfo', this.getValue());
            },
            validate: validateRequired("Please select a document.")
          },
          {
            type: 'button',
            label: 'Select a Document',
            onClick: function() {
              var el = this;
              var dialog = el.getDialog();
              Panels.open('/panels/assets/documentasset/select/').then(function(data) {
                update(dialog, data.info);
              });
            }
          },
          {
            id: 'align',
            type: 'select',
            label: 'Alignment',
            items: [
              ['Left', 'left'],
              ['Right', 'right']
            ],
            setup: function(widget) {
              var dialog = this.getDialog();
              var contentElement = dialog.getContentElement('main', 'align');
              contentElement.setValue(widget.data.align);
            },
            commit: function(widget) {
              widget.setData('align', this.getValue());
            }
          }
        ]
      }
    ],
    onLoad: function() {
      var dialog = this;

      // Add a class for targeting styles.
      dialog.parts.dialog.addClass('ombudocument-dialog');
    }
  };
});
