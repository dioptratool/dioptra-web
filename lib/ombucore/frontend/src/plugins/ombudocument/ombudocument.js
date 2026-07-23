import { Plugin } from 'ckeditor5';

import { OmbuDocumentEditing } from './ombudocumentediting.js';
import { OmbuDocumentUI } from './ombudocumentui.js';

export class OmbuDocument extends Plugin {
    static get pluginName() {
        return 'OmbuDocument';
    }

    static get requires() {
        return [OmbuDocumentEditing, OmbuDocumentUI];
    }
}
