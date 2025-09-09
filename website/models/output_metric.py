import re
from inspect import getsourcelines

from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from website.forms.fields import PositiveFixedDecimalField
from website.models.decorators import check_zero_args


def _get_source_ignoring_decorators(func, **kwargs):
    # Get the source lines and starting line number
    source_lines, starting_line_no = getsourcelines(func)

    # Initialize an index to find the start of the function definition
    index = 0

    # Skip over decorator lines
    for i, line in enumerate(source_lines):
        if line.strip().startswith("def "):
            index = i
            break

    # Return the source lines starting from the function definition
    return source_lines[index:], starting_line_no + index


class OutputMetric:
    output_name: str | None = None
    output_unit: str | None = None
    output_as_currency: bool | None = False
    metric_name: str | None = None
    metric_equation: str | None = None
    parameters: dict[str, PositiveFixedDecimalField] = {}

    @property
    def id(self) -> str:
        return self.__class__.__name__

    def __str__(self) -> str:
        return str(self.output_name)

    def get_slug(self) -> str:
        return slugify(str(self.output_name))

    def calculate(self, *args, **kwargs):
        pass

    def total_output(self, **kwargs):
        """
        Override this method for any OutputMetric with more than one parameter!

        When we are dealing with a single parameter it is fine to return it unchanged
          but if we have more than one in the OutputMetric.parameters some math should
          be done to make sure we are returning the actual total output.
        """
        if len(self.parameters) > 1:
            raise NotImplementedError(
                "This method must be overwritten for Output Metrics with more than 1 parameter"
            )

        for k, v in kwargs.items():
            if k in self.parameters.keys():
                return v
        # TODO This is commented out as it is useful and "Correct" but there are cases (involving InsightComparisonData)
        #   that we are unable to differentiate where parameters will be missing
        # raise ValueError(
        #     f"No matching parameters found for this OutputMetric ({self.metric_name}).   Expected: {list(self.parameters.keys())}  Got: {list(kwargs.keys())}"
        # )

    @classmethod
    def convert_calculate_to_excel_formula(cls, param_to_excel_map):
        """
        Intake a dictionary containing each parameter and its corresponding Excel expression, i.e.
        {
            "cost_output_sum": "SUM(B20, B21, B22)",
            "value_items_distributed": "C10"
        }
        And return the "calculate" method in Excel format based on the above mapping.  If a result cannot be parsed,
        this function will simply return None

        LIMITATIONS INCLUDE
            - "calculate" method on Metric must be a simple, arithmetic statement including no builtins/custom functions
        """
        # Verify that all metric parameters are included in the incoming param_to_excel_map
        if any([param not in param_to_excel_map for param in cls.parameters]):
            return

        # Run inspect method to convert function to a list of strings, one item for each line
        calculate_equation = cls.calculate
        equation_lines, _ = _get_source_ignoring_decorators(calculate_equation)

        # Find the line where the return statement starts
        # "return " is a reserved statement and should be a reliable locator
        start_index = None
        for i, eq_line in enumerate(equation_lines):
            cleaned_eq_line = re.sub(r"\t\r\n", "", eq_line).strip()
            if cleaned_eq_line.startswith("return "):
                start_index = i
                break
        if start_index is None:
            return

        # Remove all new lines, tabs, etc.
        cleaned_lines = [re.sub(r"\t\r\n", "", line).strip() for line in equation_lines[start_index:]]
        equation_str = "".join(cleaned_lines)

        # Get rid of the word "return" at the start of the string
        equation_str = equation_str[6:].strip()

        # Verify that the remaining equation_str only contains expected parameters
        parameter_variables = list(param_to_excel_map.keys())
        equation_variables = re.findall(r"\b\w+\b", equation_str)
        invalid_variables = list(set(equation_variables).difference(parameter_variables))
        if invalid_variables:
            return

        # Substitute each parameter with its corresponding Excel value
        for param, excel_value in param_to_excel_map.items():
            equation_str = equation_str.replace(param, excel_value)

        # # Wrap in a check for division by zero:
        # This is the ideal version but only works on modern Excel
        # equation_str = f'IF(ERROR.TYPE({equation_str})=2, "Error: Division by zero", {equation_str})'

        equation_str = f"IFERROR({equation_str}, 0)"

        return equation_str


