from website.models.fields import TypedJson

SubcomponentLabelsType = TypedJson(list[str])
SubcomponentAnalysisValuesType = TypedJson(dict[str, str])

InterventionParametersType = TypedJson(dict[str, float])

# Intervention metadata values: field key -> text/number string, or a list of option keys.
InterventionMetadataType = TypedJson(dict[str, str | list[str]])
