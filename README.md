<div align="center">

![Dioptra logo](https://images.squarespace-cdn.com/content/v1/5d5f1681773a350001f976f8/1594003441742-S7F6G85KOD0J9KNFW8AU/Dioptra_Official+Logo_Color.png?format=2500w)

### A web-based cost analysis tool that helps program staff at humanitarian and development organizations estimate the cost-efficiency of their interventions.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/dioptratool/dioptra-web?tab=Apache-2.0-1-ov-file)

</div>

---

## Contents

- [Why Dioptra?](#why-dioptra)
- [Key features](#key-features)
- [Getting started](#getting-started)
- [Open source & the Consortium](#open-source--the-consortium)
- [Contributing](#contributing)
- [License](#license)

---

## Why Dioptra?

Dioptra enables program staff to rapidly estimate the cost-efficiency of their program interventions using existing financial and monitoring data. There are two key cases where Dioptra provides the greatest value:

1. **Sectoral learning**: exploring the typical cost-per-output of common activities and analyzing how cost-per-output is driven by differences in activity design or program context.
2. **Performance management**: analyzing the cost-efficiency of a program periodically, comparing it to benchmarks for that activity, and assessing whether greater reach might be possible if the program design were adapted.

Both rely on the same underlying method: an ingredients-based approach to costing ([Levin and McEwan](https://scholar.google.com/citations?view_op=view_citation&hl=en&user=HI6m-dsAAAAJ&citation_for_view=HI6m-dsAAAAJ:bEWYMUwI8FkC)), aligned with established sector guidance on cost-efficiency analysis. See the [Cost Analysis Methodology at the IRC](https://www.rescue.org/report/cost-analysis-methodology-irc) for details.

Instead of relying on analysts to develop an ingredients list "from scratch," Dioptra taps into the reality of how implementing organizations are funded and uses existing accounting information from the awards that funded the interventions being studied. Dioptra pulls in data on all the ingredients funded by a particular award or awards (program costs, support costs, and indirect costs), then asks program staff to narrow down to the ingredients specifically used for the intervention being analyzed.

## Key features

| Feature | What it does |
|---|---|
| 🧩 **Ingredients-based approach** | Costing follows an ingredients-based method grounded in existing award accounting data, rather than a bespoke ingredients list built from scratch for each analysis. |
| ⚡ **Automatic pull of expense data** | Dioptra automatically uses the organization's available financial transaction data (see [Data connections](https://www.dioptratool.org/how-does-dioptra-work)). This reduces the time needed for a cost analysis from several days to a few hours, minimizing the burden on field staff. |
| 📏 **Standardized output metrics** | Cost-efficiency metrics that are commonly agreed upon in sectoral forums, covering **40+ interventions**, ensuring comparability of results. See the [full list of standardized metrics](https://www.dioptratool.org/standardized-metrics). |
| 🗂️ **Common set of cost categories** | Includes support and indirect costs to show the "fully loaded" cost of an intervention, avoiding artificial differences in apparent cost-efficiency caused by how support/indirect costs happen to be funded. Dioptra also calculates a suggested support-cost allocation percentage, based on the Grand Bargain Cash workstream's method. |
| 📊 **Analysis insights** | Displays results alongside available data points from similar programs, making it easier to see which features likely drive differences in cost-efficiency across designs or contexts. |

## Getting started

Dioptra can be installed and hosted by your organization directly from this repository.

- 🛠️ [Installation and hosting guide](#): setting up your own instance
- 🔌 [Data connections](https://www.dioptratool.org/how-does-dioptra-work): options for hosting, authentication, and connecting your financial data
- 📖 [User guide](https://www.dioptratool.org/videos): running an analysis
- 🌐 [Dioptra website](https://www.dioptratool.org)

Prefer a hosted, supported setup? Dioptra is also available through the Consortium. See [Open source & the Consortium](#open-source--the-consortium).

## Open source & the Consortium

Dioptra is open source and publicly available under the Apache 2.0 license. Making the code public keeps the methodology transparent and allows any organization to use and self-host the tool.

Dioptra is also offered as software-as-a-service to members of the Dioptra Consortium, a community of practitioners across humanitarian and development agencies working to strengthen the sector's use of cost evidence. Members receive installation and ongoing support, help shape the tool's development, connect through a community of practice with regular standing meetings, and explore opportunities for joint efforts and initiatives.

<table align="center">
  <tr>
    <td align="center"><img src="https://images.squarespace-cdn.com/content/v1/5d5f1681773a350001f976f8/1592589287376-XU5J728V7PX4TDAE29MF/ACH+Logo.png?format=100w" alt="Accion Contra El Hambre" height="60"></td>
    <td align="center"><img src="https://images.squarespace-cdn.com/content/v1/5d5f1681773a350001f976f8/1592589321170-8QDVFER6VX28B40IHLD9/CARE+Logo.gif?format=100w" alt="CARE" height="60"></td>
    <td align="center"><img src="https://images.squarespace-cdn.com/content/v1/5d5f1681773a350001f976f8/5f29d980-e208-4ddc-8b3d-6d4a19cb8235/CRS+Logo.jpg?format=100w" alt="Catholic Relief Services" height="60"></td>
    <td align="center"><img src="https://images.squarespace-cdn.com/content/v1/5d5f1681773a350001f976f8/6703f996-f097-4e19-ad00-0badcb3fb5b8/DRC+PNG.jpg?format=100w" alt="Danish Refugee Council" height="60"></td>
  </tr>
  <tr>
    <td align="center"><img src="https://images.squarespace-cdn.com/content/v1/5d5f1681773a350001f976f8/1594006841952-WQ0933W5DAX5EUCO6RGF/IRC+Logo.png?format=100w" alt="International Rescue Committee" height="60"></td>
    <td align="center"><img src="https://images.squarespace-cdn.com/content/v1/5d5f1681773a350001f976f8/1592589412066-UD8Q8NVSD9J83561NPCN/Mercy+Corps+Logo.jpg?format=100w" alt="Mercy Corps" height="60"></td>
    <td align="center"><img src="https://images.squarespace-cdn.com/content/v1/5d5f1681773a350001f976f8/1592589439542-5Q6GTTUI2LWP1BOFL8S9/Save+the+Children+Logo.png?format=100w" alt="Save the Children" height="60"></td>
    <td align="center"><img src="https://images.squarespace-cdn.com/content/v1/5d5f1681773a350001f976f8/137f835f-4649-4694-893e-2307ae8b29fd/NRC-logo+%282%29.png?format=100w" alt="Norwegian Refugee Council" height="60"></td>
  </tr>
</table>

📩 [Contact the IRC](https://www.dioptratool.org/contact-us) to learn more about joining the Consortium.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](https://github.com/dioptratool/dioptra-web?tab=contributing-ov-file) for guidelines.

## License

Licensed under the [Apache License 2.0](https://github.com/dioptratool/dioptra-web?tab=Apache-2.0-1-ov-file).
