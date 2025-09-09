import pytest

from website.tests.factories import AnalysisFactory, HelpPageFactory, HelpTopicFactory, InterventionFactory


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
