import json

from bs4 import BeautifulSoup
from django import template
from django.template.defaultfilters import stringfilter

from ombucore.assets.models import DocumentAsset, ImageAsset
from ombucore.assets.renderers import DocumentRenderer, ImageRenderer

register = template.Library()

ASSET_TYPES = (
    {
        "model": ImageAsset,
        "attr": "data-ombuimage",
        "render_fn": ImageRenderer(),
    },
    {
        "model": DocumentAsset,
        "attr": "data-ombudocument",
        "render_fn": DocumentRenderer(),
    },
)


@register.filter(name="assets")
@stringfilter
def assets_expand_asset(source_html, asset_types=ASSET_TYPES):
    """
    Replaces asset tags in rich text with their rendered objects.
    """
    soup = BeautifulSoup(source_html, "html.parser")

    # Collect all the items to be replaced and their replacement html.  We
    # can't replace them in this loop because the newly inserted BeautifulSoup
    # objects will break the `findAll()` method.
    to_replace = []
    for asset_type in asset_types:
        attr = asset_type["attr"]
        model = asset_type["model"]
        # Get all elements with matching data attribute, no matter tag (i.e. <p>, <div>, <span>, etc.)
        matching_elements = [elem for elem in soup.find_all() if attr in elem.attrs]
        for element in matching_elements:
            try:
                settings = json.loads(element.attrs[attr])
                object_id = settings["objInfo"]["id"]
                obj = model.objects.filter(id=object_id).get()
                html = obj.render_embedded(settings, asset_type["render_fn"])
                to_replace.append({"element": element, "html": html})
            except Exception as e:
                pass

    # Replace each item.
    for item in to_replace:
        new_element = BeautifulSoup(item["html"], "html.parser")
        item["element"].replaceWith(new_element)
    return str(soup)
