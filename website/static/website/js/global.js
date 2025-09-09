

function getDioptraCurrencySymbol() {
  var configEl = document.getElementById('dioptra-currency')
  console.log(configEl)
  if (configEl) {
    var config = JSON.parse(configEl.innerHTML)
    console.log(config)
    if (config.symbol) {
      return config.symbol
    }
  }
  return '$'
}