class NumberOfPeople(OutputMetric):
    output_name = _("Number of People")
    output_unit = _("People")
    metric_name = _("Cost Per Person")
    metric_equation = "cost_output_sum / number_of_people"
    parameters = {"number_of_people": PositiveFixedDecimalField(label=_("Number of People"))}

    def calculate(
        self,
        cost_output_sum,
        number_of_people,
        **kwargs,
    ):
        return cost_output_sum / number_of_people


class NumberOfPersonYearsOfWaterAccess(OutputMetric):
    output_name = _("Number of Person-Years of Water Access")
    output_unit = _("Person-Years of Water Access")
    metric_name = _("Cost per Person per Year of Water Access")
    metric_equation = "cost_output_sum / (number_of_people * number_of_years_of_water_access)"
    parameters = {
        "number_of_people": PositiveFixedDecimalField(label=_("Number of People")),
        "number_of_years_of_water_access": PositiveFixedDecimalField(
            label=_("Number of Years of Water Access")
        ),
    }

    def calculate(
        self,
        cost_output_sum,
        number_of_people,
        number_of_years_of_water_access,
        **kwargs,
    ):
        return cost_output_sum / (number_of_people * number_of_years_of_water_access)

    def total_output(self, number_of_people=0, number_of_years_of_water_access=0):
        return number_of_people * number_of_years_of_water_access


class NumberOfPersonYearsOfSanitationAccess(OutputMetric):
    output_name = _("Number of Person-Years of Sanitation Access")
    output_unit = _("Person-Years of Sanitation Access")
    metric_name = _("Cost per Person per Year of Sanitation Access")
    metric_equation = "cost_output_sum / (number_of_people * number_of_years_a_latrine_can_last)"
    parameters = {
        "number_of_people": PositiveFixedDecimalField(label=_("Number of People Served")),
        "number_of_years_a_latrine_can_last": PositiveFixedDecimalField(
            label=_("Number of Years a Latrine Can Last")
        ),
    }

    def calculate(
        self,
        cost_output_sum,
        number_of_people,
        number_of_years_a_latrine_can_last,
        **kwargs,
    ):
        return cost_output_sum / (number_of_people * number_of_years_a_latrine_can_last)

    def total_output(self, number_of_people=0, number_of_years_a_latrine_can_last=0):
        return number_of_people * number_of_years_a_latrine_can_last


class NumberOfDoses(OutputMetric):
    output_name = _("Number of Doses")
    output_unit = _("Doses")
    metric_name = _("Cost per Dose")
    metric_equation = "cost_output_sum / number_of_doses"
    parameters = {
        "number_of_doses": PositiveFixedDecimalField(label=_("Number of Doses")),
    }

    def calculate(self, cost_output_sum, number_of_doses, **kwargs):
        return cost_output_sum / number_of_doses


class NumberOfChildren(OutputMetric):
    output_name = _("Number of Children")
    output_unit = _("Children")
    metric_name = _("Cost per Child")
    metric_equation = "cost_output_sum / number_of_children"
    parameters = {
        "number_of_children": PositiveFixedDecimalField(label=_("Number of Children")),
    }

    def calculate(self, cost_output_sum, number_of_children, **kwargs):
        return cost_output_sum / number_of_children


class NumberOfParticipants(OutputMetric):
    output_name = _("Number of Participants")
    output_unit = _("Participant")
    metric_name = _("Cost per Participant")
    metric_equation = "cost_output_sum / number_of_participants"
    parameters = {
        "number_of_participants": PositiveFixedDecimalField(label=_("Number of Participants")),
    }

    def calculate(self, cost_output_sum, number_of_participants, **kwargs):
        return cost_output_sum / number_of_participants


