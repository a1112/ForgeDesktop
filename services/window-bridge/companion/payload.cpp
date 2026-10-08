#include "payload.h"
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QRegularExpression>
#include <QSet>
#include <cmath>
bool validObservation(const QByteArray &bytes) {
    if (bytes.size() > 65536) return false;
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(bytes, &error);
    if (error.error != QJsonParseError::NoError || !document.isObject()) return false;
    const auto object = document.object();
    const auto type = object.value("type").toString();
    const QSet<QString> allowed = type == "window"
        ? QSet<QString>{"type", "id", "parent", "kind", "geometry", "caption", "app_id"}
        : QSet<QString>{"type", "id"};
    if (type != "window" && type != "closed" && type != "active") return false;
    for (const auto &key : object.keys()) if (!allowed.contains(key)) return false;
    if (!object.contains("id")) return false;
    const auto identity = object.value("id");
    if (type == "active" && identity.isNull()) return true;
    static const QRegularExpression id("^[a-zA-Z0-9{}_\\-]{1,128}$");
    if (!identity.isString() || !id.match(identity.toString()).hasMatch()) return false;
    if (type != "window") return true;
    if (!object.contains("parent") || !object.value("caption").isString()
        || !object.value("app_id").isString() || !object.value("geometry").isObject()) return false;
    if (!object.value("parent").isNull()
        && !id.match(object.value("parent").toString()).hasMatch()) return false;
    const auto kind = object.value("kind").toString();
    if (kind != "normal" && kind != "dialog" && kind != "popup") return false;
    if (object.value("caption").toString().size() > 4096 || object.value("app_id").toString().size() > 1024) return false;
    const auto g = object.value("geometry").toObject();
    if (g.size() != 4) return false;
    for (const auto &key : {"x", "y", "width", "height"}) {
        if (!g.value(key).isDouble()) return false;
        const double value = g.value(key).toDouble();
        if (!std::isfinite(value) || value != std::floor(value)) return false;
        if (QString(key) == "x" || QString(key) == "y") { if (std::abs(value) > 1000000) return false; }
        else if (value < 1 || value > 16384) return false;
    }
    return true;
}
