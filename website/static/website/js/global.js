// Currency symbol configured for this deployment (rendered by the
// `dioptra-currency` json_script), falling back to "$". Exposed globally for
// the standalone insights-charts.js.
export function getDioptraCurrencySymbol() {
  var configEl = document.getElementById('dioptra-currency')
  if (configEl) {
    var config = JSON.parse(configEl.innerHTML)
    if (config.symbol) {
      return config.symbol
    }
  }
  return '$'
}

window.getDioptraCurrencySymbol = getDioptraCurrencySymbol;
