var gulp = require('gulp');
var sass = require('gulp-sass/legacy')(require('sass'));
var concat = require('gulp-concat');
var livereload = require('gulp-livereload');

var bootstrapDir = './node_modules/bootstrap-sass/assets';
var bootstrapJsDir = bootstrapDir + '/javascripts/bootstrap';

gulp.task('sass', function() {
  return gulp.src('css/panels.scss')
            .pipe(sass({
              includePaths: [
                bootstrapDir + '/stylesheets'
              ]
            }).on('error', sass.logError))
            .pipe(gulp.dest('./css/'))
            .pipe(livereload());
});

gulp.task('sass-inside', function() {
  return gulp.src('css/panels-inside.scss')
            .pipe(sass({
              includePaths: [
                bootstrapDir + '/stylesheets'
              ]
            }).on('error', sass.logError))
            .pipe(gulp.dest('./css/'))
            .pipe(livereload());
});

gulp.task('sass-widgets', function() {
  return gulp.src('css/panels-relation-widget.scss')
            .pipe(sass({
              includePaths: [
                bootstrapDir + '/stylesheets'
              ]
            }).on('error', sass.logError))
            .pipe(gulp.dest('./css/'))
            .pipe(livereload());
});

gulp.task('js-panels-core', function() {
  var files = [
    './js/_panels-utils.js',
    './js/_panels-alerts.js',
    './js/_panels-core.js',
    './js/_admin-overlay.js'
  ];
  return gulp.src(files)
          .pipe(concat('panels.js'))
          .pipe(gulp.dest('./js/'))
          .pipe(livereload());
});

gulp.task('js-panels-inside', function() {
  var files = [
    bootstrapJsDir + '/dropdown.js',
    './js/_panels-utils.js',
    './js/_panels-alerts.js',
    './js/_panels-core.js',
    './js/_panel-form.js',
    './js/_filter-lists-form.js',
    './js/_filter-lists.js',
    './js/_panels-focus.js'
  ];
  return gulp.src(files)
          .pipe(concat('panels-inside.js'))
          .pipe(gulp.dest('./js/'))
          .pipe(livereload());
});

gulp.task('watch', function() {
  livereload.listen();
  gulp.watch('css/**/*.scss', gulp.series(['sass', 'sass-inside']));
  gulp.watch('css/panels-relation-widget.scss', gulp.series(['sass-widgets']));
  gulp.watch([
    './js/**/*.js',
    '!./js/panels.js',
    '!./js/panels-inside.js'
  ], gulp.series(['js-panels-core', 'js-panels-inside']));
});

gulp.task('default', gulp.series(['watch']));