class NumberOfWomen(OutputMetric):
    output_name = _("Number of Women")
    output_unit = _("Women")
    metric_name = _("Cost per Woman")
    metric_equation = "cost_output_sum / number_of_women"
    parameters = {
        "number_of_women": PositiveFixedDecimalField(label=_("Number of Women")),
    }

    def calculate(self, cost_output_sum, number_of_women, **kwargs):
        return cost_output_sum / number_of_women


class NumberOfChildrenRecovered(OutputMetric):
    output_name = _("Number of Children Recovered")
    output_unit = _("Children Recovered")
    metric_name = _("Cost per Child Recovered")
    metric_equation = "cost_output_sum / number_of_children_recovered"
    parameters = {
        "number_of_children_recovered": PositiveFixedDecimalField(label=_("Number of Children Recovered")),
    }

    def calculate(self, cost_output_sum, number_of_children_recovered, **kwargs):
        return cost_output_sum / number_of_children_recovered


class NumberOfCommunities(OutputMetric):
    output_name = _("Number of Communities")
    output_unit = _("Communities")
    metric_name = _("Cost per Community")
    metric_equation = "cost_output_sum / number_of_communities"
    parameters = {
        "number_of_communities": PositiveFixedDecimalField(label=_("Number of Communities")),
    }

    def calculate(self, cost_output_sum, number_of_communities, **kwargs):
        return cost_output_sum / number_of_communities


class NumberOfCoupleYearsOfProtection(OutputMetric):
    output_name = _("Number of Couple-Years of Protection (CYPs)")
    output_unit = _("Couple-Years of Protection (CYPs)")
    metric_name = _("Cost per Couple per Year of Protection")
    metric_equation = "cost_output_sum / number_of_CYPs_provided"
    parameters = {
        "number_of_CYPs_provided": PositiveFixedDecimalField(
            label=_("Cost per Couple per Year of Protection")
        ),
    }

    def calculate(self, cost_output_sum, number_of_CYPs_provided, **kwargs):
        return cost_output_sum / number_of_CYPs_provided


class ValueOfItemsDistributed(OutputMetric):
    output_name = _(f"Value of Items Distributed")
    output_unit = _(f"Items Distributed")
    output_as_currency = True
    metric_name = _(f"Cost per Monetary Unit Distributed")
    metric_equation = "(cost_output_sum - value_items_distributed) / value_items_distributed"
    parameters = {
        "value_items_distributed": PositiveFixedDecimalField(label=_(f"Value of Items Distributed")),
    }

    @check_zero_args(["value_items_distributed", "cost_output_sum"])
    def calculate(self, cost_output_sum, value_items_distributed, **kwargs):
        return (cost_output_sum - value_items_distributed) / value_items_distributed


class NumberOfOutputs(OutputMetric):
    output_name = _("Number of Outputs")
    output_unit = _("Outputs")
    metric_name = _("Cost per Output")
    metric_equation = "cost_output_sum / number_of_outputs"
    parameters = {
        "number_of_outputs": PositiveFixedDecimalField(label=_("Number of Outputs")),
    }

    def calculate(self, cost_output_sum, number_of_outputs, **kwargs):
        return cost_output_sum / number_of_outputs


class NumberOfConsultations(OutputMetric):
    output_name = _("Number of Consultations")
    output_unit = _("Consultations")
    metric_name = _("Cost per Consultation")
    metric_equation = "cost_output_sum / number_of_consultations"
    parameters = {
        "number_of_consultations": PositiveFixedDecimalField(label=_("Number of Consultations")),
    }

    def calculate(self, cost_output_sum, number_of_consultations, **kwargs):
        return cost_output_sum / number_of_consultations


class NumberOfClients(OutputMetric):
    output_name = _("Number of Clients")
    output_unit = _("Clients")
    metric_name = _("Cost per Client")
    metric_equation = "cost_output_sum / number_of_clients"
    parameters = {
        "number_of_clients": PositiveFixedDecimalField(label=_("Number of Clients")),
    }

    def calculate(self, cost_output_sum, number_of_clients, **kwargs):
        return cost_output_sum / number_of_clients


