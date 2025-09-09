import json
import re

from bs4 import BeautifulSoup
from django import template
from django.utils.encoding import force_str
from django.utils.html import escape, json_script, strip_tags

from ombucore.admin.sites import site

register = template.Library()


@register.filter(name="chunks")
def chunks(iterable, chunk_size):
    """
    Splits an iterable into chunks of `chunk_size`.
    """
    if not hasattr(iterable, "__iter__"):
        # can't use "return" and "yield" in the same function
        yield iterable
    else:
        i = 0
        chunk = []
        for item in iterable:
            chunk.append(item)
            i += 1
            if not i % chunk_size:
                yield chunk
                chunk = []
        if chunk:
            # some items will remain which haven't been yielded yet,
            # unless len(iterable) is divisible by chunk_size
            yield chunk


@register.filter(name="padded_chunks")
def padded_chunks(iterable, chunk_size):
    """
    Splits an iterable into chunks of `chunk_size`.
    """
    if not hasattr(iterable, "__iter__"):
        # can't use "return" and "yield" in the same function
        yield iterable
    else:
        for chunk in chunks(iterable, chunk_size):
            while len(chunk) < chunk_size:
                chunk.append(None)
            yield chunk


@register.filter(name="jsonify")
def jsonify(value):
    return json.dumps(value)


@register.filter(name="jsonattr")
def jsonattr(value):
    return escape(jsonify(value))


@register.filter(name="related_info")
def related_info(obj):
    return site.related_info_for(obj)


@register.filter(name="url_for")
def url_for(model_instance_or_class, url_name):
    return site.url_for(model_instance_or_class, url_name)


@register.simple_tag(takes_context=True)
def panels_messages(context):
    messages = [
        {"level": m.level_tag, "message": m.message, "extra_tags": m.extra_tags} for m in context["messages"]
    ]
    return json_script(messages, "_initialPanelsMessages")


@register.filter
def smart_title(string):
    """Title cases a string if the first letter is lowercase."""
    if len(string) >= 1 and string[0].islower():
        return string.title()
    return string


CONSONANT_SOUND = re.compile(r"""one(![ir])""", re.IGNORECASE | re.VERBOSE)
VOWEL_SOUND = re.compile(
    r"""[aeio]|u([aeiou]|[^n][^aeiou]|ni[^dmnl]|nil[^l])|h(ier|onest|onou?r|ors\b|our(!i))|[fhlmnrsx]\b""",
    re.IGNORECASE | re.VERBOSE,
)


@register.filter
def a_or_an(text):
    text = force_str(text)
    anora = "an" if not CONSONANT_SOUND.match(text) and VOWEL_SOUND.match(text) else "a"
    return anora


@register.filter
def width_to_percent(width):
    if not width:
        return 0
    return int(round(float(width / 12.0) * 100))


@register.filter
def class_name(obj):
    return obj.__class__.__name__.lower()


@register.filter
def locales_list(locales):
    return ", ".join([locale.name for locale in locales])


@register.filter
def get_admin_overlay_info(model_instance, user):
    return site.admin_overlay_info_for(model_instance, user)


@register.filter
def strip_svg_and_tags(markup):
    soup = BeautifulSoup(markup, features="html.parser")
    tag = soup.find("svg")
    if tag:
        tag.extract()
    return strip_tags(str(soup))
