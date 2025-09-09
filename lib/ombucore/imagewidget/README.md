PreviewableImageInput
=====================

## Installation

Add 'ombucore.imagewidget' to `INSTALLED_APPS`.

Add preview view to URLs.

    from ombucore.imagewidget.views import ajax_file_preview

    url(r'^ajax-file-preview/$', ajax_file_preview, name='ajax-file-preview')


## Usage

    class MyModel(Model):
        image = ImageField

    class MyForm(Form):
        logo = forms.ImageField(
            required=False,
            widget=PreviewableImageInput(preview_generator='lms:organization-logo-form')
        )

`preview_generator` argument is optional, it will use a default if not set.
