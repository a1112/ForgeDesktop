#include "tray.h"

#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusObjectPath>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QRegularExpression>
#include <QSet>

namespace {
constexpr auto Service = "org.kde.StatusNotifierWatcher";
constexpr auto Path = "/StatusNotifierWatcher";
constexpr auto View = "org.forge.DesktopTray1";
constexpr qsizetype MaxSnapshot = 65536;
const QRegularExpression ServiceName(QStringLiteral("^(:[A-Za-z0-9_.-]+|[A-Za-z_][A-Za-z0-9_.-]+)$"));
const QRegularExpression IconName(QStringLiteral("^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"));

QDBusMessage call(const QString &interface, const QString &method,
                  const QVariantList &arguments = {}) {
    auto message = QDBusMessage::createMethodCall(QString::fromLatin1(Service),
        QString::fromLatin1(Path), interface, method);
    message.setArguments(arguments);
    return message;
}
}

Tray::Tray(QObject *parent) : QObject(parent) {
    m_retry.setInterval(1000);
    connect(&m_retry, &QTimer::timeout, this, &Tray::refresh);
    auto bus = QDBusConnection::sessionBus();
    m_watcher = new QDBusServiceWatcher(QString::fromLatin1(Service), bus,
        QDBusServiceWatcher::WatchForOwnerChange, this);
    connect(m_watcher, &QDBusServiceWatcher::serviceOwnerChanged,
            this, [this] { refresh(); });
    bus.connect(QString::fromLatin1(Service), QString::fromLatin1(Path),
        QString::fromLatin1(View), QStringLiteral("Changed"), this, SLOT(refresh()));
    refresh();
}

bool Tray::parseSnapshot(const QString &json, QVariantList *entries) {
    if (!entries || json.toUtf8().size() > MaxSnapshot) return false;
    QJsonParseError error;
    const auto doc = QJsonDocument::fromJson(json.toUtf8(), &error);
    if (error.error != QJsonParseError::NoError || !doc.isObject()) return false;
    const auto root = doc.object();
    if (root.value(QStringLiteral("version")).toInt() != 1 ||
        !root.value(QStringLiteral("items")).isArray()) return false;
    const auto items = root.value(QStringLiteral("items")).toArray();
    if (items.size() > 32) return false;
    QVariantList parsed;
    QSet<QString> ids;
    for (const auto &entry : items) {
        if (!entry.isObject()) continue;
        const auto item = entry.toObject();
        const QString id = item.value(QStringLiteral("id")).toString();
        const auto slash = id.indexOf('/');
        const QString service = id.left(slash);
        const QString path = id.mid(slash);
        const QString title = item.value(QStringLiteral("title")).toString();
        const QString icon = item.value(QStringLiteral("iconName")).toString();
        const QString status = item.value(QStringLiteral("status")).toString();
        const QJsonValue hasMenuValue = item.value(QStringLiteral("hasMenu"));
        const bool hasMenu = hasMenuValue.toBool();
        const QJsonValue itemIsMenuValue = item.value(QStringLiteral("itemIsMenu"));
        const bool itemIsMenu = itemIsMenuValue.toBool();
        const QJsonValue menuLoadingValue = item.value(QStringLiteral("menuLoading"));
        const QJsonValue menuFailedValue = item.value(QStringLiteral("menuFailed"));
        const QJsonValue parentValue = item.value(QStringLiteral("menuParent"));
        const int menuParent = parentValue.toInt();
        const QJsonValue menuValue = item.value(QStringLiteral("menu"));
        if (id.size() > 448 || slash < 1 ||
            !ServiceName.match(service).hasMatch() ||
            QDBusObjectPath(path).path() != path || ids.contains(id) ||
            title.isEmpty() || title.size() > 128 ||
            (!icon.isEmpty() && !IconName.match(icon).hasMatch()) ||
            (status != QStringLiteral("Active") &&
             status != QStringLiteral("NeedsAttention")) ||
            (!hasMenuValue.isUndefined() && !hasMenuValue.isBool()) ||
            (!itemIsMenuValue.isUndefined() && !itemIsMenuValue.isBool()) ||
            (!menuLoadingValue.isUndefined() && !menuLoadingValue.isBool()) ||
            (!menuFailedValue.isUndefined() && !menuFailedValue.isBool()) ||
            (!parentValue.isUndefined() && (!parentValue.isDouble() || menuParent < 0)) ||
            (!menuValue.isUndefined() && !menuValue.isArray())) continue;
        QVariantList menu;
        if (menuValue.isArray()) {
            const auto menuItems = menuValue.toArray();
            if (menuItems.size() > 64) continue;
            bool validMenu = true;
            QSet<int> menuIds;
            for (const auto &menuValue : menuItems) {
                if (!menuValue.isObject()) { validMenu = false; break; }
                const auto menuItem = menuValue.toObject();
                const int menuId = menuItem.value(QStringLiteral("id")).toInt();
                const QString label = menuItem.value(QStringLiteral("label")).toString();
                if (menuId <= 0 || menuIds.contains(menuId) || label.size() > 128 ||
                    !menuItem.value(QStringLiteral("enabled")).isBool() ||
                    !menuItem.value(QStringLiteral("separator")).isBool() ||
                    !menuItem.value(QStringLiteral("submenu")).isBool() ||
                    !menuItem.value(QStringLiteral("checked")).isBool()) {
                    validMenu = false; break;
                }
                menuIds.insert(menuId);
                menu.append(QVariantMap{{QStringLiteral("id"), menuId},
                    {QStringLiteral("label"), label},
                    {QStringLiteral("enabled"), menuItem.value(QStringLiteral("enabled")).toBool()},
                    {QStringLiteral("separator"), menuItem.value(QStringLiteral("separator")).toBool()},
                    {QStringLiteral("submenu"), menuItem.value(QStringLiteral("submenu")).toBool()},
                    {QStringLiteral("checked"), menuItem.value(QStringLiteral("checked")).toBool()}});
            }
            if (!validMenu) continue;
        }
        ids.insert(id);
        parsed.append(QVariantMap{{QStringLiteral("id"), id},
            {QStringLiteral("title"), title},
            {QStringLiteral("iconName"), icon},
            {QStringLiteral("status"), status},
            {QStringLiteral("hasMenu"), hasMenu},
            {QStringLiteral("itemIsMenu"), itemIsMenu},
            {QStringLiteral("menuLoading"), menuLoadingValue.toBool()},
            {QStringLiteral("menuFailed"), menuFailedValue.toBool()},
            {QStringLiteral("menuParent"), menuParent},
            {QStringLiteral("menu"), menu}});
    }
    *entries = parsed;
    return true;
}

