from django.core.management.base import BaseCommand

from website.models import Intervention

UPDATES = {
    # ("OLD", "NEW"),
    "NumberOfMentalHelathConsultationsProvided": "NumberOfMentalHealthConsultationsProvided",
}


class Command(BaseCommand):
    help = (
        "A small script that allows manually updating OutputMetrics in the system.   "
        "This is helpful if a typo has been made in a previous version.   "
        "Edit this script directly to add additional entries."
    )

    def handle(self, *args, **options):
        for each_intervention in Intervention.objects.all():
            for i, each_output_metric in enumerate(each_intervention.output_metrics):
                if each_output_metric in UPDATES:
                    print(
                        f"FOUND A ERRONEOUS ENTRY.  Replacing {each_output_metric} -> {UPDATES[each_output_metric]} ..."
                    )
                    new_output_metrics = each_intervention.output_metrics
                    new_output_metrics[i] = UPDATES[each_output_metric]

                    each_intervention.output_metrics = new_output_metrics
                    each_intervention.save()
