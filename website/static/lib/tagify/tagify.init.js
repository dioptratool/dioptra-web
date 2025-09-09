window.addEventListener('load', (e) => {
  document.querySelectorAll('input[data-tageditor]')?.forEach(function(input) {
      const tag = new Tagify(input, {
        originalInputValueFormat: valuesArr => valuesArr.map(item => item.value).join(',')
      })
  });
})
