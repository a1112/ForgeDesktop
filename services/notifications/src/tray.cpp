#include "tray.h"

#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusArgument>
#include <QDBusMessage>
#include <QDBusObjectPath>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusVariant>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>

namespace {
constexpr qsizetype MaxItems = 32;
constexpr auto BusService = "org.freedesktop.DBus";
constexpr auto BusPath = "/org/freedesktop/DBus";
constexpr auto BusInterface = "org.freedesktop.DBus";
const QRegularExpression IconPattern(QStringLiteral("^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"));

QString plain(const QVariantMap &properties, const QString &key, qsizetype limit) {
    QVariant value = properties.value(key);
    if (value.metaType() == QMetaType::fromType<QDBusVariant>())
        value = value.value<QDBusVariant>().variant();
    const QString text = value.toString();
    return text.left(limit);
}

QVariant unbox(QVariant value) {
    if (value.metaType() == QMetaType::fromType<QDBusVariant>())
        return value.value<QDBusVariant>().variant();
    return value;
}

QString menuPath(const QVariantMap &properties) {
    const QVariant value = unbox(properties.value(QStringLiteral("Menu")));
    if (value.metaType() != QMetaType::fromType<QDBusObjectPath>()) return {};
    const QString path = value.value<QDBusObjectPath>().path();
    if (path == QStringLiteral("/NO_DBUSMENU") || path.size() > 256) return {};
    return path;
}

QString normalizedStatus(const QString &status) {
    if (status == QStringLiteral("Passive") ||
        status == QStringLiteral("NeedsAttention")) return status;
    return QStringLiteral("Active");
}

bool parseMenuLayout(const QDBusMessage &reply, int parentId,
                     QJsonArray *entries, QSet<int> *ids,
                     QSet<int> *submenus) {
    if (reply.type() != QDBusMessage::ReplyMessage || reply.arguments().size() != 2 ||
        reply.arguments()[1].metaType() != QMetaType::fromType<QDBusArgument>())
        return false;
    const QDBusArgument layout = reply.arguments()[1].value<QDBusArgument>();
    if (layout.currentType() != QDBusArgument::StructureType ||
        layout.currentSignature() != QStringLiteral("(ia{sv}av)")) return false;
    layout.beginStructure();
    int rootId = -1;
    QVariantMap rootProperties;
    layout >> rootId >> rootProperties;
    if (rootId != parentId) return false;
    QJsonArray parsed;
    QSet<int> parsedIds;
    QSet<int> parsedSubmenus;
    int childrenSeen = 0;
    layout.beginArray();
    while (!layout.atEnd()) {
        if (++childrenSeen > 64) return false;
        QDBusVariant child;
        layout >> child;
        const QVariant variant = child.variant();
        if (variant.metaType() != QMetaType::fromType<QDBusArgument>()) return false;
        const QDBusArgument item = variant.value<QDBusArgument>();
        if (item.currentType() != QDBusArgument::StructureType ||
            item.currentSignature() != QStringLiteral("(ia{sv}av)")) return false;
        item.beginStructure();
        int id = 0;
        QVariantMap props;
        item >> id >> props;
        if (id <= 0 || parsedIds.contains(id)) return false;
        if (unbox(props.value(QStringLiteral("visible"))).isValid() &&
            !unbox(props.value(QStringLiteral("visible"))).toBool()) continue;
        const bool separator = plain(props, QStringLiteral("type"), 32) ==
                               QStringLiteral("separator");
        const QString label = plain(props, QStringLiteral("label"), 128);
        if (!separator && label.isEmpty()) continue;
        const QVariant enabledValue = unbox(props.value(QStringLiteral("enabled")));
        const bool enabled = !enabledValue.isValid() || enabledValue.toBool();
        const bool submenu = plain(props, QStringLiteral("children-display"), 32) ==
                             QStringLiteral("submenu");
        const bool checked = unbox(props.value(QStringLiteral("toggle-state"))).toInt() == 1;
        parsed.append(QJsonObject{{QStringLiteral("id"), id},
            {QStringLiteral("label"), label}, {QStringLiteral("enabled"), enabled},
            {QStringLiteral("separator"), separator},
            {QStringLiteral("submenu"), submenu},
            {QStringLiteral("checked"), checked}});
        parsedIds.insert(id);
        if (submenu) parsedSubmenus.insert(id);
    }
    layout.endArray();
    layout.endStructure();
    *entries = parsed;
    *ids = parsedIds;
    *submenus = parsedSubmenus;
    return true;
}
}

