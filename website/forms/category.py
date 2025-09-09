from django.forms import Form, ModelChoiceField

from website.models import Category


class CategorySetDefaultForm(Form):
    category = ModelChoiceField(
        Category.objects.all(),
        label="Default Category",
        help_text="This category will be applied to all uncategorized cost items when data is loaded within an analysis",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            current_default = Category.objects.get(default=True)
        except Category.DoesNotExist:
            current_default = None
        self.fields["category"].initial = current_default
