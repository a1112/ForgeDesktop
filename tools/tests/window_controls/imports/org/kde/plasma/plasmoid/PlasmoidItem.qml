import QtQuick
Item {
    function i18n(text, argument) { return argument === undefined ? text : text.replace("%1", argument); }
}
