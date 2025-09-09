$(function() {

    $('.previewable-file-widget').each(function(i, el) {
        new PreviewableFileWidget(el);
    });

});

function PreviewableFileWidget(wrapperEl) {
    this.els = {};
    this.els.wrapper = wrapperEl;
    this.els.$wrapper = $(wrapperEl);
    this.els.$input = this.els.$wrapper.find('input[type="file"]');
    this.els.$remove = this.els.$wrapper.find('.remove');
    this.els.$preview = this.els.$wrapper.find('.preview');
    this.els.$modeEmpty = this.els.$wrapper.find('.mode-empty');
    this.els.$modeValue = this.els.$wrapper.find('.mode-value');

    this.previewURL = this.els.$input.attr('data-ajax-file-preview-url');
    this.previewGenerator = this.els.$input.attr('data-preview-generator');
    this.csrfmiddlewaretoken = this.els.$input.parents('form').find('input[name="csrfmiddlewaretoken"]').val();
    this.hasValue = !!this.els.$preview.html().length;

    this.els.$input.on('change', $.proxy(this.fileChanged, this));
    this.els.$remove.on('click', $.proxy(this.fileRemove, this));
    this.updateUI();
}

PreviewableFileWidget.prototype.fileChanged = function(e) {
    var file = e.target.files[0];
    if (!file) {
        return;
    }
    var data = new FormData();
    data.append('file', file);
    data.append('preview-generator', this.previewGenerator)
    data.append('csrfmiddlewaretoken', this.csrfmiddlewaretoken);

    $.ajax({
        url: this.previewURL,
        type: 'POST',
        data: data,
        cache: false,
        dataType: 'text',
        processData: false,
        contentType: false,
        success: $.proxy(previewSuccess, this),
        error: $.proxy(previewFailure, this)
    });

    this.els.$preview.html('');
    this.hasValue = true;
    this.updateUI();
    this.markChange();

    function previewSuccess(data) {
        var $img = $('<img />');
        this.els.$preview.append($img);
        $img[0].src = data;
    }

    function previewFailure() {}
};

PreviewableFileWidget.prototype.fileRemove = function(e) {
    e.preventDefault();
    this.hasValue = false;
    this.updateUI();
    this.markChange();
};

PreviewableFileWidget.prototype.markChange = function() {
    this.els.$wrapper.parents('.form-group').addClass('changed');
    this.els.$wrapper.trigger('panel:inputchanged');
};

PreviewableFileWidget.prototype.updateUI = function() {
    if (this.hasValue) {
        this.els.$wrapper.attr('data-mode', 'value');
        this.els.$wrapper.find('.clear-checkbox').prop('checked', false);
    }
    else {
        this.els.$preview.html('');
        this.els.$wrapper.attr('data-mode', 'empty');
        this.els.$wrapper.find('.clear-checkbox').prop('checked', true);
    }
};
