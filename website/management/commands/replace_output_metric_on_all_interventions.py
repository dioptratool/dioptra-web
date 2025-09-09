import sys

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from website.models import Analysis, InsightComparisonData, Intervention
from website.models.output_metric import OUTPUT_METRICS_BY_ID
from website.workflows import AnalysisWorkflow


class Command(BaseCommand):
    """
    A management command that replaces an Output Metric with a
    new one on all InterventionInstances for a given Intervention on
    all Analyses preserving the Parameters where we can
    """

    help = "Replaces all Output Metric for an Intervention and preserve the Parameters"

    def add_arguments(self, parser):
        parser.add_argument(
            "intervention_name",
            type=str,
            help='Name of the Intervention (i.e. "Access to Sanitation") to be updated.   '
            "All InterventionInstances on all Analyses will be updated with the new Output Metric.",
        )
        parser.add_argument(
            "old_metric_id",
            type=str,
            help="Original Output Metric ID (i.e. NumberOfGroups, NumberOfPersonYearsOfSanitationAccess)",
        )
        parser.add_argument(
            "new_metric_id",
            type=str,
            help="Replacement Output Metric ID (i.e. NumberOfGroups, NumberOfPersonYearsOfSanitationAccess)",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help="Suppress confirmation prompt and proceed with replacement.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("backup_analysis_dates")

        intervention_name = options["intervention_name"]
        orig_metric_id = options["old_metric_id"]
        new_metric_id = options["new_metric_id"]
        force = options["force"]

        try:
            intervention = Intervention.objects.get(name=intervention_name)
        except Intervention.DoesNotExist:
            raise CommandError(f"Intervention with ID {intervention_name} does not exist.")

        try:
            old_metric_class = OUTPUT_METRICS_BY_ID[orig_metric_id]
        except KeyError:
            raise CommandError(
                f"Output Metric with ID: '{orig_metric_id}' not found in OUTPUT_METRICS_BY_ID."
            )

        try:
            new_metric_class = OUTPUT_METRICS_BY_ID[new_metric_id]
        except KeyError:
            raise CommandError(f"Output Metric with ID: '{new_metric_id}' not found in OUTPUT_METRICS_BY_ID.")

        relevant_analyses = Analysis.objects.filter(interventioninstance__intervention=intervention)

        self.stdout.write(
            f"This script will replace the Output Metric parameters on {relevant_analyses.count()} Analyses.\n"
            f"This will replace the Output Metric "
            f"'{orig_metric_id}' with '{new_metric_id}' on all Analyses."
        )

        if len(old_metric_class.parameters) != len(new_metric_class.parameters):
            sys.stdout.write(
                self.style.WARNING(
                    f"⚠️WARNING:  The number of parameters for the original Output Metric ({len(old_metric_class.parameters)}) "
                    f"does not match the number of parameters for the new Output Metric ({len(new_metric_class.parameters)})\n"
                )
            )

        original_parameters = list(old_metric_class.parameters)
        new_parameters = list(new_metric_class.parameters)
        replacement_strategy = {}

        for i, parameter_name in enumerate(original_parameters):
            try:
                replacement_strategy[parameter_name] = new_parameters[i]
            except IndexError:
                pass

        if len(new_parameters) > len(original_parameters):
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️ No value to map to the new Parameters: ({new_parameters[len(original_parameters):]}).\n"
                    f"⚠️The values for these new parameters will be blank.\n"
                )
            )

        if len(original_parameters) > len(new_parameters):
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️Discarding the following parameters: original parameters: {original_parameters[len(new_parameters):]}"
                )
            )

        formatted_replacement_strategy = "".join([f"\t{k} -> {v}\n" for k, v in replacement_strategy.items()])

        self.stdout.write(
            self.style.SUCCESS(
                f"The following parameters will be replaced:\n {formatted_replacement_strategy}"
            )
        )

        if not force:
            self.stdout.write(self.style.WARNING("WARNING: This operation will affect data irreversibly."))
            self.stdout.write("Do you wish to proceed? [y/N] ", ending="")

            choice = input().strip().lower()

            if choice != "y":
                self.stdout.write(self.style.WARNING("Operation canceled."))
                return
        self.stdout.flush()
        try:
            idx = intervention.output_metrics.index(orig_metric_id)
            intervention.output_metrics[idx] = new_metric_id
            intervention.save()
        except ValueError:
            raise CommandError(
                f"❌This Intervention does not have the specified Output Metric: {orig_metric_id}."
            )

        updated_count = 0
        updated_analyses = []
        relevant_analyses = Analysis.objects.filter(interventioninstance__intervention=intervention)
        for analysis in relevant_analyses:
            for each_intervention in analysis.interventioninstance_set.filter(intervention=intervention):
                updated_count += 1
                updated_analyses.append(analysis.id)
                new_params = {}
                for each_parameter, value in each_intervention.parameters.items():
                    if value is None:
                        continue
                    if each_parameter in replacement_strategy:
                        new_params[replacement_strategy[each_parameter]] = value
                    else:
                        new_params[each_parameter] = value
                each_intervention.parameters = new_params
                each_intervention.save()
            wf = AnalysisWorkflow(analysis)
            wf.calculate_if_possible()

        updated_insight_comparison_count = 0
        for each_insight_comparison_data in InsightComparisonData.objects.all():
            if each_insight_comparison_data.intervention.name != intervention_name:
                continue

            updated_insight_comparison_count += 1
            new_output_costs = {}
            old_output_costs = each_insight_comparison_data.output_costs

            output_metrics = old_output_costs.keys()

            for each_output_metric in output_metrics:
                if each_output_metric == orig_metric_id:

                    new_parameter_info = {}
                    old_parameter_info = each_insight_comparison_data.parameters
                    for k, v in old_parameter_info.items():
                        if k in replacement_strategy:
                            new_parameter_info[replacement_strategy[k]] = v
                        else:
                            new_parameter_info[k] = v
                    each_insight_comparison_data.parameters = new_parameter_info
                    each_insight_comparison_data.save()

            for k, v in old_output_costs.items():
                if k == orig_metric_id:

                    new_output_costs[new_metric_id] = v
                else:
                    new_output_costs[k] = v

            each_insight_comparison_data.output_costs = new_output_costs
            each_insight_comparison_data.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"✅Updated {updated_count} Intervention Instances on Analyses. {updated_analyses}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"✅Updated {updated_insight_comparison_count} Insight Comparion Data objects."
            )
        )
        call_command("backup_analysis_dates", "--restore")
