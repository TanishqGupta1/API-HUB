const { src, dest } = require('gulp');

function buildIcons() {
    return src('credentials/onprintshop.svg')
        .pipe(dest('dist/credentials'));
}

function buildNodeIcons() {
    return src('nodes/**/onprintshop.svg')
        .pipe(dest('dist/nodes'));
}

exports['build:icons'] = buildIcons;
exports['build:node-icons'] = buildNodeIcons;
exports.default = buildIcons;
