var gulp = require('gulp');
var sass = require('gulp-sass/legacy')(require('sass'));
var concat = require('gulp-concat');
var livereload = require('gulp-livereload');

var bootstrapDir = './node_modules/bootstrap-sass/assets';
var panelsDir = '../../../lib/ombucore/admin/static';

gulp.task('sass', function() {
  return gulp.src('css/style.scss')
            .pipe(sass({
              includePaths: [
                bootstrapDir + '/stylesheets'
              ]
            }).on('error', sass.logError))
            .pipe(gulp.dest('./css/'))
            .pipe(livereload());
});

gulp.task('styleguide', function() {
  return gulp.src('css/styleguide/styleguide.scss')
            .pipe(sass({
              includePaths: [
                bootstrapDir + '/stylesheets'
              ]
            }).on('error', sass.logError))
            .pipe(gulp.dest('./css/'))
});

gulp.task('panels', function() {
  return gulp.src('css/panels-inside.scss')
            .pipe(sass({
              includePaths: [
                bootstrapDir + '/stylesheets',
                panelsDir,
              ]
            }).on('error', sass.logError))
            .pipe(gulp.dest('./css/'))
});

gulp.task('templates', function() {
  livereload.reload();
});

var bootstrapJsDir = bootstrapDir + '/javascripts/bootstrap';
var jsFiles = [
  bootstrapJsDir + '/dropdown.js',
  '../lib/jquery.AreYouSure/jquery.are-you-sure.js',
  './js/global.js',
  './js/form-helpers.js',
  './js/loading-triggers.js',
  './js/analysis-categories.js',
  './js/fix-missing-data.js',
  './js/categorize-cost_type.js',
  './js/ajax-transactions.js',
  './js/filters.js',
  './js/help.js',
  './js/table-edit-row.js',
  './js/analysis-table.js',
];
gulp.task('js', function() {
  return gulp.src(jsFiles)
          .pipe(concat('scripts.js'))
          .pipe(gulp.dest('./'))
          .pipe(livereload());
});

gulp.task('watch', function() {
  livereload.listen();
  gulp.watch('css/**/*.scss', gulp.series('sass'));
  gulp.watch('css/**/*.scss', gulp.series('styleguide'));
  gulp.watch('css/**/*.scss', gulp.series('panels'));
  gulp.watch('../../**/*.html', gulp.series('templates'));
  gulp.watch(jsFiles, gulp.series('js'));
});

gulp.task('default', gulp.series('watch'));
