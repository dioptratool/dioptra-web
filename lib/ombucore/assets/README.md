Assets
======

Implements polymorphic Image, Video and Document models and admins.  Also makes
Asset models embeddable in CKEditor.


## Installation

Add `ombucore.assets` to `INSTALLED_APPS`.


## Configuration

### Videos

The default supported video providers are:

    OMBUASSETS_VIDEO_PROVIDERS = [
        {
            'name': 'YouTube',
            'example_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'patterns': {
                'http://(\S*.)?youtu(\.be/|be\.com/watch)\S+': 'http://www.youtube.com/oembed',
                'https://(\S*.)?youtu(\.be/|be\.com/watch)\S+': 'http://www.youtube.com/oembed?scheme=https&',
            },
        },
        {
            'name': 'Vimeo',
            'example_url': 'https://vimeo.com/87329114',
            'patterns': {
                'http://vimeo.com/\S+': 'http://vimeo.com/api/oembed.json',
                'https://vimeo.com/\S+': 'http://vimeo.com/api/oembed.json',
            },
        },
    ]

Copy this list to your settings and add/remove providers to change.

### Images

Set the image generator to use when embedding an image asset in rich text.

    ASSET_IMAGE_EMBEDDED_GENERATOR = "website:max_width"


## Models

All the models implement a `render_embedded()` method that is called on output
and passed a settings object with any info relevant to the specific embed
(style, caption, etc.).


## Template Usage

Upon output in a template, the `asset` filter needs to be used with any
richrich text so that asset placeholders are replaced with the actual asset
content. The `safe` filter also needs to be used to keep any rich text html
from being escaped.

Example:

    {% load assets %}

    {{ content.text|assets|safe }}
