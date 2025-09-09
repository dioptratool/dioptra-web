/* selected text on focus */
document.querySelectorAll('input.analysis-table__subcomponent-allocate-input, input.analysis-table__allocated-input').forEach((input) => {
  input.addEventListener('change', (e) => e.target.setAttribute('data-changed', true))
  input.addEventListener('focusin', (e) => e.target.select())
})

// auto resize frozen table rows whenever a table is activated
window.addEventListener('DOMContentLoaded', (e) => {
  document.querySelectorAll('.analysis-table__category-toggle')?.forEach((trigger) => {
    trigger.addEventListener('click', (evt) => {
      setTimeout(() => {// allow time for offsetHeight to update
        const frozenTable = evt.target.closest('.analysis-table__category')?.querySelector('.analysis-table__category-content--freeze-col');
        if (frozenTable) {
          resizeFrozenTableRows(frozenTable)
        }
      }, 200)
    })
  })
  document.querySelector('.analysis-table__category--unconfirmed')?.classList.add('analysis-table__category--active')
  document.querySelectorAll('.analysis-table__category-content--freeze-col')?.forEach((table) => {
    resizeFrozenTableRows(table)
  })
});

function resizeFrozenTableRows(table) {
  const active = table.closest('.analysis-table__category--active')
  table.querySelectorAll('td')?.forEach((cell) => {

    const row = cell.closest('tr')
    if (row && cell.offsetHeight > row.offsetHeight) {
      row.style.height = cell.offsetHeight + 'px'
    }
    const frozenCell = row.querySelector('td:first-child')
    if (!active) {
      frozenCell.style.height = null
      return
    }
    if (cell.offsetHeight > frozenCell.offsetHeight) {
      frozenCell.style.height = cell.offsetHeight + 'px'
    }
  })
}

/* Make tables mouse draggable */
const tableWrapperSelector = '.analysis-table__wrapper'
const tables = document.querySelectorAll(tableWrapperSelector);

const startDragging = (e) => {
  const tableWrapper = e.target.closest(tableWrapperSelector)
  tableWrapper.dataset.mouseDown = true;
  tableWrapper.dataset.startX = e.pageX - tableWrapper.offsetLeft;
  tableWrapper.dataset.scrollLeft = tableWrapper.scrollLeft;
}

const stopDragging = (e) => {
  const tableWrapper = e.target.closest(tableWrapperSelector)
  delete tableWrapper.dataset.mouseDown
}

const move = (e) => {
  const tableWrapper = e.target.closest(tableWrapperSelector)

  e.preventDefault();
  if(!tableWrapper.dataset.mouseDown) { return; }
  const x = e.pageX - tableWrapper.offsetLeft;
  const scroll = x - tableWrapper.dataset.startX;
  tableWrapper.scrollLeft = tableWrapper.dataset.scrollLeft - scroll;
}

tables.forEach(table => {
  // Add the event listeners
  table.addEventListener('mousemove', move, false);
  table.addEventListener('mousedown', startDragging, false);
  table.addEventListener('mouseup', stopDragging, false);
  table.addEventListener('mouseleave', stopDragging, false);
})
