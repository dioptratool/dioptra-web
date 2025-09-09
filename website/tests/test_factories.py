import pytest

from website.models import (
    Analysis,
    AnalysisType,
    CostLineItem,
    Country,
    Intervention,
    InterventionGroup,
    Transaction,
)
from .factories import (
    AnalysisFactory,
    AnalysisTypeFactory,
    CostLineItemFactory,
    CountryFactory,
    InterventionFactory,
    InterventionGroupFactory,
    TransactionFactory,
)


@pytest.mark.django_db
def test_country_factory():
    m = CountryFactory(name="Test Country Name")
    assert m.name == "Test Country Name"
    assert Country.objects.count() == 1


@pytest.mark.django_db
def test_intervention_group_factory():
    m = InterventionGroupFactory(name="Test Intervention Group Name")
    assert m.name == "Test Intervention Group Name"
    assert InterventionGroup.objects.count() == 1


@pytest.mark.django_db
def test_analysis_type_factory():
    m = AnalysisTypeFactory(title="Test Analysis Type Title")
    assert m.title == "Test Analysis Type Title"
    assert AnalysisType.objects.count() == 1


@pytest.mark.django_db
def test_intervention_factory():
    m = InterventionFactory(name="Test Intervention Name")
    assert m.name == "Test Intervention Name"
    assert Intervention.objects.count() == 1
    assert InterventionGroup.objects.count() == 1


@pytest.mark.django_db
def test_analysis_factory():
    m = AnalysisFactory(title="Test Analysis Title")
    assert m.title == "Test Analysis Title"
    assert Analysis.objects.count() == 1
    assert AnalysisType.objects.count() == 1
    assert Intervention.objects.count() == 0
    assert Country.objects.count() == 1


@pytest.mark.django_db
def test_costlineitem_factory():
    m = CostLineItemFactory(grant_code="Test Cost Line Item Grant Code")
    assert m.grant_code == "Test Cost Line Item Grant Code"
    assert CostLineItem.objects.count() == 1
    assert Analysis.objects.count() == 1


@pytest.mark.django_db
def test_transaction_factory():
    TransactionFactory()
    assert Transaction.objects.count() == 1
