from website.models.fields import TypedJson

SubcomponentLabelsType = TypedJson(list[str])
SubcomponentAnalysisValuesType = TypedJson(dict[str, str])

InterventionParametersType = TypedJson(dict[str, float])
