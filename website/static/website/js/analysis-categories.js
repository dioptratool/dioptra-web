$(function() {
  $('.analysis-table__category-toggle').on('click', function(e){
    e.preventDefault();
    $(this).closest('.analysis-table__category').toggleClass('analysis-table__category--active');
  }); 

  $('.analysis-table__transactions-toggle').on('click', function(e) {
    e.preventDefault();
    $(this).closest('tbody').find('.analysis-table__transaction-row').toggleClass('analysis-table__transaction-row--active')
    $(this).closest('tbody').toggleClass('analysis-table__tbody--transactions-active')
  });

  $('.analysis-table__category-edit').on('click', function(e) {
    e.preventDefault();
    $(this).closest('tbody').find('.analysis-table__edit-row').toggleClass('analysis-table__edit-row--active');
    $(this).closest('tbody').toggleClass('analysis-table__tbody--edit-active')
  });

  $('.analysis-table__category--unconfirmed').first().addClass("analysis-table__category--active");

  $('.analysis-table__category-edit--note').on('click', function(e) {
    $('.analysis-table__category-footer-action').hide();
    $('.analysis-table__actions').hide();
  });

  $('.analysis-table__set-contribution input[type="checkbox"]').on('change', function(e) {
    $(this).closest('label').toggleClass('checked')
  });
});