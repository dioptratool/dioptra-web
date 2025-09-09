Admin
=====

A panel-based admin site and UI toolkit for Django.


## Installation

Add 'ombucore.admin' to `INSTALLED_APPS` and add the url entry to your
project's `urls.py`.

    urlpatterns = [
        url(r'^panels/', include('ombucore.admin.urls')),
    ]

And register your models and admin central class with the admin site in your
app's `admin.py` file.

    from ombucore import admin

    admin.site.register(Page, PageAdmin)


## Model Relationships

Since the Panels UI has a specific way of selecting and displaying related
objects, there are some custom model fields, form fields and widgets that need
to be ussed to support the form interface.  All models referenced must be
registered with the admin site.


### Model Fields

There are two main relationship widgets, `ombucore.admin.fields.ForeignKey` and
`ombucore.admin.fieds.ManyToMany`. Both of these support referencing multiple types
of objects if they are _polymorphic_. The `Page`, `Block` and `Asset` models
included in OMBU Core are all polymorphic. Usage example:

    from ombucore.admin.fields import ManyToManyField, ForeignKey
    from ombucore.assets.models import Asset, ImageAsset, VideoAsset

    class ExampleModel(models.Model):

        # Reference a single model.
        image = ForeignKey(ImageAsset)

        # Reference a single model of a few types of objects. The first argument is
        # the base polymorphic type and the `models` argument are the options
        # that will show up on the form field.
        image_or_video = ForeignKey(Asset, models=[ImageAsset, VideoAsset])

        # Reference multiple of a single type of object.
        text_blocks = ManyToManyField(RichTextBlock, related_name='text_blocks')

        # Reference multiple of a few types of objects. The first argument is
        # the base polymorphic type and the `models` argument are the options
        # that will show up on the form field.
        blocks = ManyToManyField(Block, models=[RichTextBlock, AssetBlock], related_name='blocks')

These fields behave the same as Django's ForeignKey and ManyToMany fields but
pass the models information along to the form fields.


### Form Fields

There are two form fields that correspond to the model fields:
`ombucore.admin.forms.ModelChoiceField` and
`ombucore.admin.forms.ModelMultipleChoiceField`.

These behave the same as Django's `ModelChoiceField` and
`ModelMultipleChoiceField` but pass along model class choices to their
respective widgets through the `model_classes` keyword argument.


### Form Widgets

The form widgets for these relationships use the passed in model choices and
information about selected objects from the admin site to render objects
selection/creation widgets with editing capabilities.

The widget will render in "add only" mode (no changelist selection) if any of
the model class choices' model admins don't have a changelist view.


## Model Admin

The `ombucore.admin.modeladmin.ModelAdmin` class is the workhorse of the admin
system. Each model should be registered with a `ModelAdmin` instance which
determines how the model is represented in the admin site.

By default, the model admin will try to auto-generate changlist, select, add,
change and delete views for the model. All the views managed by the modeladmin
will have permissions applied by default following the same patterns as the
Django model admin.

| URL | View Class | URL Name | Permission |
|---|---|---|---|
|`/panels/{appname}/{modelname}/` | `{modelname}ChangelistView` | `ombucore.admin:{appname}_{modelname}_changelist` | `{appname}_{modelname}_change` |
|`/panels/{appname}/{modelname}/select/` | `{modelname}ChangelistSelectView` | `ombucore.admin:{appname}_{modelname}_changelist_select` | `{appname}_{modelname}_change` |
|`/panels/{appname}/{modelname}/<pk>/change/` | `{modelname}ChangeView` | `ombucore.admin:{appname}_{modelname}_change` | `{appname}_{modelname}_change` |
|`/panels/{appname}/{modelname}/<pk>/delete/` | `{modelname}DeleteView` | `ombucore.admin:{appname}_{modelname}_delete` | `{appname}_{modelname}_delete` |
|`/panels/{appname}/{modelname}/<pk>/add/` | `{modelname}AddView` | `ombucore.admin:{appname}_{modelname}_add` | `{appname}_{modelname}_add` |


The permissions for these modeladmin-controlled views are applied in the modeladmin's `_wrap_view_with_permission()` method. If you don't want the default permission required applied for a given view you can subclass that method and return the view like this:

~~~
    def _wrap_view_with_permission(self, view, permission_action):
        exclude = ('ContactChangeView', 'ActivityParticipantContactChangeView', 'ContactChangelistSelectView')
        if view.__name__ in exclude:
            # Don't add default permissions.
            return view
        return super(ContactAdmin, self)._wrap_view_with_permission(view, permission_action)
~~~

### Normal Configuration

#### FilterSet

Each ModelAdmin instance should be supplied with a FilterSet class that defines
how the changelist and select views filters, search, and ordering will work.
These are powered by the
[django-filter](https://django-filter.readthedocs.io/en/master/) package. See
the `ombucore.assets.admin` implementations for examples.

    filterset_class = ImageAssetFilterSet

#### Forms

Forms can be configured by either definig a `form_config` dict or
a `form_class` attribute.  The `form_config` option will create a model form
for you with the dict acting as the form configuration that would normally be
in the form's `Meta` class.

This form will be provided to both the add and change views.

If the add and change forms need to be different, `add_form_config`,
`add_form_class`, `change_form_config` and `change_form_class` can be
implemented.


#### List Display

The modeladmin has `list_display` attribute that controls the columns that are
shown in the changelist and select views. `list_display` should be a list of
2-tuples where the first item represents where the value comes from, and the
second item is the column name.

The first items in the `list_display` list resolve in a specific order:

- If the name is a method of the model, the method is called.
- If the name is an attribute/field of the model, that value is used.
- If the name is a method of the view class, the method is called.
- If the name is an attribute/field of the view class, that value is used.
- If the name is a method of the model admin class, the method is called.
- If the name is an attribute/field of the model admin class, that value is
  used.

This lets the developer define the methods used to display data right on the
model admin itself without having to subclasss the changelist view.


### Overriding views

Each of the following views can be overwritten with a class instance to be used
instead. Also, if a view is set to `False` the view and url won't be generated.
This can be helpful for "add-only" objects that don't have changelist or select
views.

- add_view
- change_view
- delete_view
- changelist_view
- changelist_select_view
- reorder_view

Additionally, if a model has an `order` field a ReorderView will automatically
be created and linked to from the changelist view.


### Object Related Info

Each model admin packages together a simple dict of "object info" that
represents it. This "object info" is what poweres the admin form widgets and
selection workflows. When an object is selected from a select list, the object
info is returned in the promise created by `Panels.open()`. By default the
object info includes:

- id: The ID of the object.
- title: Object title, either from a `title` or `name` attribute.
- ctype_id: The content type ID.
- verbose_name: The human name of the model class.
- verbose_name_plural: The plural human name of the model class.
- change_url: The URL where this object can be changed.

Depending on the model additional information can be passed along with this.
The model admin class provides a `modify_related_info(self, info, obj)` method
for making these model-specific changes to the related info.

The most common modification is passing along an `image_url` that will be shown
in the relationship widgets. See `ombucore.assets.admin` for an implementation
of this for both the `ImageAsset` and `VideoAsset` models.


## CKEditor

The CKEditor bundled with `django-ckeditor` doesn't include the Widget plugin
so a custom build is included in this module's `/static` directory.

The following plugins have been added to support asset embedding:

- ombuutil
- ombuimage
- ombuvideo
- ombudocument

These plugins are included in this module's `/static/ckeditor/ckeditor/plugins`
directory, and should be kept when updating CKEditor.
