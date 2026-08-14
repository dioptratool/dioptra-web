import pytest
from django.conf import settings

from website.models import CostType
from website.models.cost_type import ProgramCost, Support


@pytest.mark.django_db
class TestCostTypeDefaultRestore:
    def test_save_restores_default_by_configured_name(self, defaults):
        CostType.objects.update(default=False)

        CostType.objects.get(type=Support.id).save()

        assert CostType.objects.get(default=True).name == settings.DEFAULT_COST_TYPE

    def test_save_restores_default_by_type_after_rename(self, defaults):
        # Admins can rename cost types; a rename must not break the default
        # restoration (previously a name-based get() raised DoesNotExist).
        for cost_type in CostType.objects.all():
            CostType.objects.filter(pk=cost_type.pk).update(name=cost_type.name.rstrip("s"))
        CostType.objects.update(default=False)

        CostType.objects.get(type=Support.id).save()

        assert CostType.objects.get(default=True).type == ProgramCost.id
