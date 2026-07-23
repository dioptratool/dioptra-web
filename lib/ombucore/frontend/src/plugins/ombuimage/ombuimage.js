import { Plugin } from 'ckeditor5';

import { OmbuImageEditing } from './ombuimageediting.js';
import { OmbuImageUI } from './ombuimageui.js';

export class OmbuImage extends Plugin {
    static get pluginName() {
        return 'OmbuImage';
    }

    static get requires() {
        return [OmbuImageEditing, OmbuImageUI];
    }
}
