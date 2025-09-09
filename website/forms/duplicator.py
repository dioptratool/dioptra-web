from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from ombucore.admin.widgets import FlatpickrDateWidget


class DuplicateBudgetUploadAnalysisForm(forms.Form):
    pass


class DuplicateTransactionStoreAnalysisForm(forms.Form):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    change_analysis_date_range = forms.ChoiceField(
        choices=(
            ("use_existing", "Duplicate using the current analysis date range"),
            ("change", "Duplicate using a new analysis date range"),
        ),
        widget=forms.RadioSelect(),
    )
    start_date = forms.DateField(
        required=False,
        widget=FlatpickrDateWidget(
            options={"dateFormat": settings.DATE_FORMAT},
            format="%d-%b-%Y",
        ),
        input_formats=settings.DATE_INPUT_FORMATS,
    )
    end_date = forms.DateField(
        required=False,
        widget=FlatpickrDateWidget(
            options={"dateFormat": settings.DATE_FORMAT},
            format="%d-%b-%Y",
        ),
        input_formats=settings.DATE_INPUT_FORMATS,
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("start_date") > cleaned_data.get("end_date"):
            raise ValidationError("Start date must be before end date.")
        return cleaned_data

    class Media:
        js = ("website/js/duplicate.js",)
