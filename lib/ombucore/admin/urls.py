from django.urls import path

from ombucore.admin.sites import site

urlpatterns = [
    path("panels/", site.urls),
]
