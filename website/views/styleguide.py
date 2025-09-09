import logging

from django.shortcuts import render

logger = logging.getLogger(__name__)


def styleguidetoc(request, context=None):
    if not context:
        context = {}
    context["title"] = "Dioptra Styleguide"
    return render(request, "styleguide/styleguide-toc.html", context)


def styleguidecolors(request, context=None):
    if not context:
        context = {}
    context["title"] = "Style Guide - Colors"
    context["colors"] = [
        [
            {
                "name": "Lapis",
                "value": "#10457A",
                "machineValue": "#10457A",
            },
            {
                "name": "Topaz",
                "value": "#1B77D4",
                "machineValue": "#1B77D4",
            },
            {
                "name": "Moonstone",
                "value": "#FACF5A",
                "machineValue": "#FACF5A",
            },
            {
                "name": "Moss",
                "value": "#69BF79",
                "machineValue": "#69BF79",
            },
            {
                "name": "Lichen",
                "value": "#B75757",
                "machineValue": "#B75757",
            },
        ],
        [
            {
                "name": "Mineshaft",
                "value": "#333333",
                "machineValue": "#333333",
            },
            {
                "name": "Boulder",
                "value": "#767676",
                "machineValue": "#767676",
            },
            {
                "name": "Smoke",
                "value": "#9B9B9B",
                "machineValue": "#9B9B9B",
            },
            {
                "name": "White",
                "value": "#FFFFFF",
                "machineValue": "#FFFFFF",
            },
        ],
    ]
    return render(request, "styleguide/styleguide-colors.html", context)


def styleguidetypography(request, context=None):
    if not context:
        context = {}
    context["title"] = "Style Guide - Typography"
    context["headings"] = {
        "h1Label": "H1 - 36px Bold #333333",
        "h2Label": "H2 - 28px Bold #333333",
        "h3Label": "H3 - 24px Bold #333333",
        "pLabel": "P, Body Text - 18px Regular #333333",
    }
    context["typefaces"] = [
        {
            "label": "Arial Regular",
            "machineFamily": "Arial",
            "machineWeight": "400",
            "machineStyle": "normal",
        },
        {
            "label": "Arial Regular Italic",
            "machineFamily": "Arial",
            "machineWeight": "400",
            "machineStyle": "italic",
        },
        {
            "label": "Arial Bold",
            "machineFamily": "Arial",
            "machineWeight": "700",
            "machineStyle": "normal",
        },
    ]
    return render(request, "styleguide/styleguide-typography.html", context)


def styleguiderte(request, context=None):
    if not context:
        context = {}
    context["title"] = "Style Guide - RTE Example"
    return render(request, "styleguide/styleguide-rte.html", context)


def styleguidebuttons(request, context=None):
    if not context:
        context = {}
    context["title"] = "Style Guide - Buttons and Links"
    context["primary"] = {
        "visible": "true",
    }
    context["secondary"] = {
        "visible": "true",
    }
    context["tertiary"] = {
        "visible": "false",
    }
    context["textLink"] = {
        "visible": "true",
    }
    return render(request, "styleguide/styleguide-buttons.html", context)


def styleguideforms(request, context=None):
    if not context:
        context = {}
    context["title"] = "Style Guide - RTE Example"
    return render(request, "styleguide/styleguide-forms.html", context)
