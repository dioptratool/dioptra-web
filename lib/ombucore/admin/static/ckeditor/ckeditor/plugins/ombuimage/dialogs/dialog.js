CKEDITOR.dialog.add('ombuimage', function(editor) {

  var util = CKEDITOR.ombuutil;

  function update(dialog, objInfo) {
    var contentElement = dialog.getContentElement('main', 'image');
    var domElement = contentElement.getElement();
    if (objInfo && objInfo.id) {
      contentElement.setValue(objInfo);
      domElement.setHtml('<img src="' + objInfo.image_url + '" />');
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
    title: 'Image',
    minWidth: 300,
    minHeight: 'auto',
    contents: [
      {
        id: 'main',
        label: 'Image',
        elements: [
          {
            type: 'html',
            html: '<div style="max-width: 100%; max-height: 300px;"></div>',
            id: 'image',
            setup: function(widget) {
              update(this.getDialog(), widget.data.objInfo);
            },
            commit: function(widget) {
              widget.setData('objInfo', this.getValue());
            },
            validate: validateRequired("Please select an image.")
          },
          {
            type: 'button',
            label: 'Select an Image',
            onClick: function() {
              var el = this;
              var dialog = el.getDialog();

              Panels.open('/panels/assets/imageasset/select/').then(function(data) {
                update(dialog, data.info);
              });
            }
          },
          {
            id: 'caption',
            type: 'text',
            label: 'Caption',
            setup: function(widget) {
              var dialog = this.getDialog();
              var contentElement = dialog.getContentElement('main', 'caption');
              contentElement.setValue(widget.data.caption);
            },
            commit: function(widget) {
              widget.setData('caption', this.getValue());
            }
          },
          {
            id: 'align',
            type: 'select',
            label: 'Alignment',
            items: [
              ['Center', 'center'],
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
    ]
  };


});
