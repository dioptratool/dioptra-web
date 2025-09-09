from django import forms

from website.models import Category, CostLineItem, CostType


class CostLineItemNoteForm(forms.ModelForm):
    class Meta:
        model = CostLineItem
        fields = ["note"]


class CostLineItemCostTypeCategoryForm(forms.Form):
    cost_type_id = forms.IntegerField()
    category_id = forms.IntegerField()

    def clean_cost_type_id(self):
        pk = self.cleaned_data["cost_type_id"]
        if not CostType.objects.filter(pk=pk).exists():
            raise forms.ValidationError("No matching CostType found.")
        return pk

    def clean_category_id(self):
        pk = self.cleaned_data["category_id"]
        if not Category.objects.filter(pk=pk).exists():
            raise forms.ValidationError("No matching Category found.")
        return pk
