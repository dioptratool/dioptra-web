import {
    Alignment,
    Autoformat,
    Bold,
    ClassicEditor,
    Essentials,
    GeneralHtmlSupport,
    Heading,
    HorizontalLine,
    Italic,
    Link,
    List,
    Paragraph,
    RemoveFormat,
    SimpleUploadAdapter,
    SourceEditing,
    Style,
    Table,
    TableCaption,
    TableCellProperties,
    TableColumnResize,
    TableProperties,
    TableToolbar,
    Underline,
    WidgetTypeAround,
    WordCount,
} from 'ckeditor5';

import 'ckeditor5/ckeditor5.css';

import { OmbuDocument } from './plugins/ombudocument/ombudocument.js';
import './plugins/ombudocument/ombudocument.css';
import { OmbuImage } from './plugins/ombuimage/ombuimage.js';
import './plugins/ombuimage/ombuimage.css';
import { PastePlainTextToggle } from './plugins/pasteplaintext/pasteplaintext.js';

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (const cookieEntry of cookies) {
            const cookie = cookieEntry.trim();
            if (cookie.substring(0, name.length + 1) === `${name}=`) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function resolveElementArray(element, query) {
    return element.matches(query) ? [element] : [...element.querySelectorAll(query)];
}

const builtinPlugins = [
    Alignment,
    Autoformat,
    Bold,
    Essentials,
    GeneralHtmlSupport,
    Heading,
    HorizontalLine,
    Italic,
    Link,
    List,
    Paragraph,
    RemoveFormat,
    SimpleUploadAdapter,
    SourceEditing,
    Style,
    Table,
    TableCaption,
    TableCellProperties,
    TableColumnResize,
    TableProperties,
    TableToolbar,
    Underline,
    WidgetTypeAround,
    WordCount,
    PastePlainTextToggle,
    OmbuDocument,
    OmbuImage,
];

const editors = {};
const callbacks = {};

function createEditors(element = document.body) {
    const textareas = resolveElementArray(element, '.django_ckeditor_5');

    textareas.forEach((textarea) => {
        if (
            textarea.id.indexOf('__prefix__') !== -1 ||
            textarea.getAttribute('data-processed') === '1' ||
            textarea.getAttribute('data-processing') === '1'
        ) {
            return;
        }

        const scriptId = `${textarea.id}_script`;

        if (
            textarea.nextSibling &&
            textarea.nextSibling.nodeType === Node.TEXT_NODE &&
            textarea.nextSibling.textContent.trim() === ''
        ) {
            textarea.nextSibling.remove();
        }

        const uploadConfigElement = element.querySelector(`#${scriptId}-ck-editor-5-upload-url`);
        const configElement = element.querySelector(`#${scriptId}-span`);
        if (!uploadConfigElement || !configElement) {
            return;
        }

        const uploadUrl = uploadConfigElement.getAttribute('data-upload-url');
        const uploadFileTypes = JSON.parse(uploadConfigElement.getAttribute('data-upload-file-types'));
        const csrfCookieName = uploadConfigElement.getAttribute('data-csrf_cookie_name');

        const label = element.querySelector(`[for$="${textarea.id}"]`);
        if (label) {
            label.style.float = 'none';
        }

        const config = JSON.parse(configElement.textContent, (key, value) => {
            const match = value.toString().match(new RegExp('^/(.*?)/([gimy]*)$'));
            return match ? new RegExp(match[1], match[2]) : value;
        });

        config.simpleUpload = {
            uploadUrl,
            headers: {
                'X-CSRFToken': getCookie(csrfCookieName),
            },
        };
        config.fileUploader = { fileTypes: uploadFileTypes };
        config.licenseKey = 'GPL';
        config.ui = { ...(config.ui || {}), poweredBy: { forceVisible: false } };
        config.extraPlugins = [...(config.extraPlugins || []), ...builtinPlugins];

        if (config.autosave) {
            config.autosave.save = function save(editor) {
                return new Promise((resolve, reject) => {
                    const data = editor.getData();
                    textarea.value = data;

                    if (!config.autosave.saveUrl) {
                        resolve();
                        return;
                    }

                    fetch(config.autosave.saveUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie(csrfCookieName),
                        },
                        body: JSON.stringify({ id: textarea.id, content: data }),
                    })
                        .then((response) => response.json())
                        .then((result) => resolve(result))
                        .catch((error) => reject(error));
                });
            };
        }

        textarea.setAttribute('data-processing', '1');

        ClassicEditor.create(textarea, config)
            .then((editor) => {
                editor.model.document.on('change:data', () => {
                    textarea.value = editor.getData();
                });

                if (editor.plugins.has('WordCount')) {
                    const wordCount = editor.plugins.get('WordCount');
                    const wordCountElement = element.querySelector(`#${scriptId}-word-count`);
                    if (wordCountElement) {
                        wordCountElement.innerHTML = '';
                        wordCountElement.appendChild(wordCount.wordCountContainer);
                    }
                }

                editors[textarea.id] = editor;
                textarea.removeAttribute('data-processing');
                textarea.setAttribute('data-processed', '1');

                if (callbacks[textarea.id]) {
                    callbacks[textarea.id](editor);
                }
            })
            .catch((error) => {
                textarea.removeAttribute('data-processing');
                console.error(error);
            });
    });

    window.editors = editors;
}

function registerCallback(id, callback) {
    callbacks[id] = callback;
}

function unregisterCallback(id) {
    callbacks[id] = null;
}

window.ClassicEditor = ClassicEditor;
window.ckeditorRegisterCallback = registerCallback;
window.ckeditorUnregisterCallback = unregisterCallback;
window.editors = editors;

document.addEventListener('DOMContentLoaded', () => {
    createEditors();

    if (typeof django === 'object' && django.jQuery) {
        django.jQuery(document).on('formset:added', () => {
            createEditors();
        });
    }

    const observer = new MutationObserver((mutations) => {
        mutations
            .flatMap(({ addedNodes }) => Array.from(addedNodes))
            .filter((node) => node.nodeType === 1)
            .forEach((node) => {
                createEditors(node);
            });
    });

    observer.observe(document.body, { childList: true, subtree: true });
});
