var gulp = require('gulp');
var sass = require('gulp-sass/legacy')(require('sass'));
var concat = require('gulp-concat');
var livereload = require('gulp-livereload');
var fs = require('fs');
var path = require('path');
var rollup = require('rollup').rollup;
var nodeResolvePlugin = require('@rollup/plugin-node-resolve');
var commonjsPlugin = require('@rollup/plugin-commonjs');
var postcss = require('rollup-plugin-postcss');
var esbuild = require('rollup-plugin-esbuild');

var bootstrapDir = './node_modules/bootstrap-sass/assets';
var panelsDir = '../../../lib/ombucore/admin/static';
var ckeditorEntry = path.resolve(__dirname, '../../../lib/ombucore/frontend/src/ckeditor.js');
var ckeditorOutDir = path.resolve(__dirname, '../../../lib/ombucore/admin/static/django_ckeditor_5/dist');
var resolve = nodeResolvePlugin.nodeResolve || nodeResolvePlugin.default || nodeResolvePlugin;
var commonjs = commonjsPlugin.default || commonjsPlugin;
var minify = esbuild.minify;

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
  './js/analysis-table-nested-checkboxes.js',
  './js/fix-missing-data.js',
  './js/categorize-cost_type.js',
  './js/allocate-bulk.js',
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

gulp.task('ckeditor', async function() {
  fs.mkdirSync(ckeditorOutDir, { recursive: true });

  var bundle = await rollup({
    input: ckeditorEntry,
    plugins: [
      resolve({ modulePaths: [path.resolve(__dirname, 'node_modules')] }),
      commonjs(),
      postcss({ extract: path.join(ckeditorOutDir, 'styles.css'), minimize: true }),
      minify(),
    ],
  });

  await bundle.write({
    file: path.join(ckeditorOutDir, 'bundle.js'),
    format: 'iife',
    name: 'CKEditor5Bundle',
    sourcemap: true,
  });
  await bundle.close();
});

gulp.task('scripts', gulp.series('js', 'ckeditor'));

gulp.task('watch', function() {
  livereload.listen();
  gulp.watch('css/**/*.scss', gulp.series('sass'));
  gulp.watch('css/**/*.scss', gulp.series('styleguide'));
  gulp.watch('css/**/*.scss', gulp.series('panels'));
  gulp.watch('../../**/*.html', gulp.series('templates'));
  gulp.watch(jsFiles, gulp.series('js'));
  gulp.watch('../../../lib/ombucore/frontend/src/**/*.{css,js}', gulp.series('ckeditor'));
});

gulp.task('default', gulp.series('watch'));
