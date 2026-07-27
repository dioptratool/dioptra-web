/* selected text on focus */
document.querySelectorAll('input.analysis-table__subcomponent-allocate-input, input.analysis-table__allocated-input').forEach((input) => {
  input.addEventListener('change', (e) => e.target.setAttribute('data-changed', true))
  input.addEventListener('focusin', (e) => e.target.select())
})

document.querySelectorAll('.analysis-table__category-content--freeze-col, .analysis-table__category-content--freeze-row')?.forEach((table) => {
  const wrapper = table.querySelector('.analysis-table__wrapper');
  wrapper.addEventListener('scroll', (e) => {
    wrapper.setAttribute('data-dragged-x', e.target.scrollLeft > 5);
    wrapper.setAttribute('data-dragged-y', e.target.scrollTop > 5);
  });
});

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
