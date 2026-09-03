"""website URL Configuration"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from website.admin.app_log import SendPendingNotificationsView
from website.admin.category import CategorySetDefaultView
from website.admin.cost_type_category_mapping import (
    ExportCostTypeCategoryMapping,
    UploadCostTypeCategoryPanel,
)
from website.admin.country import UploadCountriesPanel
from website.admin.insight_comparison_data import UploadInsightComparisonDataPanel
from website.admin.subcomponent_analysis import SubcomponentsDeleteView
from website.help import views as help_views
from website.users.views import AdminLoginView, CustomPasswordResetFromKeyView
from website.views import intervention
from website.views import logout
from website.views import styleguide
from website.views.analysis.corrections import (
    AllocationChangesPromptPanel,
    CorrectionSelectionCreate,
    CostItemCorrectionPanel,
    TransactionCorrectionPanel,
)
from website.views.analysis.analysis import (
    AnalysisDetailView,
    AnalysisLessonsEditorView,
    CostLineItemTransactions,
    CostLineItemUpsertView,
    GrantCategoryHelp,
    SaveSuggestedToAllConfirmView,
)
from website.views.analysis.steps.add_other_costs import (
    AddOtherCosts,
    AddOtherCostsDetail,
)
from website.views.analysis.steps.allocate import (
    Allocate,
    AllocateCostTypeGrant,
    AllocateInterventionBulk,
    AllocateSupportingCosts,
)
from website.views.analysis.steps.allocate_subcomponents import (
    AllocateSubcomponents,
    AllocateSubcomponentsBulk,
    AllocateSubcomponentsInterventionGrant,
)
from website.views.analysis.steps.categorize import Categorize
from website.views.analysis.steps.categorize_cost_type import CategorizeCostType
from website.views.analysis.steps.define import (
    DefineCreate,
    DefineUpdate,
)
from website.views.analysis.steps.insights import Insights, InsightsPrint
from website.views.analysis.steps.load_data import (
    BudgetTemplateDownload,
    LoadData,
    TransactionTemplateDownload,
)
from website.views.dashboard import DashboardView
from website.views.documents import full_cost_model_spreadsheet
from website.views.duplicator import DuplicateView
from website.views.analysis.steps.interventions import (
    EditSubcomponentLabel,
    Interventions,
    InterventionSubcomponentLabels,
    InterventionSubcomponentLabelsDelete,
)

urlpatterns = [
    path(
        "",
        DashboardView.as_view(),
        name="dashboard",
    ),
    path(
        "panels/website/category/default",
        CategorySetDefaultView.as_view(),
        name="category-set-default",
    ),
    path(
        "panels/website/costtype_category_mapping/upload",
        UploadCostTypeCategoryPanel.as_view(),
        name="upload-cost-type-category-mapping-panel",
    ),
    path(
        "panels/website/costtype_category_mapping/export",
        ExportCostTypeCategoryMapping.as_view(),
        name="export-cost-type-category-mapping",
    ),
    path(
        "panels/website/insight_comparison_data/upload",
        UploadInsightComparisonDataPanel.as_view(),
        name="upload-insight-comparison-data-panel",
    ),
    path(
        "panels/website/country/upload",
        UploadCountriesPanel.as_view(),
        name="upload-countries-panel",
    ),
    # Analysis.
    path(
        "analysis/define/",
        DefineCreate.as_view(),
        name="analysis-define-create",
    ),
    path(
        "subcomponents/label/change/<int:label_idx>/<path:label>",
        EditSubcomponentLabel.as_view(),
        name="subcomponent-label-edit-label",
    ),
    path(
        "analysis/<int:pk>/",
        AnalysisDetailView.as_view(),
        name="analysis",
    ),
    path(
        "analysis/<int:pk>/define/",
        DefineUpdate.as_view(),
        name="analysis-define-update",
    ),
    path(
        "analysis/<int:pk>/interventions/",
        Interventions.as_view(),
        name="analysis-interventions",
    ),
    path(
        "analysis/<int:pk>/interventions/<int:instance_pk>/subcomponent-labels/",
        InterventionSubcomponentLabels.as_view(),
        name="analysis-interventions-subcomponent-labels",
    ),
    path(
        "analysis/<int:pk>/interventions/<int:instance_pk>/subcomponent-labels/delete/",
        InterventionSubcomponentLabelsDelete.as_view(),
        name="analysis-interventions-subcomponent-labels-delete",
    ),
    path(
        "analysis/<int:pk>/load-data/",
        LoadData.as_view(),
        name="analysis-load-data",
    ),
    path(
        "analysis/<int:pk>/load-data/budget-template/",
        BudgetTemplateDownload.as_view(),
        name="budget-template-download",
    ),
    path(
        "analysis/<int:pk>/load-data/transaction-template/<str:template_id>/",
        TransactionTemplateDownload.as_view(),
        name="transaction-template-download",
    ),
    path(
        "analysis/<int:pk>/categorize/",
        Categorize.as_view(),
        name="analysis-categorize",
    ),
    path(
        "analysis/<int:pk>/categorize/<int:cost_type_pk>/",
        CategorizeCostType.as_view(),
        name="analysis-categorize-cost_type",
    ),
    # In-app corrections (Feature 91): selection token, then the edit panels.
    path(
        "analysis/<int:pk>/corrections/selection/",
        CorrectionSelectionCreate.as_view(),
        name="analysis-correction-selection",
    ),
    path(
        "analysis/<int:pk>/corrections/unsaved-allocations/",
        AllocationChangesPromptPanel.as_view(),
        name="analysis-correction-unsaved-prompt",
    ),
    path(
        "analysis/<int:pk>/corrections/<str:step>/transactions/",
        TransactionCorrectionPanel.as_view(),
        name="analysis-correct-transactions",
    ),
    path(
        "analysis/<int:pk>/corrections/<str:step>/cost-items/",
        CostItemCorrectionPanel.as_view(),
        name="analysis-correct-cost-items",
    ),
    path(
        "analysis/<int:pk>/allocate/",
        Allocate.as_view(),
        name="analysis-allocate",
    ),
    path(
        "analysis/<int:pk>/allocate/<int:cost_type_pk>/<path:grant>/save-suggested/",
        SaveSuggestedToAllConfirmView.as_view(),
        name="analysis-allocate-cost_type-grant--save-suggested",
    ),
    # NOTE: bulk routes must precede the `<path:grant>` catch-alls below.
    path(
        "analysis/<int:pk>/allocate/<int:cost_type_pk>/<path:grant>/bulk/",
        AllocateInterventionBulk.as_view(),
        name="analysis-allocate-cost_type-grant-bulk",
    ),
    path(
        "analysis/<int:pk>/allocate/<int:cost_type_pk>/<path:grant>/",
        AllocateCostTypeGrant.as_view(),
        name="analysis-allocate-cost_type-grant",
    ),
    path(
        "analysis/<int:pk>/allocate/<path:grant>/other-costs/",
        AllocateSupportingCosts.as_view(),
        name="analysis-allocate-supporting-costs",
    ),
    path(
        "analysis/<int:pk>/allocate-subcomponents/",
        AllocateSubcomponents.as_view(),
        name="analysis-allocate-subcomponents",
    ),
    path(
        "analysis/<int:pk>/allocate-subcomponents/<int:intervention_instance_pk>/<path:grant>/bulk/",
        AllocateSubcomponentsBulk.as_view(),
        name="analysis-allocate-subcomponents-intervention-grant-bulk",
    ),
    path(
        "analysis/<int:pk>/allocate-subcomponents/<int:intervention_instance_pk>/<path:grant>/",
        AllocateSubcomponentsInterventionGrant.as_view(),
        name="analysis-allocate-subcomponents-intervention-grant",
    ),
    path(
        "analysis/<int:pk>/add-other-costs/",
        AddOtherCosts.as_view(),
        name="analysis-add-other-costs",
    ),
    path(
        "analysis/<int:pk>/add-other-costs/<int:cost_type>",
        AddOtherCostsDetail.as_view(),
        name="analysis-add-other-costs-detail",
    ),
    path(
        "analysis/<int:pk>/insights/",
        Insights.as_view(),
        name="analysis-insights",
    ),
    path(
        "analysis/<int:pk>/lesson/<str:lesson_field>",
        AnalysisLessonsEditorView.as_view(),
        name="analysis-insights-lesson-editor",
    ),
    path(
        "analysis/<int:pk>/insights/print/",
        InsightsPrint.as_view(),
        name="analysis-insights-print",
    ),
    path(
        "analysis/<int:pk>/download",
        full_cost_model_spreadsheet,
        name="analysis-cost-model-spreadsheet",
    ),
    path(
        "analysis/<int:pk>/copy",
        DuplicateView.as_view(),
        name="analysis-create-copy",
    ),
    path(
        "panels/analysis/<int:pk>/subcomponent_cost_analysis/<int:subcomponent_pk>/delete/",
        SubcomponentsDeleteView.as_view(),
        name="subcomponent-cost-analysis-delete",
    ),
    path(
        "grant/<int:pk>/category-help/",
        GrantCategoryHelp.as_view(),
        name="grant-category-help",
    ),
    path(
        "cost-line-item/<int:pk>/transactions/",
        CostLineItemTransactions.as_view(),
        name="cost-line-item-transactions",
    ),
    path(
        "analysis/<int:pk>/cost-line-item/other-cost/<int:cost_type>",
        CostLineItemUpsertView.as_view(),
        name="cost-line-item-create",
    ),
    path(
        "analysis/<int:pk>/cost-line-item/<int:cost_pk>/other-cost/<int:cost_type>",
        CostLineItemUpsertView.as_view(),
        name="cost-line-item-update",
    ),
    path(
        "intervention/<int:pk>/",
        intervention.InterventionInsights.as_view(),
        name="intervention-insights",
    ),
    path(
        "styleguide/",
        styleguide.styleguidetoc,
        name="styleguidetoc",
    ),
    path(
        "styleguide/colors/",
        styleguide.styleguidecolors,
        name="styleguidecolors",
    ),
    path(
        "styleguide/typography/",
        styleguide.styleguidetypography,
        name="styleguidetypography",
    ),
    path(
        "styleguide/rte/",
        styleguide.styleguiderte,
        name="styleguiderte",
    ),
    path(
        "styleguide/forms/",
        styleguide.styleguideforms,
        name="styleguideforms",
    ),
    path(
        "styleguide/buttons-links/",
        styleguide.styleguidebuttons,
        name="styleguidebuttons",
    ),
    path(
        "help/",
        help_views.help_menu,
        name="help-menu",
    ),
    path(
        "help/<path:path>/",
        help_views.help_page,
        name="help-page",
    ),
    path(
        "panels/app_log/send-notifications/",
        SendPendingNotificationsView.as_view(),
        name="send-notification-subscriptions",
    ),
    # Authentication
    re_path(
        r"^accounts/password/reset/key/(?P<uidb36>[0-9A-Za-z]+)-(?P<key>.+)/$",
        CustomPasswordResetFromKeyView.as_view(),
        name="account_reset_password_from_key",
    ),
    path(
        "accounts/",
        include("website.email_2fa.urls"),
    ),
    path(
        "accounts/",
        include("allauth.urls"),
    ),
    path(
        "accounts/adminlogin/",
        AdminLoginView.as_view(),
        name="adminlogin",
    ),
    # These views are handled by django-allauth so we redirect rather than using Ombucore
    path(
        "login/",
        RedirectView.as_view(url="/accounts/login/"),
    ),
    path(
        "password-reset/",
        RedirectView.as_view(url="/accounts/password/reset/"),
    ),
    path(
        "password-reset/done/",
        RedirectView.as_view(url="/accounts/password/reset/done/"),
    ),
    path(
        "reset/done/",
        RedirectView.as_view(url="/accounts/password/reset/done/"),
    ),
    path(
        "logout/",
        logout.LogoutView.as_view(),
        name="account_logout",
    ),
    # API
    path("api/", include("website.api.urls")),
    path("", include("ombucore.urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
        path("admin/", admin.site.urls),
    ]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
