import pytest
from django.conf import settings

from website.models import Category, CostLineItem, CostType, CostTypeCategoryMapping
from website.tests.factories import (
    CategoryFactory,
    CostLineItemFactory,
    CostTypeCategoryMappingFactory,
    CostTypeFactory,
)


@pytest.mark.django_db
@pytest.mark.usefixtures("defaults")
class TestCostTypeCategoryMapping:
    def test_map_by_country_code(self):
        cost_line_item = CostLineItemFactory(
            country_code="5JO",
        )

        first_mapping = CostTypeCategoryMappingFactory(
            country_code="5JO",
            category=None,
            cost_type=CostType.objects.get(name=settings.DEFAULT_COST_TYPE),
        )

        CostTypeCategoryMapping.auto_categorize_cost_line_items(CostLineItem.objects.all())
        assert cost_line_item.config.cost_type == first_mapping.cost_type
        assert cost_line_item.config.category == Category.get_default()

    def test_map_separate_cost_type_and_category(self):
        cost_line_item = CostLineItemFactory(country_code="5JO")
        first_mapping = CostTypeCategoryMappingFactory(country_code="5JO", category=None)
        second_mapping = CostTypeCategoryMappingFactory(country_code="5JO", cost_type=None)

        CostTypeCategoryMapping.auto_categorize_cost_line_items(CostLineItem.objects.all())

        assert cost_line_item.config.cost_type == first_mapping.cost_type
        assert cost_line_item.config.category == second_mapping.category

    def test_map_generic_to_specific(self):
        cost_line_item = CostLineItemFactory(country_code="5JO", grant_code="DF119")
        first_mapping = CostTypeCategoryMappingFactory(
            country_code="5JO",
            category=None,
        )
        second_mapping = CostTypeCategoryMappingFactory(
            country_code="5JO",
            grant_code="DF119",
            category=None,
        )

        CostTypeCategoryMapping.auto_categorize_cost_line_items(CostLineItem.objects.all())
        assert cost_line_item.config.cost_type == second_mapping.cost_type
        assert cost_line_item.config.category == Category.get_default()

    def test_map_unknown_to_defaults(self):
        cost_line_item = CostLineItemFactory(country_code="HONK", grant_code="DF119")
        CostTypeCategoryMapping.auto_categorize_cost_line_items(CostLineItem.objects.all())

        assert cost_line_item.config.category == Category.get_default()
        assert cost_line_item.config.cost_type == CostType.get_default()

    def test_map_unknown_to_defaults_just_category(self):
        cost_line_item = CostLineItemFactory(country_code="5JO", grant_code="DF119")
        first_mapping = CostTypeCategoryMappingFactory(country_code="5JO", category=None)

        CostTypeCategoryMapping.auto_categorize_cost_line_items(CostLineItem.objects.all())

        assert cost_line_item.config.category == Category.get_default()
        assert cost_line_item.config.cost_type == first_mapping.cost_type

    def test_map_unknown_to_defaults_just_cost_type(self):
        cost_line_item = CostLineItemFactory(country_code="5JO", grant_code="DF119")
        first_mapping = CostTypeCategoryMappingFactory(country_code="5JO", cost_type=None)

        CostTypeCategoryMapping.auto_categorize_cost_line_items(CostLineItem.objects.all())

        assert cost_line_item.config.category == first_mapping.category
        assert cost_line_item.config.cost_type == CostType.get_default()


class TestDefaultCategories:
    @pytest.mark.django_db
    def test_single_default(self):
        # Ensure there's at least one default category
        default_category = CategoryFactory(name="Default Category", default=True)
        other_category = CategoryFactory(name="Other Category")

        # There should be only one default category
        assert Category.objects.filter(default=True).count() == 1
        assert Category.get_default() == default_category

        # Setting another category as default
        other_category.default = True
        other_category.save()

        # Ensure the new default is set and the old one is unset
        assert Category.objects.filter(default=True).count() == 1
        assert Category.get_default() == other_category

        # Ensure the original default is no longer default
        default_category.refresh_from_db()
        assert not default_category.default

    @pytest.mark.django_db
    def test_no_default(self):
        # Create categories without setting any as default but ensuring one has the name of the Default category
        CategoryFactory(name=settings.DEFAULT_CATEGORY)
        CategoryFactory(name="Category 2")

        # Manually unset the default
        Category.objects.filter(default=True).update(default=False)

        # Save a new category as the default
        new_category = CategoryFactory(name="Category 3", default=True)
        new_category.save()

        assert Category.objects.filter(default=True).count() == 1
        assert Category.get_default() == new_category

    @pytest.mark.django_db
    def test_default_restored(self):
        # Create and unset the default category
        default_category = CategoryFactory(name=settings.DEFAULT_CATEGORY, default=True)
        default_category.default = False
        default_category.save()

        # Ensure no default exists.  This is an ERROR STATE but the system will self-repair
        Category.objects.filter(default=True).update(default=False)
        assert Category.objects.filter(default=True).count() == 0

        # Save a new category and ensure it restores the default
        new_category = CategoryFactory(name="Category 3", default=False)
        new_category.save()

        default_category.refresh_from_db()
        assert default_category.default
        assert Category.objects.filter(default=True).count() == 1
        assert Category.get_default() == default_category


class TestDefaultCostTypes:
    @pytest.mark.django_db
    def test_single_default(self):
        # Ensure there's at least one default cost type
        default_cost_type = CostTypeFactory(name="Program Cost", default=True, type=10)
        other_cost_type = CostTypeFactory(name="Other Cost Type", type=20)

        # There should be only one default cost type
        assert CostType.objects.filter(default=True).count() == 1
        assert CostType.get_default() == default_cost_type

        # Setting another category as default
        other_cost_type.default = True
        other_cost_type.save()

        # Ensure the new default is set and the old one is unset
        assert CostType.objects.filter(default=True).count() == 1
        assert CostType.get_default() == other_cost_type

        # Ensure the original default is no longer default
        default_cost_type.refresh_from_db()
        assert not default_cost_type.default

    @pytest.mark.django_db
    def test_no_default(self):
        # Create categories without setting any as default but ensuring one has the name of the Default cost type
        CostTypeFactory(name=settings.DEFAULT_COST_TYPE, type=10)
        CostType(name="Cost Type 2")

        # Manually unset the default
        CostType.objects.filter(default=True).update(default=False)

        # Save a new cost type as the default
        new_cost_type = CostTypeFactory(name="Category 3", default=True, type=20)
        new_cost_type.save()

        assert CostType.objects.filter(default=True).count() == 1
        assert CostType.get_default() == new_cost_type