class NumberOfHouseholds(OutputMetric):
    output_name = _("Number of Households")
    output_unit = _("Households")
    metric_name = _("Cost per Household")
    metric_equation = "cost_output_sum / number_of_households"
    parameters = {
        "number_of_households": PositiveFixedDecimalField(label=_("Number of Households")),
    }

    def calculate(self, cost_output_sum, number_of_households, **kwargs):
        return cost_output_sum / number_of_households


class NumberOfTeacherDaysOfTraining(OutputMetric):
    output_name = _("Number of Teacher-Days of Training")
    output_unit = _("Teacher-Days of Training")
    metric_name = _("Cost per Teacher per Day of Training")
    metric_equation = "cost_output_sum / (number_of_teachers * number_of_days_of_training)"
    parameters = {
        "number_of_teachers": PositiveFixedDecimalField(label=_("Number of Teachers")),
        "number_of_days_of_training": PositiveFixedDecimalField(label=_("Number of Days of Training")),
    }

    def calculate(self, cost_output_sum, number_of_teachers, number_of_days_of_training, **kwargs):
        return cost_output_sum / (number_of_teachers * number_of_days_of_training)

    def total_output(self, number_of_teachers=0, number_of_days_of_training=0):
        return number_of_teachers * number_of_days_of_training


class NumberOfDaysOfTraining(OutputMetric):
    output_name = _("Number of Days of Training")
    output_unit = _("Days of Training")
    metric_name = _("Cost per Person per Day of Training")
    metric_equation = "cost_output_sum / (number_of_people * number_of_days_of_training)"
    parameters = {
        "number_of_people": PositiveFixedDecimalField(label=_("Number of People")),
        "number_of_days_of_training": PositiveFixedDecimalField(label=_("Number of Days of Training")),
    }

    def calculate(self, cost_output_sum, number_of_people, number_of_days_of_training, **kwargs):
        return cost_output_sum / (number_of_people * number_of_days_of_training)

    def total_output(self, number_of_people=0, number_of_days_of_training=0):
        return number_of_people * number_of_days_of_training


class NumberOfTeacherYearsOfSupport(OutputMetric):
    output_name = _("Number of Teacher-Years of Support")
    output_unit = _("Teacher-Years of Support")
    metric_name = _("Cost per Teacher per Year  of Support")
    metric_equation = "cost_output_sum / (number_of_teachers * number_of_years_of_support)"
    parameters = {
        "number_of_teachers": PositiveFixedDecimalField(label=_("Number of Teachers")),
        "number_of_years_of_support": PositiveFixedDecimalField(label=_("Number of Years of Support")),
    }

    def calculate(self, cost_output_sum, number_of_teachers, number_of_years_of_support, **kwargs):
        return cost_output_sum / (number_of_teachers / number_of_years_of_support)

    def total_output(self, number_of_teachers=0, number_of_years_of_support=0):
        return number_of_teachers * number_of_years_of_support


class NumberOfChildrenTreated(OutputMetric):
    output_name = _("Number of Children Treated (Excluding Defaulters)")
    output_unit = _("Children Treated (Excluding Defaulters)")
    metric_name = _("Cost per Child Treated")
    metric_equation = "cost_output_sum / number_of_children_treated"
    parameters = {
        "number_of_children_treated": PositiveFixedDecimalField(
            label=_("Number of Children Treated (Excluding Defaulters)")
        ),
    }

    def calculate(self, cost_output_sum, number_of_children_treated, **kwargs):
        return cost_output_sum / number_of_children_treated


class ValueOfCashDistributed(OutputMetric):
    output_name = _(f"Value of Cash Distributed")
    output_unit = _(f"Cash Distributed")
    output_as_currency = True
    metric_name = _(f"Cost per Cash Distributed")
    metric_equation = "(cost_output_sum - value_of_cash_distributed) / value_of_cash_distributed"
    parameters = {
        "value_of_cash_distributed": PositiveFixedDecimalField(
            label=_(f"Value of Cash Distributed"),
        ),
    }

    @check_zero_args(["value_of_cash_distributed", "cost_output_sum"])
    def calculate(self, cost_output_sum, value_of_cash_distributed, **kwargs):
        return (cost_output_sum - value_of_cash_distributed) / value_of_cash_distributed


