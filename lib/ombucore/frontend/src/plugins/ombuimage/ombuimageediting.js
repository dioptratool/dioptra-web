import { Command, Plugin, Widget, toWidget } from 'ckeditor5';

function createCaptionElement(writer, caption) {
    return writer.createRawElement('span', { class: 'ombu-image__caption' }, (domElement) => {
        domElement.textContent = caption;
    });
}

function findCaptionElement(viewElement) {
    for (const child of viewElement.getChildren()) {
        if (child.is('element', 'span') && child.hasClass('ombu-image__caption')) {
            return child;
        }
    }
    return null;
}

export class InsertOmbuImageCommand extends Command {
    execute({ objInfo, caption = '', align = 'center' }) {
        this.editor.model.change((writer) => {
            const element = writer.createElement('ombuImage', {
                objInfo,
                caption,
                align,
            });
            this.editor.model.insertObject(element, null, null, { setSelection: 'on' });
        });
    }

    refresh() {
        const model = this.editor.model;
        const selection = model.document.selection;
        const allowedIn = model.schema.findAllowedParent(selection.getFirstPosition(), 'ombuImage');
        this.isEnabled = allowedIn !== null;
    }
}

export class SetOmbuImageAlignCommand extends Command {
    execute(align) {
        const element = this.editor.model.document.selection.getSelectedElement();
        if (element && element.is('element', 'ombuImage')) {
            this.editor.model.change((writer) => {
                writer.setAttribute('align', align, element);
            });
        }
    }

    refresh() {
        const element = this.editor.model.document.selection.getSelectedElement();
        this.isEnabled = !!(element && element.is('element', 'ombuImage'));
        if (this.isEnabled) {
            this.value = element.getAttribute('align') || 'center';
        }
    }
}

export class OmbuImageEditing extends Plugin {
    static get pluginName() {
        return 'OmbuImageEditing';
    }

    static get requires() {
        return [Widget];
    }

    init() {
        const editor = this.editor;

        editor.model.schema.register('ombuImage', {
            inheritAllFrom: '$blockObject',
            allowAttributes: ['objInfo', 'caption', 'align'],
        });

        editor.conversion.for('upcast').elementToElement({
            view: {
                name: 'div',
                attributes: { 'data-ombuimage': true },
            },
            model: (viewElement, { writer }) => {
                let data = {};
                try {
                    data = JSON.parse(viewElement.getAttribute('data-ombuimage') || '{}');
                } catch {
                    data = {};
                }

                return writer.createElement('ombuImage', {
                    objInfo: data.objInfo || {},
                    caption: data.caption || '',
                    align: data.align || 'center',
                });
            },
        });

        editor.conversion.for('dataDowncast').elementToElement({
            model: 'ombuImage',
            view: (modelElement, { writer }) => {
                const data = {
                    objInfo: modelElement.getAttribute('objInfo'),
                    caption: modelElement.getAttribute('caption'),
                    align: modelElement.getAttribute('align'),
                };
                return writer.createContainerElement('div', {
                    'data-ombuimage': JSON.stringify(data),
                });
            },
        });

        editor.conversion.for('editingDowncast').elementToElement({
            model: 'ombuImage',
            view: (modelElement, { writer }) => {
                const objInfo = modelElement.getAttribute('objInfo') || {};
                const caption = modelElement.getAttribute('caption') || '';
                const align = modelElement.getAttribute('align') || 'center';
                const container = writer.createContainerElement('div', {
                    class: `ombu-widget ombu-image ombu-image--${align}`,
                });

                if (objInfo.image_url) {
                    writer.insert(
                        writer.createPositionAt(container, 0),
                        writer.createEmptyElement('img', { src: objInfo.image_url })
                    );
                }

                if (caption) {
                    writer.insert(writer.createPositionAt(container, 'end'), createCaptionElement(writer, caption));
                }

                return toWidget(container, writer, { label: 'image widget' });
            },
        });

        editor.conversion.for('editingDowncast').add((dispatcher) => {
            dispatcher.on('attribute:align:ombuImage', (evt, data, conversionApi) => {
                const viewElement = conversionApi.mapper.toViewElement(data.item);
                if (!viewElement) {
                    return;
                }

                conversionApi.writer.removeClass(
                    ['ombu-image--left', 'ombu-image--center', 'ombu-image--right'],
                    viewElement
                );
                conversionApi.writer.addClass(`ombu-image--${data.attributeNewValue || 'center'}`, viewElement);
            });

            dispatcher.on('attribute:caption:ombuImage', (evt, data, conversionApi) => {
                const viewElement = conversionApi.mapper.toViewElement(data.item);
                if (!viewElement) {
                    return;
                }

                const writer = conversionApi.writer;
                const existingCaption = findCaptionElement(viewElement);
                const nextCaption = data.attributeNewValue || '';

                if (existingCaption) {
                    writer.remove(existingCaption);
                }
                if (nextCaption) {
                    writer.insert(writer.createPositionAt(viewElement, 'end'), createCaptionElement(writer, nextCaption));
                }
            });
        });

        editor.commands.add('insertOmbuImage', new InsertOmbuImageCommand(editor));
        editor.commands.add('setOmbuImageAlign', new SetOmbuImageAlignCommand(editor));
    }
}