TrayStore::TrayStore(QObject *parent) : QObject(parent) {
    m_refreshTimer.setSingleShot(true);
    m_refreshTimer.setInterval(150);
    connect(&m_refreshTimer, &QTimer::timeout, this, [this] {
        const auto dirty = m_dirtyItems;
        m_dirtyItems.clear();
        for (const auto &id : dirty) refresh(id);
    });
    auto bus = QDBusConnection::sessionBus();
    bus.connect(QString::fromLatin1(BusService), QString::fromLatin1(BusPath),
        QString::fromLatin1(BusInterface), QStringLiteral("NameOwnerChanged"),
        this, SLOT(nameOwnerChanged(QString,QString,QString)));
    for (const QString &interface : {QStringLiteral("org.kde.StatusNotifierItem"),
                                      QStringLiteral("org.freedesktop.StatusNotifierItem")}) {
        for (const QString &signal : {QStringLiteral("NewTitle"), QStringLiteral("NewIcon"),
                                      QStringLiteral("NewAttentionIcon"),
                                      QStringLiteral("NewToolTip")})
            bus.connect({}, {}, interface, signal, this, SLOT(itemSignal(QDBusMessage)));
        bus.connect({}, {}, interface, QStringLiteral("NewStatus"), this,
                    SLOT(statusSignal(QString,QDBusMessage)));
    }
}

bool TrayStore::ownedBy(const QString &sender, const QString &service) const {
    if (service == sender) return true;
    if (service.isEmpty() || service.size() > 192 || service.startsWith(':')) return false;
    auto interface = QDBusConnection::sessionBus().interface();
    if (!interface) return false;
    const auto owner = interface->serviceOwner(service);
    return owner.isValid() && owner.value() == sender;
}

bool TrayStore::registerItem(const QString &sender, const QString &spec,
                             const QString &interface, QString *error) {
    if (spec.isEmpty() || spec.size() > 256) {
        if (error) *error = QStringLiteral("invalid item registration");
        return false;
    }
    QString service = spec;
    QString path = QStringLiteral("/StatusNotifierItem");
    if (spec.startsWith('/')) {
        service = sender;
        path = spec;
    } else if (const qsizetype slash = spec.indexOf('/'); slash >= 0) {
        service = spec.left(slash);
        path = spec.mid(slash);
    }
    if (!ownedBy(sender, service) || path.size() > 256 ||
        QDBusObjectPath(path).path() != path) {
        if (error) *error = QStringLiteral("item is not owned by caller or has invalid path");
        return false;
    }
    const QString id = service + path;
    if (m_items.contains(id)) {
        if (m_items.value(id).owner == sender) return true;
        remove(id);
    }
    if (m_items.size() >= MaxItems) {
        if (error) *error = QStringLiteral("item registry is full");
        return false;
    }
    Item item;
    item.owner = sender;
    item.service = service;
    item.path = path;
    item.interface = interface;
    item.title = service.left(128);
    m_items.insert(id, item);
    m_order.append(id);
    emit itemRegistered(id);
    emit changed();
    refresh(id);
    return true;
}

bool TrayStore::registerHost(const QString &sender, const QString &spec,
                             QString *error) {
    if (!ownedBy(sender, spec) || m_hosts.size() >= MaxItems) {
        if (error) *error = QStringLiteral("host is not owned by caller or registry is full");
        return false;
    }
    const bool first = m_hosts.isEmpty();
    m_hosts.insert(spec, sender);
    if (first) emit hostBecameRegistered();
    return true;
}

void TrayStore::remove(const QString &id) {
    if (!m_items.remove(id)) return;
    m_dirtyItems.remove(id);
    m_order.removeAll(id);
    emit itemUnregistered(id);
    emit changed();
}

