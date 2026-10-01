import re

import pytest
from django.contrib.auth import get_user_model

from website.models import AnalysisStatus, Settings
from website.tests.factories import (
    AnalysisFactory,
    HelpPageFactory,
    HelpTopicFactory,
    InterventionFactory,
    UserFactory,
)

User = get_user_model()


@pytest.mark.django_db
class TestDashboard:
    def test_can_view_dashboard(self, client_with_admin, defaults):
        intervention = InterventionFactory(name="Legal Aid Case Management")
        analysis = AnalysisFactory()
        analysis.add_intervention(intervention)
        response = client_with_admin.get("/", follow=True)
        assert response.status_code == 200
        assert response.content.decode().count("Legal Aid Case Management") == 3

    def test_can_view_analysis(self, client_with_admin, analysis_workflow_with_loaddata_complete):
        analysis = analysis_workflow_with_loaddata_complete.analysis
        analysis.title = "DFID CCI IRC Cash Transfer Program (September 2017)"
        analysis.save()
        response = client_with_admin.get(f"/analysis/{analysis.pk}/", follow=True)
        assert response.status_code == 200
        assert response.content.decode().count("DFID CCI IRC Cash Transfer Program (September 2017)") == 1

    def test_can_view_lesson(self, client_with_admin):
        a = InterventionFactory(
            description="Provision of sufficient quantity of safe water to meet the "
            "drinking and domestic needs of people in need."
        )
        response = client_with_admin.get(f"/intervention/{a.pk}/")
        assert response.status_code == 200
        assert (
            response.content.decode().count(
                "Provision of sufficient quantity of safe water to meet the "
                "drinking and domestic needs of people in need."
            )
            == 1
        )

    def test_can_define_analysis(self, client_with_admin):
        response = client_with_admin.get("/analysis/define/")
        assert response.status_code == 200
        assert response.content.decode().count("Define the details of this analysis") == 2

    def test_can_view_help_page(self, client_with_admin):
        HelpPageFactory(topic=HelpTopicFactory(title="Using Dioptra results"))
        response = client_with_admin.get("/help/")
        assert response.status_code == 200
        assert response.content.decode().count("Using Dioptra results") == 1

    def test_can_view_help_article(self, client_with_admin):
        HelpPageFactory(title="Scale of Training")
        response = client_with_admin.get("/help/scale-of-training/")
        assert response.status_code == 200
        assert response.content.decode().count("Scale of Training") == 1


def titles(response):
    return [analysis.title for analysis in response.context["object_list"]]


def facet(content, name):
    """The markup of one 'Add filter' facet, up to the next facet or the end of the filter form."""
    start = content.index(f'data-filter="{name}"')
    rest = content[start + len(f'data-filter="{name}"') :]
    end = min(index for index in (rest.find('data-filter="'), rest.find("</form>")) if index >= 0)
    return rest[:end]


def sort_link(content, column, direction=""):
    match = re.search(rf'href="(\?[^"]*order_by={direction}{column}[^"]*)"', content)
    assert match, f"no sort link for {direction}{column}"
    return match.group(1).replace("&amp;", "&")


