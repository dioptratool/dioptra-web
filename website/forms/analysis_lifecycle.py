from django import forms


class AnalysisLifecycleConfirmForm(forms.Form):
    """
    The confirmation for a lifecycle action. The action and its target come from the URL, so the
    form has no fields; a rejection by the lifecycle service is shown as a non-field error.
    """

    # The panel form template asks before a form with changes is abandoned; this one has none.
    allow_abandonment = True