void TrayStore::nameOwnerChanged(const QString &name, const QString &,
                                  const QString &newOwner) {
    const auto items = m_order;
    for (const auto &id : items) {
        const auto item = m_items.value(id);
        if ((name == item.owner && newOwner.isEmpty()) ||
            (name == item.service && newOwner != item.owner)) remove(id);
    }
    bool hostRemoved = false;
    for (auto it = m_hosts.begin(); it != m_hosts.end();) {
        if ((name == it.key() && newOwner != it.value()) ||
            (name == it.value() && newOwner.isEmpty())) {
            it = m_hosts.erase(it);
            hostRemoved = true;
        } else ++it;
    }
    if (hostRemoved && m_hosts.isEmpty()) emit hostBecameUnregistered();
}

void TrayStore::refresh(const QString &id) {
    auto it = m_items.find(id);
    if (it == m_items.end()) return;
    if (it->refreshPending) { it->refreshQueued = true; return; }
    it->refreshPending = true;
    const quint64 request = it->request = ++m_nextRequest;
    auto message = QDBusMessage::createMethodCall(it->owner, it->path,
        QStringLiteral("org.freedesktop.DBus.Properties"), QStringLiteral("GetAll"));
    message.setArguments({it->interface});
    auto *pending = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 1000), this);
    connect(pending, &QDBusPendingCallWatcher::finished, this,
            [this, id, request](QDBusPendingCallWatcher *done) {
        const QDBusPendingReply<QVariantMap> reply = *done;
        done->deleteLater();
        auto it = m_items.find(id);
        if (it == m_items.end() || it->request != request) return;
        it->refreshPending = false;
        if (it->refreshQueued) {
            it->refreshQueued = false;
            scheduleRefresh(id);
        }
        if (reply.isError()) return;
        const auto properties = reply.value();
        const QString title = plain(properties, QStringLiteral("Title"), 128);
        QString icon = plain(properties, QStringLiteral("IconName"), 128);
        if (!IconPattern.match(icon).hasMatch()) icon.clear();
        const QString status = normalizedStatus(plain(properties, QStringLiteral("Status"), 32));
        const QString path = menuPath(properties);
        const bool itemIsMenu = unbox(properties.value(QStringLiteral("ItemIsMenu"))).toBool();
        const QString finalTitle = title.isEmpty() ? it->service.left(128) : title;
        if (it->title == finalTitle && it->iconName == icon &&
            it->status == status && it->menuPath == path &&
            it->itemIsMenu == itemIsMenu) return;
        if (it->menuPath != path) {
            it->menu = {};
            it->menuLoading = false;
            it->menuFailed = false;
            it->visibleMenuIds.clear();
            it->submenuIds.clear();
        }
        it->title = finalTitle;
        it->iconName = icon;
        it->status = status;
        it->menuPath = path;
        it->itemIsMenu = itemIsMenu;
        emit changed();
    });
}

void TrayStore::scheduleRefresh(const QString &id) {
    if (!m_items.contains(id)) return;
    m_dirtyItems.insert(id);
    if (!m_refreshTimer.isActive()) m_refreshTimer.start();
}

void TrayStore::refreshSignal(const QDBusMessage &message) {
    for (const auto &id : m_order) {
        const auto &item = m_items[id];
        if (item.owner == message.service() && item.path == message.path() &&
            item.interface == message.interface()) scheduleRefresh(id);
    }
}

void TrayStore::itemSignal(const QDBusMessage &message) { refreshSignal(message); }
void TrayStore::statusSignal(const QString &, const QDBusMessage &message) {
    refreshSignal(message);
}

QString TrayStore::snapshot() const {
    QJsonArray entries;
    for (const auto &id : m_order) {
        const auto &item = m_items[id];
        if (item.status == QStringLiteral("Passive")) continue;
        entries.append(QJsonObject{{QStringLiteral("id"), id},
            {QStringLiteral("title"), item.title},
            {QStringLiteral("iconName"), item.iconName},
            {QStringLiteral("status"), item.status},
            {QStringLiteral("hasMenu"), !item.menuPath.isEmpty()},
            {QStringLiteral("itemIsMenu"), item.itemIsMenu},
            {QStringLiteral("menuLoading"), item.menuLoading},
            {QStringLiteral("menuFailed"), item.menuFailed},
            {QStringLiteral("menuParent"), item.menuParent},
            {QStringLiteral("menu"), item.menu}});
    }
    return QString::fromUtf8(QJsonDocument(QJsonObject{
        {QStringLiteral("version"), 1}, {QStringLiteral("items"), entries}})
        .toJson(QJsonDocument::Compact));
}

