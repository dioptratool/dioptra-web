import { Command, Plugin, Widget, toWidget } from 'ckeditor5';

export class InsertOmbuDocumentCommand extends Command {
    execute({ objInfo, align = 'left' }) {
        this.editor.model.change((writer) => {
            const element = writer.createElement('ombuDocument', {
                objInfo,
                align,
            });
            this.editor.model.insertObject(element, null, null, { setSelection: 'on' });
        });
    }

    refresh() {
        const model = this.editor.model;
        const selection = model.document.selection;
        const allowedIn = model.schema.findAllowedParent(selection.getFirstPosition(), 'ombuDocument');
        this.isEnabled = allowedIn !== null;
    }
}

export class SetOmbuDocumentAlignCommand extends Command {
    execute(align) {
        const element = this.editor.model.document.selection.getSelectedElement();
        if (element && element.is('element', 'ombuDocument')) {
            this.editor.model.change((writer) => {
                writer.setAttribute('align', align, element);
            });
        }
    }

    refresh() {
        const element = this.editor.model.document.selection.getSelectedElement();
        this.isEnabled = !!(element && element.is('element', 'ombuDocument'));
        if (this.isEnabled) {
            this.value = element.getAttribute('align') || 'left';
        }
    }
}

export class OmbuDocumentEditing extends Plugin {
    static get pluginName() {
        return 'OmbuDocumentEditing';
    }

    static get requires() {
        return [Widget];
    }

    init() {
        const editor = this.editor;

        editor.model.schema.register('ombuDocument', {
            inheritAllFrom: '$blockObject',
            allowAttributes: ['objInfo', 'align'],
        });

        editor.conversion.for('upcast').elementToElement({
            view: {
                name: 'div',
                attributes: { 'data-ombudocument': true },
            },
            model: (viewElement, { writer }) => {
                let data = {};
                try {
                    data = JSON.parse(viewElement.getAttribute('data-ombudocument') || '{}');
                } catch {
                    data = {};
                }

                return writer.createElement('ombuDocument', {
                    objInfo: data.objInfo || {},
                    align: data.align || 'left',
                });
            },
        });

        editor.conversion.for('dataDowncast').elementToElement({
            model: 'ombuDocument',
            view: (modelElement, { writer }) => {
                const data = {
                    objInfo: modelElement.getAttribute('objInfo'),
                    align: modelElement.getAttribute('align'),
                };
                return writer.createContainerElement('div', {
                    'data-ombudocument': JSON.stringify(data),
                });
            },
        });

        editor.conversion.for('editingDowncast').elementToElement({
            model: 'ombuDocument',
            view: (modelElement, { writer }) => {
                const objInfo = modelElement.getAttribute('objInfo') || {};
                const align = modelElement.getAttribute('align') || 'left';

                const container = writer.createContainerElement('div', {
                    class: `ombu-widget ombu-document ombu-document--${align}`,
                });

                if (objInfo.title) {
                    const titleElement = writer.createRawElement(
                        'div',
                        { class: 'ombu-document__title' },
                        (domElement) => {
                            domElement.textContent = objInfo.title;
                        }
                    );
                    writer.insert(writer.createPositionAt(container, 0), titleElement);
                }

                const typeElement = writer.createRawElement(
                    'div',
                    { class: 'ombu-document__type' },
                    (domElement) => {
                        domElement.textContent = 'Document';
                    }
                );
                writer.insert(writer.createPositionAt(container, 'end'), typeElement);

                return toWidget(container, writer, { label: 'document widget' });
            },
        });

        editor.conversion.for('editingDowncast').add((dispatcher) => {
            dispatcher.on('attribute:align:ombuDocument', (evt, data, conversionApi) => {
                const viewElement = conversionApi.mapper.toViewElement(data.item);
                if (!viewElement) {
                    return;
                }

                conversionApi.writer.removeClass(['ombu-document--left', 'ombu-document--right'], viewElement);
                conversionApi.writer.addClass(`ombu-document--${data.attributeNewValue || 'left'}`, viewElement);
            });
        });

        editor.commands.add('insertOmbuDocument', new InsertOmbuDocumentCommand(editor));
        editor.commands.add('setOmbuDocumentAlign', new SetOmbuDocumentAlignCommand(editor));
    }
}
