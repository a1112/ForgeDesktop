#include "notifications.h"

#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>

namespace {
constexpr auto Service = "org.freedesktop.Notifications";
constexpr auto Path = "/org/freedesktop/Notifications";
constexpr auto View = "org.forge.DesktopNotifications1";

QDBusMessage call(const QString &method, const QVariantList &arguments = {}) {
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(Service), QString::fromLatin1(Path),
        QString::fromLatin1(View), method);
    message.setArguments(arguments);
    return message;
}
}

Notifications::Notifications(QObject *parent) : QObject(parent) {
    m_retry.setInterval(1000);
    connect(&m_retry, &QTimer::timeout, this, &Notifications::refresh);
    QDBusConnection bus = QDBusConnection::sessionBus();
    m_watcher = new QDBusServiceWatcher(QString::fromLatin1(Service), bus,
        QDBusServiceWatcher::WatchForOwnerChange, this);
    connect(m_watcher, &QDBusServiceWatcher::serviceOwnerChanged,
            this, [this] { refresh(); });
    bus.connect(QString::fromLatin1(Service), QString::fromLatin1(Path),
                QString::fromLatin1(View), QStringLiteral("Changed"),
                this, SLOT(refresh()));
    refresh();
}

bool Notifications::parseSnapshot(const QString &json, QVariantList *entries) {
    // The producer holds at most 64 entries. Its field limits total 21,888
    // UTF-16 units per entry; JSON escaping costs at most six bytes per unit.
    // Including keys and framing, every valid snapshot fits within 10 MiB.
    constexpr qsizetype MaxSnapshotBytes = 10 * 1024 * 1024;
    if (!entries || json.size() > MaxSnapshotBytes) return false;
    const QByteArray bytes = json.toUtf8();
    if (bytes.size() > MaxSnapshotBytes) return false;
    QJsonParseError error;
    const QJsonDocument doc = QJsonDocument::fromJson(bytes, &error);
    if (error.error != QJsonParseError::NoError || !doc.isObject()) return false;
    const QJsonObject root = doc.object();
    if (root.value(QStringLiteral("version")).toInt() != 1 ||
        !root.value(QStringLiteral("notifications")).isArray()) return false;
    const QJsonArray items = root.value(QStringLiteral("notifications")).toArray();
    if (items.size() > 64) return false;
    QVariantList parsed;
    for (const QJsonValue &value : items) {
        if (!value.isObject()) return false;
        const QJsonObject item = value.toObject();
        const qint64 id = item.value(QStringLiteral("id")).toInteger();
        const QString app = item.value(QStringLiteral("app")).toString();
        const QString summary = item.value(QStringLiteral("summary")).toString();
        const QString body = item.value(QStringLiteral("body")).toString();
        const QJsonValue actionValue = item.value(QStringLiteral("actions"));
        if (id <= 0 || id > 0xffffffffLL || app.size() > 128 ||
            summary.size() > 1024 || body.size() > 16384 ||
            !actionValue.isArray()) return false;
        const QJsonArray actions = actionValue.toArray();
        if (actions.size() > 16 || actions.size() % 2) return false;
        QStringList labels;
        QVariantList keys;
        for (qsizetype i = 0; i < actions.size(); i += 2) {
            if (!actions[i].isString() || !actions[i + 1].isString() ||
                actions[i].toString().isEmpty() ||
                actions[i].toString().size() > 256 ||
                actions[i + 1].toString().size() > 256) return false;
            keys.append(actions[i].toString());
            labels.append(actions[i + 1].toString());
        }
        parsed.append(QVariantMap{{QStringLiteral("id"), id},
            {QStringLiteral("app"), app}, {QStringLiteral("summary"), summary},
            {QStringLiteral("body"), body},
            {QStringLiteral("actionKeys"), keys},
            {QStringLiteral("actionLabels"), labels}});
    }
    *entries = parsed;
    return true;
}

void Notifications::setState(QVariantList entries, bool online) {
    if (online) m_retry.stop();
    else if (!m_retry.isActive()) m_retry.start();
    if (m_entries == entries && m_online == online) return;
    m_entries = std::move(entries);
    m_online = online;
    emit changed();
}

void Notifications::refresh() {
    const quint64 request = ++m_request;
    QDBusConnection bus = QDBusConnection::sessionBus();
    if (!bus.isConnected()) {
        setState({}, false);
        return;
    }
    auto *watcher = new QDBusPendingCallWatcher(bus.asyncCall(call(QStringLiteral("Snapshot"))), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, request](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<QString> reply = *finished;
        finished->deleteLater();
        if (request != m_request) return;
        QVariantList entries;
        if (reply.isError() || !parseSnapshot(reply.value(), &entries))
            setState({}, false);
        else
            setState(std::move(entries), true);
    });
}

void Notifications::dismiss(quint32 id) {
    if (id == 0 || !m_online) return;
    QDBusConnection::sessionBus().asyncCall(call(QStringLiteral("Dismiss"), {id}));
}

void Notifications::invoke(quint32 id, const QString &action) {
    if (id == 0 || action.isEmpty() || action.size() > 256 || !m_online) return;
    QDBusConnection::sessionBus().asyncCall(call(QStringLiteral("Invoke"), {id, action}));
}
