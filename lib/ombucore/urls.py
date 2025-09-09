from django.urls import include, path

from ombucore.imagewidget.views import ajax_file_preview

urlpatterns = [
    path("", include("ombucore.admin.urls")),
    path("ajax-file-preview/", ajax_file_preview, name="ajax-file-preview"),
    path("taggit_autosuggest/", include("taggit_autosuggest.urls")),
]
