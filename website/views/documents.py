import re
from datetime import datetime
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import redirect
from django.urls import reverse
from openpyxl import Workbook
from openpyxl.workbook.child import INVALID_TITLE_REGEX

from website.app_log import loggers as app_loggers
from website.models import Analysis, AnalysisCostType
from website.utils.documents import (
    _fill_in_cost_breakdown_functions,
    _fill_in_cost_efficiency_functions,
    _fill_in_subcomponent_cost_efficiency_functions,
    _formatting_pass,
    _write_cost_breakdown_table,
    _write_cost_efficiency_table,
    _write_cost_of_each_subcomponent_per_output_metric_table,
    _write_full_cost_model_table,
    _write_metadata_table,
    _write_other_cost_model_table,
)
from website.workflows import AnalysisWorkflow


@login_required
def full_cost_model_spreadsheet(request, pk):
    analysis = Analysis.objects.get(pk=pk)
    analysis_wf = AnalysisWorkflow(analysis)

    # If we aren't to the insights step we need to just redirect to the last valid step in the
    #   workflow and let the user fix things.  This is consistent with the other step views (even
    #   those this isn't a step)
    if not analysis_wf.get_step("insights").is_complete or not analysis.output_costs:
        return redirect(reverse("analysis", kwargs={"pk": analysis.pk}))

    app_loggers.log_analysis_cost_model_download(analysis, analysis.cost_line_items.count(), request.user)

    workbook = Workbook()

    # Remove the default sheet created
    workbook.remove(workbook.active)
    for each_intervention_instance in analysis.interventioninstance_set.all():
        fixed_title = re.sub(INVALID_TITLE_REGEX, " ", each_intervention_instance.display_name())
        # In the Excel spec Worksheet names cannot be longer than 30 characters.
        fixed_title = fixed_title[:30]

        worksheet = workbook.create_sheet(fixed_title)

        # Metadata Section
        parameter_metadata = {}
        last_metadata_row = _write_metadata_table(
            ws=worksheet,
            an_analysis=analysis,
            parameter_metadata=parameter_metadata,
            intervention_instance=each_intervention_instance,
        )

        row = last_metadata_row
        row += 2

        # Cost Efficiency Section
        metrics_all_costs_metadata = {}  # used to track references by the subcomponent formulas
        first_cost_efficiency_row = row
        last_cost_efficiency_row = _write_cost_efficiency_table(
            ws=worksheet,
            an_analysis=analysis,
            starting_row=first_cost_efficiency_row,
            metrics_all_costs_metadata=metrics_all_costs_metadata,
            intervention_instance=each_intervention_instance,
        )

        row = last_cost_efficiency_row
        row += 2

        first_subcomponent_analysis_cost_summary_row = None
        last_subcomponent_analysis_cost_summary_row = None
        # Subcomponent Analysis Costs Section
        if analysis.has_confirmed_subcomponent():
            first_subcomponent_analysis_cost_summary_row = row
            last_subcomponent_analysis_cost_summary_row = (
                _write_cost_of_each_subcomponent_per_output_metric_table(
                    ws=worksheet,
                    an_analysis=analysis,
                    starting_row=first_subcomponent_analysis_cost_summary_row,
                    intervention_instance=each_intervention_instance,
                )
            )
            row = last_subcomponent_analysis_cost_summary_row
            row += 2

        # Cost Breakdown Section
        direct_cost_rows = []
        first_cost_breakdown_row = row
        last_cost_breakdown_row = _write_cost_breakdown_table(
            worksheet,
            analysis,
            direct_cost_rows,
            first_cost_breakdown_row,
        )

        row = last_cost_breakdown_row
        row += 2

        first_full_cost_model_row = row
        last_full_cost_model_row = _write_full_cost_model_table(
            ws=worksheet,
            an_analysis=analysis,
            starting_row=first_full_cost_model_row,
            intervention_instance=each_intervention_instance,
        )

        row = last_full_cost_model_row
        row += 2

        other_cost_rows = {
            int(AnalysisCostType.IN_KIND): [],
            int(AnalysisCostType.CLIENT_TIME): [],
        }
        first_other_cost_model_row = row
        last_other_cost_model_row = _write_other_cost_model_table(
            worksheet,
            analysis,
            each_intervention_instance,
            other_cost_rows,
            first_other_cost_model_row,
        )

        _fill_in_cost_breakdown_functions(
            worksheet,
            first_cost_breakdown_row + 2,
            last_cost_breakdown_row,
            first_full_cost_model_row + 2,
            last_full_cost_model_row,
        )

        _fill_in_cost_efficiency_functions(
            ws=worksheet,
            an_analysis=analysis,
            intervention_instance=each_intervention_instance,
            parameter_metadata=parameter_metadata,
            direct_cost_rows=direct_cost_rows,
            other_cost_rows=other_cost_rows,
            full_cost_row=last_cost_breakdown_row,
            efficiency_row=first_cost_efficiency_row + 1,
        )

        if analysis.has_confirmed_subcomponent():
            _fill_in_subcomponent_cost_efficiency_functions(
                worksheet,
                metrics_all_costs_metadata,
                first_subcomponent_analysis_cost_summary_row + 1,
                last_subcomponent_analysis_cost_summary_row,
                first_full_cost_model_row + 2,
                last_full_cost_model_row,
            )

        _formatting_pass(worksheet)

    virtual_workbook = BytesIO()
    workbook.save(virtual_workbook)
    virtual_workbook.seek(0)
    response = FileResponse(
        virtual_workbook,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        filename=f'{analysis.title.lower().replace(" ", "")}-insights-{datetime.now():%Y%m%d-%H%M}.xlsx',
    )
    return response