class ValueOfBusinessGrantAmount(OutputMetric):
    output_name = _(f"Value of Business Grant Amount")
    output_unit = _(f"Amount Provided")
    output_as_currency = True
    metric_name = _(f"Cost per Grant Cash Provided")
    metric_equation = "(cost_output_sum - value_of_business_grant_amount) / value_of_business_grant_amount"
    parameters = {
        "value_of_business_grant_amount": PositiveFixedDecimalField(
            label=_("Value of Business Grant Amount"),
        ),
    }

    @check_zero_args(["value_of_business_grant_amount", "cost_output_sum"])
    def calculate(self, cost_output_sum, value_of_business_grant_amount, **kwargs):
        return (cost_output_sum - value_of_business_grant_amount) / value_of_business_grant_amount


class NumberOfHectares(OutputMetric):
    output_name = _("Number of Hectares")
    output_unit = _("Hectares")
    metric_name = _("Cost per Hectare")
    metric_equation = "cost_output_sum / number_of_hectares"
    parameters = {
        "number_of_hectares": PositiveFixedDecimalField(label=_("Number of Hectares")),
    }

    def calculate(self, cost_output_sum, number_of_hectares, **kwargs):
        return cost_output_sum / number_of_hectares


class NumberOfCaregivers(OutputMetric):
    output_name = _("Number of Caregivers")
    output_unit = _("Caregivers")
    metric_name = _("Cost per Caregiver")
    metric_equation = "cost_output_sum / number_of_caregivers"
    parameters = {
        "number_of_caregivers": PositiveFixedDecimalField(label=_("Number of Caregivers")),
    }

    def calculate(self, cost_output_sum, number_of_caregivers, **kwargs):
        return cost_output_sum / number_of_caregivers


class NumberOfMeals(OutputMetric):
    output_name = _("Number of Meals")
    output_unit = _("Meals")
    metric_name = _("Cost per Meal")
    metric_equation = "cost_output_sum / number_of_meals"
    parameters = {
        "number_of_meals": PositiveFixedDecimalField(label=_("Number of Meals")),
    }

    def calculate(self, cost_output_sum, number_of_meals, **kwargs):
        return cost_output_sum / number_of_meals


class NumberOfGroups(OutputMetric):
    output_name = _("Number of Groups")
    output_unit = _("Groups")
    metric_name = _("Cost per Group")
    metric_equation = "cost_output_sum / number_of_groups"
    parameters = {
        "number_of_groups": PositiveFixedDecimalField(label=_("Number of Groups")),
    }

    def calculate(self, cost_output_sum, number_of_groups, **kwargs):
        return cost_output_sum / number_of_groups


OUTPUT_METRICS = [
    NumberOfCaregivers(),
    NumberOfChildren(),
    NumberOfChildrenRecovered(),
    NumberOfChildrenTreated(),
    NumberOfClients(),
    NumberOfCommunities(),
    NumberOfConsultations(),
    NumberOfCoupleYearsOfProtection(),
    NumberOfDaysOfTraining(),
    NumberOfDoses(),
    NumberOfGroups(),
    NumberOfHectares(),
    NumberOfHouseholds(),
    NumberOfMeals(),
    NumberOfOutputs(),
    NumberOfParticipants(),
    NumberOfPeople(),
    NumberOfPersonYearsOfSanitationAccess(),
    NumberOfPersonYearsOfWaterAccess(),
    NumberOfTeacherDaysOfTraining(),
    NumberOfTeacherYearsOfSupport(),
    NumberOfWomen(),
    ValueOfBusinessGrantAmount(),
    ValueOfCashDistributed(),
    ValueOfItemsDistributed(),
]

OUTPUT_METRIC_CHOICES = [(output_metric.id, output_metric.output_name) for output_metric in OUTPUT_METRICS]
OUTPUT_METRICS_BY_ID = {output_metric.id: output_metric for output_metric in OUTPUT_METRICS}
