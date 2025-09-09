from django.db.models import Q

from ombucore.admin.views import DeleteView
from website import models as website_models


class ProtectedDeleteView(DeleteView):
    """
    Displays a custom protected error message when used with category or cost_type admins.
    """

    def get_protected_error_message(self, _unused):
        """
        Override method from DeleteView.
        """
        field = self.object.__class__.__name__.lower()  # category or cost_type
        titles_in_use = self.titles_in_use(field)
        protected_error_message = self.custom_protected_error_message(titles_in_use, field)
        return protected_error_message

    def titles_in_use(self, field):
        query = Q(**{field: self.object})
        related_analyses = website_models.AnalysisCostTypeCategory.objects.filter(query).distinct().all()

        titles_in_use = [u.analysis.title for u in list(related_analyses)]
        return titles_in_use

    def custom_protected_error_message(self, titles_in_use, field):
        num_titles = len(titles_in_use)
        num_titles_to_display = 10
        message = (
            f"Unable to delete {field} {self.object.name}. It's being used by the following analyses:</br>"
        )

        for title in titles_in_use[:num_titles_to_display]:
            message += f"- {title}</br>"

        if num_titles > num_titles_to_display:
            message += f"... and {num_titles - num_titles_to_display} more analyses"
        return message
