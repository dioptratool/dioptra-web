import argparse
import json
import textwrap

from any_urlfield.models import AnyUrlValue
from bs4 import BeautifulSoup
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from ombucore.assets.models import ImageAsset
from website.help.models import HelpItem, HelpPage, HelpTopic
from .mixins import DryRunCommandMixin


class Command(DryRunCommandMixin, BaseCommand):
    # _static_registry = UrlTypeRegistry()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Map each original model instance with its newly created counterpart
        self.source_map = {
            "items": {},
            "topics": {},
            "pages": {},
            "images": {},
        }

        self.json_file = None

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--json",
            type=argparse.FileType("r"),
            help=textwrap.dedent("Path to a JSON input file, or '-' for stdin"),
        )

    def _handle_mutatable(self, *args, **options):
        self.json_file = options.get("json")
        if not self.json_file:
            raise CommandError("--json is required")

        return self.import_help_wrapper()

    def import_help_wrapper(self):
        """
        Rollback changes on any exception
        """
        try:
            code = self.import_help()
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"*Early Exit due to unhandled error: {exc}"))
            return 1  # Value of 1 signifies the need to rollback

        return code

    def import_help(self):
        prev_items_count = HelpItem.objects.all().count()
        prev_pages_count = HelpPage.objects.all().count()
        prev_topics_count = HelpTopic.objects.all().count()
        HelpItem.objects.all().delete()
        HelpPage.objects.all().delete()
        HelpTopic.objects.all().delete()

        help_data = json.load(self.json_file)

        for image_data in help_data["images"]:
            source_id = image_data.pop("source_id")
            image_data.pop("asset_ptr_id", None)
            image_data.pop("polymorphic_ctype_id", None)

            # Convert old file name to new file name, then create new Django File for the ImageAsset
            image_filename = image_data.pop("image")
            new_image_filename = image_filename.replace(
                "/media/", "website/management/commands/seed_data/help_data/"
            )
            image_asset = ImageAsset(**image_data)
            image_file = open(new_image_filename, "rb")
            image_asset.image = File(image_file, name=new_image_filename.split("/")[-1])
            image_asset.save()
            image_file.close()

            self.source_map["images"][source_id] = image_asset

        for topic_data in help_data["topics"]:
            source_id = topic_data.pop("source_id")
            help_topic = HelpTopic.objects.create(**topic_data)
            self.source_map["topics"][source_id] = help_topic

        for page_data in help_data["pages"]:
            # Get new PageTopic reference
            prev_topic_id = page_data["topic_id"]
            page_data["topic_id"] = self.source_map["topics"][prev_topic_id].id

            # Update embedded asset references
            image_url_map = {}
            soup = BeautifulSoup(page_data["body"], "html.parser")
            for item in soup.find_all():
                if "data-ombuimage" in item.attrs:
                    image_info = json.loads(item.attrs["data-ombuimage"])

                    prev_asset_id = image_info["objInfo"]["id"]
                    new_asset_id = self.source_map["images"][prev_asset_id].id
                    image_info["objInfo"]["id"] = new_asset_id

                    prev_image_url = image_info["objInfo"]["image_url"]
                    new_image_url = self.source_map["images"][prev_asset_id].image.url
                    if "media/img/" not in new_image_url:
                        new_image_url = new_image_url.replace("media/", "media/img/")
                    image_url_map[prev_image_url] = new_image_url
                    image_info["objInfo"]["image_url"] = new_image_url

                    item.attrs["data-ombuimage"] = json.dumps(image_info)

            for img in soup.find_all("img"):
                if "src" in img.attrs and img.attrs["src"] in image_url_map:
                    img.attrs["src"] = image_url_map[img.attrs["src"]]

            page_data["body"] = str(soup)

            source_id = page_data.pop("source_id")
            help_page = HelpPage.objects.create(**page_data)
            self.source_map["pages"][source_id] = help_page

        for item_data in help_data["items"]:
            link_data = item_data.pop("link", None)
            if link_data:
                # Update help page pointer
                if link_data[0] == "help.helppage":
                    prev_help_page_id = link_data[1]
                    link_data[1] = self.source_map["pages"][prev_help_page_id].id
                clean_value = AnyUrlValue(*link_data)
                item_data["link"] = clean_value

            source_id = item_data.pop("source_id")
            help_item = HelpItem.objects.create(**item_data)
            self.source_map["items"][source_id] = help_item

        items_count = HelpItem.objects.all().count()
        pages_count = HelpPage.objects.all().count()
        topics_count = HelpTopic.objects.all().count()
        confirm = input(
            f"""
You have requested a Help data reset.
This will IRREVERSIBLY DESTROY existing Django Help Data in the database.
({prev_items_count} HelpItems, {prev_topics_count} HelpTopics, {prev_pages_count} HelpPages)

{items_count} new HelpItems, {topics_count} new HelpTopics, {pages_count} new HelpPages will be created.
Are you sure you want to do this?

Type 'y' to continue, or 'n' to cancel: """
        )

        if confirm != "y":
            return 1  # Value of 1 signifies the need to rollback

        return 0
