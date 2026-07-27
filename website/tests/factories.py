import datetime
from decimal import Decimal

import factory
from django.contrib.auth import get_user_model
from factory import LazyAttribute
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyDate
from faker import Faker

from website.help.models import HelpPage, HelpTopic
from website.models import (
    AccountCodeDescription,
    Analysis,
    AnalysisCostTypeCategory,
    AnalysisCostTypeCategoryGrant,
    AnalysisType,
    Category,
    CostLineItem,
    CostLineItemConfig,
    CostType,
    CostTypeCategoryMapping,
    Country,
    InsightComparisonData,
    Intervention,
    InterventionGroup,
    InterventionInstance,
    Region,
    SubcomponentCostAllocation,
    SubcomponentCostAnalysis,
    Transaction,
)
from website.models.cost_line_item import CostLineItemInterventionAllocation

fake = Faker()
Faker.seed(0)
User = get_user_model()


class AccountCodeDescriptionFactory(DjangoModelFactory):
    account_code = factory.Faker("word")
    account_description = factory.Faker("sentence")

    class Meta:
        model = AccountCodeDescription


class RegionFactory(DjangoModelFactory):
    name = factory.Faker("name")

    class Meta:
        model = Region


class CountryFactory(DjangoModelFactory):
    code = factory.Faker("country_code")

    class Meta:
        model = Country

    @factory.lazy_attribute
    def name(self):
        return fake.country() + fake.uuid4()


class InterventionGroupFactory(DjangoModelFactory):
    class Meta:
        model = InterventionGroup


class AnalysisTypeFactory(DjangoModelFactory):
    class Meta:
        model = AnalysisType


class AnalysisCostTypeCategoryFactory(DjangoModelFactory):
    class Meta:
        model = AnalysisCostTypeCategory


class AnalysisCostTypeCategoryGrantFactory(DjangoModelFactory):
    class Meta:
        model = AnalysisCostTypeCategoryGrant


class InterventionFactory(DjangoModelFactory):
    name = factory.Faker("name")
    group = factory.SubFactory(InterventionGroupFactory)
    description = factory.Faker("paragraph")

    class Meta:
        model = Intervention


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    name = factory.Sequence(lambda n: f"Rusty Shackleford{n}")
    email = factory.Sequence(lambda n: f"shackleford{n}@example.com")


class AnalysisFactory(DjangoModelFactory):
    analysis_type = factory.SubFactory(AnalysisTypeFactory)
    country = factory.SubFactory(CountryFactory)
    start_date = FuzzyDate(datetime.date(2010, 1, 1), datetime.date(2018, 12, 31))
    end_date = FuzzyDate(datetime.date(2019, 1, 1))
    owner = factory.SubFactory(UserFactory)

    class Meta:
        model = Analysis


class InterventionInstanceFactory(DjangoModelFactory):
    analysis = factory.SubFactory(AnalysisFactory)
    intervention = factory.SubFactory(InterventionFactory)

    class Meta:
        model = InterventionInstance


class CostTypeFactory(DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Test Cost Type {n}")

    class Meta:
        model = CostType


class CategoryFactory(DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Test Category {n}")

    class Meta:
        model = Category


class CostTypeCategoryMappingFactory(DjangoModelFactory):
    cost_type = LazyAttribute(lambda _: CostType.objects.get(default=True))
    category = factory.SubFactory(CategoryFactory)

    class Meta:
        model = CostTypeCategoryMapping


class CostLineItemFactory(DjangoModelFactory):
    total_cost = Decimal("100.01")
    analysis = factory.SubFactory(AnalysisFactory)
    quantity = 1
    grant_code = "Unknown"

    class Meta:
        model = CostLineItem


class CostLineItemConfigFactory(DjangoModelFactory):
    cost_line_item = factory.SubFactory(CostLineItemFactory)
    cost_type = LazyAttribute(lambda _: CostType.objects.get(default=True))
    category = factory.SubFactory(CategoryFactory)

    class Meta:
        model = CostLineItemConfig


class CostLineItemInterventionAllocationFactory(DjangoModelFactory):
    class Meta:
        model = CostLineItemInterventionAllocation


class TransactionFactory(DjangoModelFactory):
    date = FuzzyDate(datetime.date(2010, 1, 1))
    amount_in_instance_currency = Decimal("100.01")
    amount_in_source_currency = Decimal("100.01")
    analysis = factory.SubFactory(AnalysisFactory)

    class Meta:
        model = Transaction


class InsightComparisonDataFactory(DjangoModelFactory):
    class Meta:
        model = InsightComparisonData


class SubcomponentCostAnalysisFactory(DjangoModelFactory):
    subcomponent_labels = factory.LazyAttribute(lambda _: fake.words(nb=5))

    class Meta:
        model = SubcomponentCostAnalysis

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        analysis = kwargs.pop("analysis", None)
        if analysis is not None:
            intervention_instance = analysis.interventioninstance_set.first()
            if intervention_instance is None:
                intervention_instance = InterventionInstanceFactory(analysis=analysis)
            kwargs["intervention_instance"] = intervention_instance
        elif "intervention_instance" not in kwargs:
            kwargs["intervention_instance"] = InterventionInstanceFactory()
        return super()._create(model_class, *args, **kwargs)


class SubcomponentCostAllocationFactory(DjangoModelFactory):
    subcomponent_analysis = factory.SubFactory(SubcomponentCostAnalysisFactory)
    cli_config = factory.SubFactory(CostLineItemConfigFactory)
    allocations = factory.LazyAttribute(lambda _: {"0": "100"})

    class Meta:
        model = SubcomponentCostAllocation


class HelpTopicFactory(DjangoModelFactory):
    title = factory.Faker("word")

    class Meta:
        model = HelpTopic


class HelpPageFactory(DjangoModelFactory):
    title = factory.Faker("sentence")
    body = factory.Faker("paragraph")
    topic = factory.SubFactory(HelpTopicFactory)

    class Meta:
        model = HelpPage