void Tray::setState(QVariantList entries, bool online) {
    if (online) m_retry.stop();
    else if (!m_retry.isActive()) m_retry.start();
    if (m_entries == entries && m_online == online) return;
    m_entries = std::move(entries);
    m_online = online;
    emit changed();
}

void Tray::refresh() {
    const quint64 request = ++m_request;
    auto bus = QDBusConnection::sessionBus();
    if (!bus.isConnected()) { setState({}, false); return; }
    auto *pending = new QDBusPendingCallWatcher(
        bus.asyncCall(call(QString::fromLatin1(View), QStringLiteral("Snapshot")), 1000),
        this);
    connect(pending, &QDBusPendingCallWatcher::finished, this,
            [this, request](QDBusPendingCallWatcher *done) {
        const QDBusPendingReply<QString> reply = *done;
        done->deleteLater();
        if (request != m_request) return;
        QVariantList entries;
        if (reply.isError() || !parseSnapshot(reply.value(), &entries)) {
            setState({}, false);
            return;
        }
        setState(std::move(entries), true);
        auto bus = QDBusConnection::sessionBus();
        bus.asyncCall(call(QString::fromLatin1(Service),
            QStringLiteral("RegisterStatusNotifierHost"), {bus.baseService()}), 1000);
    });
}

void Tray::activate(const QString &id, int x, int y, bool context) {
    if (!m_online) return;
    bool found = false;
    for (const auto &entry : m_entries) {
        if (entry.toMap().value(QStringLiteral("id")).toString() == id) {
            found = true; break;
        }
    }
    if (!found) return;
    QDBusConnection::sessionBus().asyncCall(call(QString::fromLatin1(View),
        QStringLiteral("Activate"), {id, x, y, context}), 1000);
}

void Tray::requestMenu(const QString &id, int parentId) {
    if (!m_online || parentId < 0) return;
    for (const auto &entry : m_entries) {
        const auto item = entry.toMap();
        if (item.value(QStringLiteral("id")).toString() != id ||
            !item.value(QStringLiteral("hasMenu")).toBool()) continue;
        if (parentId != 0) {
            bool submenu = false;
            for (const auto &value : item.value(QStringLiteral("menu")).toList()) {
                const auto action = value.toMap();
                if (action.value(QStringLiteral("id")).toInt() == parentId &&
                    action.value(QStringLiteral("submenu")).toBool()) {
                    submenu = true; break;
                }
            }
            if (!submenu) return;
        }
        QDBusConnection::sessionBus().asyncCall(call(QString::fromLatin1(View),
            QStringLiteral("RequestMenu"), {id, parentId}), 1000);
        return;
    }
}

void Tray::selectMenu(const QString &id, int menuId) {
    if (!m_online || menuId <= 0) return;
    for (const auto &entry : m_entries) {
        const auto item = entry.toMap();
        if (item.value(QStringLiteral("id")).toString() != id) continue;
        for (const auto &value : item.value(QStringLiteral("menu")).toList()) {
            const auto action = value.toMap();
            if (action.value(QStringLiteral("id")).toInt() == menuId &&
                action.value(QStringLiteral("enabled")).toBool() &&
                !action.value(QStringLiteral("separator")).toBool() &&
                !action.value(QStringLiteral("submenu")).toBool()) {
                QDBusConnection::sessionBus().asyncCall(call(QString::fromLatin1(View),
                    QStringLiteral("SelectMenu"), {id, menuId}), 1000);
                return;
            }
        }
        return;
    }
}