bool TrayStore::activate(const QString &id, int x, int y, bool context) {
    const auto it = m_items.constFind(id);
    if (it == m_items.cend() || it->status == QStringLiteral("Passive")) return false;
    auto message = QDBusMessage::createMethodCall(it->owner, it->path,
        it->interface, context ? QStringLiteral("ContextMenu") :
                                 QStringLiteral("Activate"));
    message.setArguments({x, y});
    QDBusConnection::sessionBus().asyncCall(message, 1000);
    return true;
}

bool TrayStore::requestMenu(const QString &id, int parentId) {
    auto it = m_items.find(id);
    if (it == m_items.end() || it->menuPath.isEmpty() ||
        (parentId != 0 && !it->submenuIds.contains(parentId))) return false;
    const quint64 request = it->menuRequest = ++m_nextMenuRequest;
    it->menu = {};
    it->menuParent = parentId;
    it->menuLoading = true;
    it->menuFailed = false;
    it->visibleMenuIds.clear();
    it->submenuIds.clear();
    emit changed();
    const QString service = it->owner;
    const QString path = it->menuPath;
    auto about = QDBusMessage::createMethodCall(service, path,
        QStringLiteral("com.canonical.dbusmenu"), QStringLiteral("AboutToShow"));
    about.setArguments({parentId});
    auto *pending = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(about, 1000), this);
    connect(pending, &QDBusPendingCallWatcher::finished, this,
            [this, id, parentId, request, service, path](QDBusPendingCallWatcher *done) {
        const QDBusMessage aboutReply = done->reply();
        done->deleteLater();
        const auto item = m_items.constFind(id);
        if (item == m_items.cend() || item->menuRequest != request ||
            item->owner != service || item->menuPath != path) return;
        if (aboutReply.type() != QDBusMessage::ReplyMessage) {
            auto current = m_items.find(id);
            current->menuLoading = false;
            current->menuFailed = true;
            emit changed();
            return;
        }
        auto layout = QDBusMessage::createMethodCall(service, path,
            QStringLiteral("com.canonical.dbusmenu"), QStringLiteral("GetLayout"));
        layout.setArguments({parentId, 1, QStringList{}});
        auto *layoutPending = new QDBusPendingCallWatcher(
            QDBusConnection::sessionBus().asyncCall(layout, 1000), this);
        connect(layoutPending, &QDBusPendingCallWatcher::finished, this,
                [this, id, parentId, request](QDBusPendingCallWatcher *finished) {
            const QDBusMessage reply = finished->reply();
            finished->deleteLater();
            auto item = m_items.find(id);
            if (item == m_items.end() || item->menuRequest != request) return;
            QJsonArray entries;
            QSet<int> ids, submenus;
            if (!parseMenuLayout(reply, parentId, &entries, &ids, &submenus)) {
                item->menuLoading = false;
                item->menuFailed = true;
                emit changed();
                return;
            }
            item->menu = entries;
            item->menuLoading = false;
            item->menuFailed = false;
            item->menuParent = parentId;
            item->visibleMenuIds = ids;
            item->submenuIds = submenus;
            emit changed();
        });
    });
    return true;
}

bool TrayStore::selectMenu(const QString &id, int menuId) {
    const auto it = m_items.constFind(id);
    if (it == m_items.cend() || it->menuPath.isEmpty() ||
        !it->visibleMenuIds.contains(menuId) || it->submenuIds.contains(menuId)) return false;
    bool allowed = false;
    for (const auto &value : it->menu) {
        const auto entry = value.toObject();
        if (entry.value(QStringLiteral("id")).toInt() == menuId &&
            entry.value(QStringLiteral("enabled")).toBool() &&
            !entry.value(QStringLiteral("separator")).toBool()) {
            allowed = true; break;
        }
    }
    if (!allowed) return false;
    auto event = QDBusMessage::createMethodCall(it->owner, it->menuPath,
        QStringLiteral("com.canonical.dbusmenu"), QStringLiteral("Event"));
    event.setArguments({menuId, QStringLiteral("clicked"),
                        QVariant::fromValue(QDBusVariant(QVariant(0))), quint32(0)});
    QDBusConnection::sessionBus().asyncCall(event, 1000);
    return true;
}
