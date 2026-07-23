import { ButtonView, Plugin, WidgetToolbarRepository } from 'ckeditor5';

const DOCUMENT_ICON =
    '<svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path d="M5 1h8l4 4v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2zm7 1.5V6h3.5L12 2.5zM5 9h10v1H5V9zm0 3h10v1H5v-1zm0 3h7v1H5v-1z"/></svg>';
const ALIGN_LEFT_ICON =
    '<svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M2 3h16v1.5H2zm11.5 4H18v1.5h-4.5zm0 4H18v1.5h-4.5zM2 15h16v1.5H2z"/>' +
    '<rect x="2" y="6" width="8" height="6" rx=".75"/></svg>';
const ALIGN_RIGHT_ICON =
    '<svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M2 3h16v1.5H2zm0 4h4.5v1.5H2zm0 4h4.5v1.5H2zM2 15h16v1.5H2z"/>' +
    '<rect x="10" y="6" width="8" height="6" rx=".75"/></svg>';

const ALIGNMENTS = [
    { name: 'ombuDocumentAlignLeft', align: 'left', label: 'Align left', icon: ALIGN_LEFT_ICON },
    { name: 'ombuDocumentAlignRight', align: 'right', label: 'Align right', icon: ALIGN_RIGHT_ICON },
];

export class OmbuDocumentUI extends Plugin {
    static get pluginName() {
        return 'OmbuDocumentUI';
    }

    static get requires() {
        return [WidgetToolbarRepository];
    }

    init() {
        const editor = this.editor;

        editor.ui.componentFactory.add('ombuDocument', (locale) => {
            const button = new ButtonView(locale);
            const command = editor.commands.get('insertOmbuDocument');

            button.set({ label: 'Document', icon: DOCUMENT_ICON, tooltip: true });
            button.bind('isEnabled').to(command);
            button.on('execute', () => this.openPanelSelector());

            return button;
        });

        this.registerAlignmentButtons();
        this.setupDoubleClickHandler();
    }

    afterInit() {
        const widgetToolbarRepository = this.editor.plugins.get(WidgetToolbarRepository);
        widgetToolbarRepository.register('ombuDocument', {
            ariaLabel: 'Document toolbar',
            items: ['ombuDocumentAlignLeft', 'ombuDocumentAlignRight'],
            getRelatedElement: (viewSelection) => {
                const viewElement = viewSelection.getSelectedElement();
                return viewElement && viewElement.hasClass('ombu-document') ? viewElement : null;
            },
        });
    }

    registerAlignmentButtons() {
        const editor = this.editor;

        for (const { name, align, label, icon } of ALIGNMENTS) {
            editor.ui.componentFactory.add(name, (locale) => {
                const button = new ButtonView(locale);
                const command = editor.commands.get('setOmbuDocumentAlign');

                button.set({ label, icon, tooltip: true, isToggleable: true });
                button.bind('isEnabled').to(command);
                button.bind('isOn').to(command, 'value', (value) => value === align);
                button.on('execute', () => {
                    editor.execute('setOmbuDocumentAlign', align);
                    editor.editing.view.focus();
                });

                return button;
            });
        }
    }

    openPanelSelector(existingElement = null) {
        const editor = this.editor;

        if (typeof Panels === 'undefined') {
            console.error('Panels is not available. Cannot open document selector.');
            return;
        }

        Panels.open('/panels/assets/documentasset/select/').then((data) => {
            if (!data || !data.info) {
                return;
            }

            if (existingElement) {
                editor.model.change((writer) => {
                    writer.setAttribute('objInfo', data.info, existingElement);
                });
            } else {
                editor.execute('insertOmbuDocument', {
                    objInfo: data.info,
                    align: 'left',
                });
            }
        });
    }

    setupDoubleClickHandler() {
        this.listenTo(this.editor.editing.view.document, 'dblclick', () => {
            const modelElement = this.getSelectedOmbuDocumentElement();
            if (modelElement) {
                this.openPanelSelector(modelElement);
            }
        });
    }

    getSelectedOmbuDocumentElement() {
        const selectedElement = this.editor.model.document.selection.getSelectedElement();
        return selectedElement && selectedElement.is('element', 'ombuDocument') ? selectedElement : null;
    }
}