@pytest.mark.django_db
class TestDashboardLifecycle:
    @pytest.fixture
    def analyses(self, defaults):
        return {
            "in_progress": AnalysisFactory(title="In progress one"),
            "complete": AnalysisFactory(
                title="Complete one", lifecycle__analysis_status=AnalysisStatus.COMPLETE
            ),
            "validated": AnalysisFactory(
                title="Validated one", lifecycle__analysis_status=AnalysisStatus.VALIDATED
            ),
            "archived": AnalysisFactory(title="Archived one", lifecycle__is_archived=True),
        }

    def test_default_view_hides_archived_analyses_and_selects_no(self, client_with_admin, analyses):
        response = client_with_admin.get("/")

        assert response.status_code == 200
        assert "Archived one" not in titles(response)
        assert len(titles(response)) == 3
        assert 'value="no" selected' in response.content.decode()

    def test_explicit_no_matches_the_default(self, client_with_admin, analyses):
        assert titles(client_with_admin.get("/?archived=no")) == titles(client_with_admin.get("/"))

    def test_cleared_archive_filter_shows_everything(self, client_with_admin, analyses):
        response = client_with_admin.get("/?archived=")

        assert sorted(titles(response)) == [
            "Archived one",
            "Complete one",
            "In progress one",
            "Validated one",
        ]
        assert 'value="no" selected' not in response.content.decode()

    def test_archived_yes_shows_only_archived_analyses(self, client_with_admin, analyses):
        response = client_with_admin.get("/?archived=yes")

        assert titles(response) == ["Archived one"]
        assert 'value="yes" selected' in response.content.decode()

    def test_status_filter_is_any_of_the_selected_statuses(self, client_with_admin, analyses):
        response = client_with_admin.get("/?archived=&analysis_status=complete&analysis_status=validated")

        assert sorted(titles(response)) == ["Complete one", "Validated one"]

    def test_no_status_selected_adds_no_condition(self, client_with_admin, analyses):
        assert len(titles(client_with_admin.get("/?analysis_status="))) == 3

    def test_status_facet_has_checkboxes_and_an_apply_button(self, client_with_admin, analyses):
        content = client_with_admin.get("/").content.decode()
        status_facet = facet(content, "analysis_status")
        assert status_facet.count('type="checkbox"') == 3
        assert "Apply" in status_facet
        assert "Apply" not in facet(content, "archived")

    def test_sorting_follows_the_lifecycle_order_with_a_stable_tie_break(self, client_with_admin, defaults):
        second_complete = AnalysisFactory(lifecycle__analysis_status=AnalysisStatus.COMPLETE)
        validated = AnalysisFactory(lifecycle__analysis_status=AnalysisStatus.VALIDATED)
        in_progress = AnalysisFactory()
        first_complete = AnalysisFactory(lifecycle__analysis_status=AnalysisStatus.COMPLETE)

        ascending = client_with_admin.get("/?order_by=analysis_status")
        descending = client_with_admin.get("/?order_by=-analysis_status")

        assert [a.pk for a in ascending.context["object_list"]] == [
            in_progress.pk,
            second_complete.pk,
            first_complete.pk,
            validated.pk,
        ]
        assert [a.pk for a in descending.context["object_list"]] == [
            validated.pk,
            second_complete.pk,
            first_complete.pk,
            in_progress.pk,
        ]

    def test_sort_links_keep_every_parameter_and_restart_paging(self, client_with_admin, analyses):
        response = client_with_admin.get(
            "/?archived=&analysis_status=complete&analysis_status=validated&search=one&page=1"
        )

        link = sort_link(response.content.decode(), "analysis_status")
        assert "archived=&" in link or link.endswith("archived=")
        assert "analysis_status=complete" in link
        assert "analysis_status=validated" in link
        assert "search=one" in link
        assert "page=" not in link

    def test_page_links_keep_every_parameter(self, client_with_admin, defaults):
        Settings.objects.update(paginate_by=10)
        for _ in range(11):
            AnalysisFactory()

        response = client_with_admin.get("/?archived=&analysis_status=in_progress&search=")

        content = response.content.decode()
        match = re.search(r'href="(\?[^"]*page=2[^"]*)" class="pager__link"', content)
        assert match, "no link to page 2"
        link = match.group(1).replace("&amp;", "&")
        assert "archived=" in link
        assert "analysis_status=in_progress" in link

    def test_a_page_past_the_end_serves_the_last_page(self, client_with_admin, defaults):
        Settings.objects.update(paginate_by=10)
        for _ in range(11):
            AnalysisFactory()

        response = client_with_admin.get("/?page=5")

        assert response.status_code == 200
        assert response.context["page_obj"].number == 2
        assert len(response.context["object_list"]) == 1

    def test_encoded_search_terms_are_matched(self, client_with_admin, defaults):
        AnalysisFactory(title="Cash & Transfer")
        AnalysisFactory(title="Something else")

        response = client_with_admin.get("/?search=Cash+%26+Transfer")

        assert titles(response) == ["Cash & Transfer"]

    def test_rows_show_the_status_badge_and_the_archived_tag(self, client_with_admin, analyses):
        content = client_with_admin.get("/?archived=").content.decode()
        assert 'lifecycle-badge lifecycle-badge--validated">Validated<' in content
        assert 'lifecycle-badge lifecycle-badge--in_progress">In Progress<' in content
        assert content.count('class="lifecycle-tag">Archived<') == 1

    def test_title_opens_the_analysis_and_there_is_no_edit_link(self, client_with_admin, analyses):
        content = client_with_admin.get("/").content.decode()
        assert f'href="/analysis/{analyses["complete"].pk}/"' in content
        assert ">Edit<" not in content
        assert "dashboard__edit-link" not in content

    def test_admin_actions_menu(self, client_with_admin, analyses):
        content = client_with_admin.get("/?archived=").content.decode()
        active = analyses["complete"]
        archived = analyses["archived"]
        assert f'/analysis/{active.pk}/copy"' in content
        assert f'/analysis/{active.pk}/archive/"' in content
        assert f'/analysis/{archived.pk}/unarchive/"' in content
        assert content.count("actions-menu__item") >= 6  # Duplicate, Delete, Archive on every row
        assert content.count(">Delete<") == 4

    def test_basic_owner_sees_duplicate_and_archive_but_not_delete(self, client, defaults):
        analysis = AnalysisFactory()
        client.force_login(analysis.owner)

        content = client.get("/").content.decode()

        assert f'/analysis/{analysis.pk}/copy"' in content
        assert f'/analysis/{analysis.pk}/archive/"' in content
        assert ">Delete<" not in content

    def test_viewer_gets_no_actions_menu(self, client, defaults):
        analysis = AnalysisFactory()
        viewer = UserFactory()
        viewer.secondary_countries.add(analysis.country)
        client.force_login(viewer)

        content = client.get("/").content.decode()

        assert analysis.title in content
        assert "actions-menu" not in content
