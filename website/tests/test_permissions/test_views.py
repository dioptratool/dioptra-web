import pytest
from django.urls import NoReverseMatch, URLResolver, get_resolver, reverse

from website.models import Analysis, CostType


def extract_path_names(urlpatterns):
    """Get all URL patterns by name"""

    urls = []
    for pattern in urlpatterns:
        if isinstance(pattern, URLResolver):
            # Resolve "included" URL patterns
            urls.extend(extract_path_names(pattern.url_patterns))
        else:
            urls.append(pattern.name)
    return urls


@pytest.mark.django_db
class TestPageAccess:
    PUBLIC_PAGES = [
        "/styleguide/",
        "/styleguide/colors/",
        "/styleguide/typography/",
        "/styleguide/rte/",
        "/styleguide/forms/",
        "/styleguide/buttons-links/",
        "/help/",
        "/panels/app_log/send-notifications/",
        "/taggit_autosuggest/list/",
        "/accounts/signup/",
        "/accounts/login/",
        "/accounts/inactive/",
        "/accounts/confirm-email/",
        "/accounts/password/reset/",
        "/accounts/password/reset/done/",
        "/accounts/password/reset/key/done/",
        "/accounts/3rdparty/login/cancelled/",
        "/accounts/3rdparty/login/error/",
        "/accounts/adminlogin/",
        "/password-reset/",
        "/password-reset/done/",
        "/reset/done/",
    ]

    SKIPPED_URLS = ["/ajax-file-preview/"]

    @pytest.fixture
    def urls_with_params(self, analysis_workflow_with_all_cost_lines_allocated_to_subcomponents):
        analysis_wf = analysis_workflow_with_all_cost_lines_allocated_to_subcomponents
        analysis_pk = Analysis.objects.first().pk
        cost_type_pk = analysis_wf.analysis.cost_line_items.first().config.cost_type.pk
        grant = Analysis.objects.first().grants.split()[0]
        subcomponent_analysis_pk = Analysis.objects.first().subcomponent_cost_analysis.pk

        return [
            ("analysis", {"pk": analysis_pk}),
            ("analysis-define-update", {"pk": analysis_pk}),
            ("analysis-load-data", {"pk": analysis_pk}),
            ("analysis-categorize", {"pk": analysis_pk}),
            (
                "analysis-categorize-cost_type",
                {"pk": analysis_pk, "cost_type_pk": cost_type_pk},
            ),
            (
                "analysis-categorize-cost_type-bulk",
                {"pk": analysis_pk, "cost_type_pk": cost_type_pk},
            ),
            ("analysis-allocate", {"pk": analysis_pk}),
            (
                "analysis-allocate-cost_type-grant--save-suggested",
                {"pk": analysis_pk, "cost_type_pk": cost_type_pk, "grant": grant},
            ),
            (
                "analysis-allocate-cost_type-grant",
                {
                    "pk": analysis_pk,
                    "cost_type_pk": cost_type_pk,
                    "grant": grant,
                },
            ),
            ("analysis-allocate-supporting-costs", {"pk": analysis_pk, "grant": grant}),
            ("analysis-add-other-costs", {"pk": analysis_pk}),
            (
                "analysis-add-other-costs-detail",
                {"pk": analysis_pk, "cost_type": 1},
            ),
            ("analysis-insights", {"pk": analysis_pk}),
            (
                "analysis-insights-lesson-editor",
                {"pk": analysis_pk, "lesson_field": "breakdown_lesson"},
            ),
            ("analysis-insights-print", {"pk": analysis_pk}),
            ("analysis-cost-model-spreadsheet", {"pk": analysis_pk}),
            ("subcomponent-cost-analysis-create", {"pk": analysis_pk}),
            (
                "subcomponent-cost-analysis",
                {"pk": analysis_pk, "subcomponent_pk": subcomponent_analysis_pk},
            ),
            (
                "subcomponent-cost-analysis-label-edit",
                {"pk": analysis_pk, "subcomponent_pk": subcomponent_analysis_pk},
            ),
            (
                "subcomponent-cost-analysis-allocate",
                {"pk": analysis_pk, "subcomponent_pk": subcomponent_analysis_pk},
            ),
            (
                "subcomponent-cost-analysis-allocate-cost_type-grant",
                {
                    "pk": analysis_pk,
                    "subcomponent_pk": subcomponent_analysis_pk,
                    "cost_type_pk": cost_type_pk,
                    "grant": grant,
                },
            ),
        ]

    def test_anonymous_user_access_is_blocked_simple_pages(self, client):
        """
        When an AnonymousUser tries to access a list of specific pages,
        then the server should return a non-200 status code
        """

        paths = extract_path_names(get_resolver().url_patterns)
        for name in paths:
            try:
                url = reverse(name)
            except NoReverseMatch:
                # These are urls that have arguments that we need to test manually
                continue
            if url in self.PUBLIC_PAGES:
                continue

            if url in self.SKIPPED_URLS:
                continue

            try:
                response = client.get(url)
            except Exception as e:
                print()
                print()
                print(url)
                print()
                print()
                raise e
            assert response.status_code == 302, f"Unexpected status code for: {url} ({name})"
            assert response.url.startswith(
                "/accounts/login/"
            ), f'The redirect from {url} doesn\'t start with "/accounts/login/": {response.url}'

    def test_anonymous_user_access_is_blocked_pages_with_params(self, client, urls_with_params):
        for name, params in urls_with_params:
            url = reverse(name, kwargs=params)
            # First we check that it redirects
            try:
                response = client.get(url)
            except Exception as e:
                assert False, f"Unexpected exception for: {url} ({name}):  {e}"
            assert response.status_code == 302, f"Unexpected status code for: {url} ({name})"
            response = client.get(url, follow=True)
            # Check the redirect chain to see if it ends up at the login page
            final_url = (
                response.redirect_chain[-1][0] if response.redirect_chain else response.request["PATH_INFO"]
            )
            assert final_url.startswith(
                "/accounts/login/"
            ), f'The redirect from {url} doesn\'t start with "/accounts/login/": {response.url}'
