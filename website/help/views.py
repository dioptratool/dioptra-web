from django.http import Http404
from django.shortcuts import get_object_or_404, render

from website.help.fields import HELP_TOPICS
from website.help.models import HelpPage


def help_menu(request):
    pages_by_topic = {}
    for topic in HELP_TOPICS:
        pages_by_topic[topic] = HelpPage.objects.filter(topic__title=topic, published=True)
    return render(request, "help/help-menu.html", {"pages_by_topic": pages_by_topic})


def help_page(request, path):
    page = get_object_or_404(HelpPage, path=path)
    if not page.published:
        raise Http404()
    return render(request, "help/help-page.html", {"page": page})
