from django.urls import path

from .views import (
    CostLineItemAddNoteView,
    CostLineItemUpdateCostTypeCategoryView,
)

urlpatterns = [
    path(
        "cost_line_item/<int:pk>/add_note/",
        CostLineItemAddNoteView.as_view(),
        name="api--costlineitem--add-note",
    ),
    path(
        "cost_line_item/<int:pk>/update_cost_type_and_category/",
        CostLineItemUpdateCostTypeCategoryView.as_view(),
        name="api--costlineitem--edit-cost_type-category",
    ),
]
