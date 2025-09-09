import base64

from django.http import HttpResponse
from imagekit.registry import generator_registry
from imagekit.utils import generate
from pilkit.utils import format_to_mimetype, open_image


def ajax_file_preview(request):
    f = request.FILES["file"]
    generator_name = request.POST.get("preview-generator", "imagewidget:preview")
    generator = generator_registry.get(generator_name, source=f)
    preview_f = generate(generator)
    data = base64.b64encode(preview_f.read())
    file_format = open_image(preview_f).format
    mimetype = format_to_mimetype(file_format)
    return HttpResponse(f"data:{mimetype};base64,{data.decode()}")
