import { ButtonView, Plugin, WidgetToolbarRepository } from 'ckeditor5';

const IMAGE_ICON =
    '<svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path d="M6.91 10.54c.26-.23.64-.21.88.03l3.36 3.14 2.23-2.06a.64.64 0 0 1 .87 0l2.52 2.97V4.5H3.2v10.12l3.71-4.08zm10.27-7.51c.6 0 1.09.47 1.09 1.05v11.84c0 .59-.49 1.06-1.09 1.06H2.79c-.6 0-1.09-.47-1.09-1.06V4.08c0-.58.49-1.05 1.1-1.05h14.38zm-5.22 5.56a1.96 1.96 0 1 1 0-3.92 1.96 1.96 0 0 1 0 3.92z"/></svg>';
const ALIGN_LEFT_ICON =
    '<svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M2 3h16v1.5H2zm11.5 4H18v1.5h-4.5zm0 4H18v1.5h-4.5zM2 15h16v1.5H2z"/>' +
    '<rect x="2" y="6" width="8" height="6" rx=".75"/></svg>';
const ALIGN_CENTER_ICON =
    '<svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M2 3h16v1.5H2zm0 12h16v1.5H2z"/>' +
    '<rect x="5" y="6" width="10" height="6" rx=".75"/></svg>';
const ALIGN_RIGHT_ICON =
    '<svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M2 3h16v1.5H2zm0 4h4.5v1.5H2zm0 4h4.5v1.5H2zM2 15h16v1.5H2z"/>' +
    '<rect x="10" y="6" width="8" height="6" rx=".75"/></svg>';
const CAPTION_ICON =
    '<svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M3 4h14v2H3zm0 5h14v2H3zm0 5h9v2H3z"/></svg>';

const ALIGNMENTS = [
    { name: 'ombuImageAlignLeft', align: 'left', label: 'Align left', icon: ALIGN_LEFT_ICON },
    { name: 'ombuImageAlignCenter', align: 'center', label: 'Align center', icon: ALIGN_CENTER_ICON },
    { name: 'ombuImageAlignRight', align: 'right', label: 'Align right', icon: ALIGN_RIGHT_ICON },
];

export class OmbuImageUI extends Plugin {
    static get pluginName() {
        return 'OmbuImageUI';
    }

    static get requires() {
        return [WidgetToolbarRepository];
    }

    init() {
        const editor = this.editor;

        editor.ui.componentFactory.add('ombuImage', (locale) => {
            const button = new ButtonView(locale);
            const command = editor.commands.get('insertOmbuImage');

            button.set({ label: 'Image', icon: IMAGE_ICON, tooltip: true });
            button.bind('isEnabled').to(command);
            button.on('execute', () => this.openPanelSelector());

            return button;
        });

        this.registerAlignmentButtons();
        this.registerCaptionButton();
        this.setupDoubleClickHandler();
    }

    afterInit() {
        const widgetToolbarRepository = this.editor.plugins.get(WidgetToolbarRepository);
        widgetToolbarRepository.register('ombuImage', {
            ariaLabel: 'Image toolbar',
            items: [
                'ombuImageEditCaption',
                'ombuImageAlignLeft',
                'ombuImageAlignCenter',
                'ombuImageAlignRight',
            ],
            getRelatedElement: (viewSelection) => {
                const viewElement = viewSelection.getSelectedElement();
                return viewElement && viewElement.hasClass('ombu-image') ? viewElement : null;
            },
        });
    }

    registerAlignmentButtons() {
        const editor = this.editor;

        for (const { name, align, label, icon } of ALIGNMENTS) {
            editor.ui.componentFactory.add(name, (locale) => {
                const button = new ButtonView(locale);
                const command = editor.commands.get('setOmbuImageAlign');

                button.set({ label, icon, tooltip: true, isToggleable: true });
                button.bind('isEnabled').to(command);
                button.bind('isOn').to(command, 'value', (value) => value === align);
                button.on('execute', () => {
                    editor.execute('setOmbuImageAlign', align);
                    editor.editing.view.focus();
                });

                return button;
            });
        }
    }

    registerCaptionButton() {
        const editor = this.editor;

        editor.ui.componentFactory.add('ombuImageEditCaption', (locale) => {
            const button = new ButtonView(locale);

            button.set({ label: 'Edit caption', icon: CAPTION_ICON, tooltip: true });
            button.on('execute', () => {
                const modelElement = this.getSelectedOmbuImageElement();
                if (!modelElement) {
                    return;
                }

                const caption = window.prompt('Image caption', modelElement.getAttribute('caption') || '');
                if (caption === null) {
                    return;
                }

                editor.model.change((writer) => {
                    writer.setAttribute('caption', caption, modelElement);
                });
                editor.editing.view.focus();
            });

            return button;
        });
    }

    openPanelSelector(existingElement = null) {
        const editor = this.editor;

        if (typeof Panels === 'undefined') {
            console.error('Panels is not available. Cannot open image selector.');
            return;
        }

        Panels.open('/panels/assets/imageasset/select/').then((data) => {
            if (!data || !data.info) {
                return;
            }

            if (existingElement) {
                editor.model.change((writer) => {
                    writer.setAttribute('objInfo', data.info, existingElement);
                });
            } else {
                editor.execute('insertOmbuImage', {
                    objInfo: data.info,
                    caption: '',
                    align: 'center',
                });
            }
        });
    }

    setupDoubleClickHandler() {
        this.listenTo(this.editor.editing.view.document, 'dblclick', () => {
            const modelElement = this.getSelectedOmbuImageElement();
            if (modelElement) {
                this.openPanelSelector(modelElement);
            }
        });
    }

    getSelectedOmbuImageElement() {
        const selectedElement = this.editor.model.document.selection.getSelectedElement();
        return selectedElement && selectedElement.is('element', 'ombuImage') ? selectedElement : null;
    }
}
