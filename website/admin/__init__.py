from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

# Load these files to register their admins.
import website.admin.account_code_description
import website.admin.analysis
import website.admin.app_log
import website.admin.category
import website.admin.core
import website.admin.cost_efficiency_strategy
import website.admin.cost_line_item
import website.admin.cost_type
import website.admin.cost_type_category_mapping
import website.admin.country
import website.admin.insight_comparison_data
import website.admin.intervention
import website.admin.region
import website.admin.settings
import website.admin.tags
import website.users.admin  # noqa
from ombucore.admin.sites import AdminCentralBaseView, site
from website.models import FieldLabelOverrides, Settings


class AdminCentralView(LoginRequiredMixin, AdminCentralBaseView):
    title = "Administration"

    def get_groups(self):
        settings = Settings.objects.first()
        field_label_overrides = FieldLabelOverrides.get()
        return [
            {
                "title": _("Analysis"),
                "items": [
                    {
                        "title": _("Analysis"),
                        "links": [
                            {
                                "title": _("Manage Analyses"),
                                "url": reverse("ombucore.admin:website_analysis_changelist"),
                                "perm": "website.change_analysis",
                            },
                        ],
                    },
                    {
                        "title": _("Interventions"),
                        "links": [
                            {
                                "title": _("Manage Interventions"),
                                "url": reverse("ombucore.admin:website_intervention_changelist"),
                                "perm": "website.change_intervention",
                            },
                            {
                                "title": _("Manage Groups"),
                                "url": reverse("ombucore.admin:website_interventiongroup_changelist"),
                                "perm": "website.change_interventiongroup",
                            },
                        ],
                    },
                ],
            },
            {
                "title": _("Configuration"),
                "items": [
                    {
                        "title": _("Categories & Cost Types"),
                        # 'description': _(''),
                        "links": [
                            {
                                "title": _("Manage Categories"),
                                "url": reverse("ombucore.admin:website_category_changelist"),
                                "perm": "website.change_category",
                            },
                            {
                                "title": _("Manage Cost Types"),
                                "url": reverse("ombucore.admin:website_costtype_changelist"),
                                "perm": "website.change_costtype",
                            },
                            {
                                "title": _("Manage Cost Type & Category mappings"),
                                "url": reverse("ombucore.admin:website_costtypecategorymapping_changelist"),
                                "perm": "website.change_costtypecategorymapping",
                            },
                        ],
                    },
                    {
                        "title": _("Countries & Regions"),
                        "links": [
                            {
                                "title": _("Manage Countries"),
                                "url": reverse("ombucore.admin:website_country_changelist"),
                                "perm": "website.change_country",
                            },
                            {
                                "title": _("Manage Regions"),
                                "url": reverse("ombucore.admin:website_region_changelist"),
                                "perm": "website.change_region",
                            },
                        ],
                    },
                    {
                        "title": _("Insight Comparison Data"),
                        "links": [
                            {
                                "title": _("Manage Insight Comparison Data"),
                                "url": reverse("ombucore.admin:website_insightcomparisondata_changelist"),
                                "perm": "website.change_insightcomparisondata",
                            },
                        ],
                    },
                    {
                        "title": _("Cost Efficiency Strategies"),
                        # 'description': _(''),
                        "links": [
                            {
                                "title": _("Manage Cost Efficiency Strategies"),
                                "url": reverse("ombucore.admin:website_costefficiencystrategy_changelist"),
                                "perm": "website.change_costefficiencystrategy",
                            },
                        ],
                    },
                    {
                        "title": _("Account Code Descriptions"),
                        # 'description': _(''),
                        "links": [
                            {
                                "title": _("Manage Account Code Descriptions"),
                                "url": reverse("ombucore.admin:website_accountcodedescription_changelist"),
                                "perm": "website.change_accountcodedescription",
                            },
                        ],
                    },
                    {
                        "title": _("Help"),
                        # 'description': _(''),
                        "links": [
                            {
                                "title": _("Manage Contextual Help"),
                                "url": reverse("ombucore.admin:help_helpitem_changelist"),
                                "perm": "help.change_helpitem",
                            },
                            {
                                "title": _("Manage Help Pages"),
                                "url": reverse("ombucore.admin:help_helppage_changelist"),
                                "perm": "help.change_helppage",
                            },
                        ],
                    },
                    {
                        "title": _("Settings"),
                        # 'description': _(''),
                        "links": [
                            {
                                "title": _("Manage Settings"),
                                "url": reverse(
                                    "ombucore.admin:website_settings_change",
                                    args=[settings.pk],
                                ),
                                "perm": "website.change_settings",
                            },
                            {
                                "title": _("Manage Field Label Overrides"),
                                "url": reverse(
                                    "ombucore.admin:website_fieldlabeloverrides_change",
                                    args=[field_label_overrides.pk],
                                ),
                                "perm": "website.change_fieldlabeloverrides",
                            },
                        ],
                    },
                ],
            },
            {
                "title": _("Users"),
                "items": [
                    {
                        "title": _("Users"),
                        # 'description': _(''),
                        "links": [
                            {
                                "title": _("Manage Users"),
                                "url": reverse("ombucore.admin:users_user_changelist"),
                                "perm": "users.change_any_user",
                            },
                        ],
                    },
                ],
            },
            {
                "title": "Assets",
                "items": [
                    {
                        "title": "Assets",
                        "description": "A collection of images, and "
                        "documents that can be used throughout the website",
                        "links": [
                            {
                                "title": "Manage images",
                                "url": reverse("ombucore.admin:assets_imageasset_changelist"),
                                "perm": "assets.change_imageasset",
                            },
                        ],
                    },
                    {
                        "title": "Asset Folders",
                        "description": "A configurable folder system to store assets "
                        "for easy reference when relating to website content",
                        "links": [
                            {
                                "title": "Manage asset folders",
                                "url": reverse("ombucore.admin:assets_assetfolder_changelist"),
                                "perm": "ombucore_admin.access_admin_central",
                            }
                        ],
                    },
                    {
                        "title": "Tags",
                        "links": [
                            {
                                "title": "Manage tags",
                                "url": reverse("ombucore.admin:taggit_tag_changelist"),
                                "perm": "ombucore_admin.access_admin_central",
                            },
                        ],
                    },
                ],
            },
            {
                "title": _("System Information"),
                "items": [
                    {
                        "title": _("Application Log"),
                        "description": _("View logs and configure notifications."),
                        "links": [
                            {
                                "title": _("View Log"),
                                "url": reverse("ombucore.admin:app_log_applogentry_changelist"),
                                "perm": "app_log.change_subscription",
                            },
                            {
                                "title": _("Send pending subscription notifications"),
                                "url": reverse("send-notification-subscriptions"),
                                "perm": "app_log.change_subscription",
                            },
                        ],
                    },
                    {
                        "title": _("Application Version"),
                        "description": self._get_application_version(),
                        "nolinks": True,
                    },
                ],
            },
        ]


site.register_admin_central_view(AdminCentralView)
