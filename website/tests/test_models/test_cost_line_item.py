import pytest

from website.tests.factories import (
    CostLineItemConfigFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionInstanceFactory,
)


@pytest.mark.django_db
class TestGetSoleAllocatorName:
    def test_returns_empty_string_without_any_allocation(self, defaults):
        config = CostLineItemConfigFactory()

        assert config.get_sole_allocator_name == ""

    def test_returns_empty_string_without_a_full_allocation(self, defaults):
        config = CostLineItemConfigFactory()
        instance = InterventionInstanceFactory(analysis=config.cost_line_item.analysis)
        CostLineItemInterventionAllocationFactory(
            cli_config=config,
            intervention_instance=instance,
            allocation=50,
        )

        assert config.get_sole_allocator_name == ""

    def test_returns_display_name_for_full_allocation(self, defaults):
        config = CostLineItemConfigFactory()
        instance = InterventionInstanceFactory(analysis=config.cost_line_item.analysis)
        CostLineItemInterventionAllocationFactory(
            cli_config=config,
            intervention_instance=instance,
            allocation=100,
        )

        assert config.get_sole_allocator_name == instance.display_name()
