import { ButtonView, Plugin } from 'ckeditor5';

const CLIPBOARD_ICON =
    '<svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M13 2a1 1 0 0 1 1 1v1h1.5A1.5 1.5 0 0 1 17 5.5v12a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 3 17.5v-12A1.5 1.5 0 0 1 4.5 4H6V3a1 1 0 0 1 1-1h6Zm-1 1.5H8v1h4v-1ZM15.5 5.5h-11v12h11v-12Z"/>' +
    '<path d="M7 9h6v1H7zm0 3h4v1H7z" opacity=".6"/>' +
    '</svg>';

export class PastePlainTextToggle extends Plugin {
    static get pluginName() {
        return 'PastePlainTextToggle';
    }

    init() {
        const editor = this.editor;
        this.isActive = false;

        editor.ui.componentFactory.add('pasteAsPlainText', (locale) => {
            const button = new ButtonView(locale);

            button.set({
                label: 'Paste as plain text',
                icon: CLIPBOARD_ICON,
                tooltip: true,
                isToggleable: true,
                isOn: this.isActive,
            });

            button.on('execute', () => {
                this.isActive = !this.isActive;
                button.isOn = this.isActive;
            });

            return button;
        });

        editor.plugins.get('ClipboardPipeline').on(
            'inputTransformation',
            (evt, data) => {
                if (!this.isActive) {
                    return;
                }

                const plain = data.dataTransfer.getData('text/plain');
                if (!plain) {
                    return;
                }

                data.content = editor.data.htmlProcessor.toView(
                    plain
                        .split(/\r?\n\r?\n/)
                        .map((block) => {
                            const escaped = block
                                .replace(/&/g, '&amp;')
                                .replace(/</g, '&lt;')
                                .replace(/>/g, '&gt;')
                                .replace(/\n/g, '<br>');
                            return `<p>${escaped}</p>`;
                        })
                        .join('')
                );
            },
            { priority: 'high' }
        );
    }
}
