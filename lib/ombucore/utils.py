from django.conf import settings

locales_by_code = dict(settings.LANGUAGES)


def extend_subclass(cls, subcls_name, subcls_options):
    """Creates a derivative of `cls` so that an internal class can be extended"""
    subcls_bases = (getattr(cls, subcls_name), object) if hasattr(cls, subcls_name) else (object,)
    subcls = type(str(subcls_name), subcls_bases, subcls_options)
    return type(
        str(cls.__name__),
        (cls,),
        {
            "__module__": cls.__module__,
            subcls_name: subcls,
        },
    )
