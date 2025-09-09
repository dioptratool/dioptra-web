import json

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from ombucore.assets.models import ImageAsset
from website.help.models import HelpItem, HelpPage, HelpTopic


class Command(BaseCommand):
    FIELDS_TO_REMOVE = ("id", "_state", "created")

    def handle(self, *args, **options):
        self.export_help()

    def _serialize(self, model_instance):
        instance_json = model_instance.__dict__
        instance_json["source_id"] = model_instance.id

        for field in self.FIELDS_TO_REMOVE:
            instance_json.pop(field, None)

        return instance_json

    def export_help(self):
        help_json = {
            "items": [],
            "topics": [],
            "pages": [],
            "images": [],
        }

        items_qs = HelpItem.objects.all()
        for item in items_qs:
            item_json = self._serialize(item)
            help_json["items"].append(item_json)
            if not item.link:
                continue
            item_json["link"] = [item.link.type_prefix, item.link.type_value]

        topics_qs = HelpTopic.objects.all()
        for topic in topics_qs:
            topic_json = self._serialize(topic)
            help_json["topics"].append(topic_json)

        image_assset_ids = []
        pages_qs = HelpPage.objects.all()
        for page in pages_qs:
            page_json = self._serialize(page)
            help_json["pages"].append(page_json)
            if not page.body:
                continue

            # Find all embedded ImageAsset instances that will need to be created
            soup = BeautifulSoup(page.body, "html.parser")
            for item in soup.find_all():
                if "data-ombuimage" in item.attrs:
                    image_info = json.loads(item.attrs["data-ombuimage"])
                    image_assset_ids.append(image_info["objInfo"]["id"])

        assets_qs = ImageAsset.objects.filter(id__in=image_assset_ids)
        for image_asset in assets_qs:
            image_asset_json = self._serialize(image_asset)
            image_asset_json["image"] = image_asset.image.url
            help_json["images"].append(image_asset_json)

        with open("website/management/commands/seed_data/help_data/exported-help.json", "w+") as f:
            json.dump(help_json, f, indent=4)

        return
