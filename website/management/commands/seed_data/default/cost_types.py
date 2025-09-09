from website.models.cost_type import Indirect, ProgramCost, Support

DEFAULT_COST_TYPE = {
    "name": "Program Costs",
    "type": ProgramCost.id,
}

COST_TYPES = [
    {
        "name": "Support Costs",
        "type": Support.id,
    },
    {
        "name": "Indirect Costs",
        "type": Indirect.id,
    },
]
