#include <QCoreApplication>
#include <QDBusAbstractAdaptor>
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusObjectPath>
#include <QDBusVariant>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QThread>

#include <cstdio>
#include <cstdlib>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>

struct MenuLayout {
    int id = 0;
    QVariantMap properties;
    QList<QDBusVariant> children;
};
Q_DECLARE_METATYPE(MenuLayout)
QDBusArgument &operator<<(QDBusArgument &argument, const MenuLayout &layout) {
    argument.beginStructure();
    argument << layout.id << layout.properties << layout.children;
    argument.endStructure();
    return argument;
}
const QDBusArgument &operator>>(const QDBusArgument &argument, MenuLayout &layout) {
    argument.beginStructure();
    argument >> layout.id >> layout.properties >> layout.children;
    argument.endStructure();
    return argument;
}

class FakeMenu final : public QObject {
    Q_OBJECT
public:
    int clicks = 0;
    int shows = 0;
    bool tooManyHidden = false;
};
class FakeMenuAdaptor final : public QDBusAbstractAdaptor {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "com.canonical.dbusmenu")
public:
    explicit FakeMenuAdaptor(FakeMenu *menu) : QDBusAbstractAdaptor(menu), m_menu(menu) {}
public slots:
    bool AboutToShow(int) { ++m_menu->shows; return false; }
    void GetLayout(int parent, int, const QStringList &, quint32 &revision,
                   MenuLayout &layout) {
        revision = 1;
        layout.id = parent;
        for (int i = 0; i < (m_menu->tooManyHidden ? 65 : 1); ++i) {
            MenuLayout child;
            child.id = 5 + i;
            child.properties.insert(QStringLiteral("label"), QStringLiteral("Switch input"));
            child.properties.insert(QStringLiteral("enabled"), true);
            if (m_menu->tooManyHidden)
                child.properties.insert(QStringLiteral("visible"), false);
            layout.children.append(QDBusVariant(QVariant::fromValue(child)));
        }
    }
    void Event(int id, const QString &event, const QDBusVariant &, quint32) {
        if (id == 5 && event == QStringLiteral("clicked")) ++m_menu->clicks;
    }
private:
    FakeMenu *m_menu;
};

class FakeItem final : public QObject {
    Q_OBJECT
public:
    int activations = 0;
    int menus = 0;
    int propertyReads = 0;
    QString status = QStringLiteral("Active");
};

class FakeItemAdaptor final : public QDBusAbstractAdaptor {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.kde.StatusNotifierItem")
    Q_PROPERTY(QString Title READ Title)
    Q_PROPERTY(QString IconName READ IconName)
    Q_PROPERTY(QString Status READ Status)
    Q_PROPERTY(QDBusObjectPath Menu READ Menu)
    Q_PROPERTY(bool ItemIsMenu READ ItemIsMenu)
public:
    explicit FakeItemAdaptor(FakeItem *item) : QDBusAbstractAdaptor(item), m_item(item) {}
    QString Title() const { ++m_item->propertyReads; return QStringLiteral("输入法"); }
    QString IconName() const { return QStringLiteral("input-keyboard"); }
    QString Status() const { return m_item->status; }
    QDBusObjectPath Menu() const { return QDBusObjectPath(QStringLiteral("/UnimplementedMenu")); }
    bool ItemIsMenu() const { return true; }
public slots:
    void Activate(int, int) { ++m_item->activations; }
    void ContextMenu(int, int) { ++m_item->menus; }
signals:
    void NewStatus(const QString &status);
private:
    FakeItem *m_item;
};

namespace {
void require(bool ok, const char *reason) {
    if (!ok) { std::fprintf(stderr, "tray D-Bus test: %s\n", reason); std::exit(1); }
}
QDBusMessage call(const QDBusConnection &connection, const QString &service,
                  const QString &iface, const QString &method,
                  const QVariantList &args = {}) {
    auto message = QDBusMessage::createMethodCall(service,
        QStringLiteral("/StatusNotifierWatcher"), iface, method);
    message.setArguments(args);
    return connection.call(message, QDBus::Block, 3000);
}
bool denied(const QDBusMessage &message) {
    return message.type() == QDBusMessage::ErrorMessage &&
        message.errorName() == QStringLiteral("org.freedesktop.DBus.Error.AccessDenied");
}
}

int main(int argc, char **argv) {
    require(argc == 2, "daemon path required");
    qDBusRegisterMetaType<MenuLayout>();
    qDBusRegisterMetaType<QList<QDBusVariant>>();
    int ends[2];
    require(socketpair(AF_UNIX, SOCK_STREAM, 0, ends) == 0, "socketpair");
    const pid_t pid = fork();
    require(pid >= 0, "fork");
    if (pid == 0) {
        close(ends[0]);
        require(dup2(ends[1], STDIN_FILENO) >= 0, "dup stdin");
        close(ends[1]);
        execl(argv[1], argv[1], static_cast<char *>(nullptr));
        _exit(127);
    }
    close(ends[1]);
    QCoreApplication app(argc, argv);
    const auto shell = QDBusConnection::sessionBus();
    auto itemBus = QDBusConnection::connectToBus(
        QDBusConnection::SessionBus, QStringLiteral("tray-item"));
    require(shell.isConnected() && itemBus.isConnected() &&
            shell.baseService() != itemBus.baseService(), "distinct bus senders");
    const QString watcher = QStringLiteral("org.kde.StatusNotifierWatcher");
    const QString watcherIface = watcher;
    const QString view = QStringLiteral("org.forge.DesktopTray1");
    bool ready = false;
    for (int i = 0; i < 40; ++i) {
        auto result = call(shell, watcher, watcherIface,
                           QStringLiteral("RegisterStatusNotifierHost"),
                           {shell.baseService()});
        if (result.type() == QDBusMessage::ReplyMessage) { ready = true; break; }
        QThread::msleep(50);
    }
    require(ready, "watcher accepts host registration");
    FakeItem item;
    auto *itemAdaptor = new FakeItemAdaptor(&item);
    require(itemBus.registerObject(QStringLiteral("/StatusNotifierItem"), &item,
            QDBusConnection::ExportAdaptors), "fake item registered");
    require(denied(call(shell, watcher, watcherIface,
            QStringLiteral("RegisterStatusNotifierItem"), {itemBus.baseService()})),
            "another client cannot register someone else's item");
    require(call(itemBus, watcher, watcherIface,
            QStringLiteral("RegisterStatusNotifierItem"),
            {QStringLiteral("/StatusNotifierItem")}).type() ==
            QDBusMessage::ReplyMessage, "item registers its own path");
    require(denied(call(shell, watcher, view, QStringLiteral("Snapshot"))),
            "unregistered shell cannot enumerate tray items");
    const QByteArray authorize = "1\tauthorize\t" + shell.baseService().toLatin1() + '\n';
    require(send(ends[0], authorize.constData(), authorize.size(), MSG_NOSIGNAL) ==
            authorize.size(), "authorize current shell");
    QString id;
    for (int i = 0; i < 80; ++i) {
        QCoreApplication::processEvents();
        auto result = call(shell, watcher, view, QStringLiteral("Snapshot"));
        if (result.type() == QDBusMessage::ReplyMessage) {
            const auto root = QJsonDocument::fromJson(
                result.arguments().value(0).toString().toUtf8()).object();
            const auto entries = root.value(QStringLiteral("items")).toArray();
            if (!entries.isEmpty() &&
                entries.first().toObject().value(QStringLiteral("title")).toString() ==
                    QStringLiteral("输入法")) {
                id = entries.first().toObject().value(QStringLiteral("id")).toString();
                require(entries.first().toObject().value(QStringLiteral("iconName"))
                    .toString() == QStringLiteral("input-keyboard"), "icon name reflected");
                break;
            }
        }
        QThread::msleep(25);
    }
    require(!id.isEmpty(), "authorized shell sees live item metadata");
    const int readsBeforeFlood = item.propertyReads;
    item.status = QStringLiteral("Unexpected");
    for (int i = 0; i < 200; ++i)
        emit itemAdaptor->NewStatus(item.status);
    bool normalized = false;
    for (int i = 0; i < 80; ++i) {
        QCoreApplication::processEvents();
        const auto result = call(shell, watcher, view, QStringLiteral("Snapshot"));
        const auto entries = QJsonDocument::fromJson(
            result.arguments().value(0).toString().toUtf8()).object()
                                 .value(QStringLiteral("items")).toArray();
        if (!entries.isEmpty() && entries.first().toObject()
                .value(QStringLiteral("status")).toString() == QStringLiteral("Active") &&
            item.propertyReads > readsBeforeFlood) {
            normalized = true; break;
        }
        QThread::msleep(25);
    }
    require(normalized, "invalid item status normalizes without disappearing");
    QThread::msleep(300);
    QCoreApplication::processEvents();
    require(item.propertyReads - readsBeforeFlood <= 3,
            "signal flood coalesces GetAll requests per item");
    require(call(shell, watcher, view, QStringLiteral("RequestMenu"), {id, 0})
                .arguments().value(0).toBool(), "shell requests registered item menu");
    bool menuFailed = false;
    for (int i = 0; i < 80; ++i) {
        QCoreApplication::processEvents();
        const auto result = call(shell, watcher, view, QStringLiteral("Snapshot"));
        const auto entries = QJsonDocument::fromJson(
            result.arguments().value(0).toString().toUtf8()).object()
                                 .value(QStringLiteral("items")).toArray();
        if (!entries.isEmpty()) {
            const auto entry = entries.first().toObject();
            if (entry.value(QStringLiteral("menuFailed")).toBool() &&
                !entry.value(QStringLiteral("menuLoading")).toBool() &&
                entry.value(QStringLiteral("itemIsMenu")).toBool()) {
                menuFailed = true; break;
            }
        }
        QThread::msleep(25);
    }
    require(menuFailed, "menu failure is visible and menu-only item is identified");
    FakeMenu menu;
    new FakeMenuAdaptor(&menu);
    require(itemBus.registerObject(QStringLiteral("/UnimplementedMenu"), &menu,
            QDBusConnection::ExportAdaptors), "fake DBusMenu registered");
    require(call(shell, watcher, view, QStringLiteral("RequestMenu"), {id, 0})
                .arguments().value(0).toBool(), "shell reloads working menu");
    bool menuReady = false;
    for (int i = 0; i < 80; ++i) {
        QCoreApplication::processEvents();
        const auto result = call(shell, watcher, view, QStringLiteral("Snapshot"));
        const auto entries = QJsonDocument::fromJson(
            result.arguments().value(0).toString().toUtf8()).object()
                                 .value(QStringLiteral("items")).toArray();
        if (!entries.isEmpty()) {
            const auto entry = entries.first().toObject();
            const auto actions = entry.value(QStringLiteral("menu")).toArray();
            if (!entry.value(QStringLiteral("menuLoading")).toBool() &&
                !entry.value(QStringLiteral("menuFailed")).toBool() &&
                actions.size() == 1 && actions.first().toObject()
                    .value(QStringLiteral("label")).toString() ==
                    QStringLiteral("Switch input")) {
                menuReady = true; break;
            }
        }
        QThread::msleep(25);
    }
    require(menuReady && menu.shows == 1, "DBusMenu layout reaches private snapshot");
    require(call(shell, watcher, view, QStringLiteral("SelectMenu"), {id, 5})
                .arguments().value(0).toBool(), "shell selects visible menu action");
    for (int i = 0; i < 40 && !menu.clicks; ++i) {
        QCoreApplication::processEvents(); QThread::msleep(5);
    }
    require(menu.clicks == 1, "DBusMenu Event clicked delivered");
    menu.tooManyHidden = true;
    require(call(shell, watcher, view, QStringLiteral("RequestMenu"), {id, 0})
                .arguments().value(0).toBool(), "request oversized hidden menu");
    bool oversizedRejected = false;
    for (int i = 0; i < 80; ++i) {
        QCoreApplication::processEvents();
        const auto result = call(shell, watcher, view, QStringLiteral("Snapshot"));
        const auto entries = QJsonDocument::fromJson(
            result.arguments().value(0).toString().toUtf8()).object()
                                 .value(QStringLiteral("items")).toArray();
        if (!entries.isEmpty() && entries.first().toObject()
                .value(QStringLiteral("menuFailed")).toBool()) {
            oversizedRejected = true; break;
        }
        QThread::msleep(25);
    }
    require(oversizedRejected, "hidden children count toward menu bound");
    require(denied(call(itemBus, watcher, view, QStringLiteral("Activate"),
                        {id, 2, 3, false})), "item cannot invoke private action");
    require(denied(call(itemBus, watcher, view, QStringLiteral("RequestMenu"),
                        {id, 0})), "item cannot read another item's menu");
    require(denied(call(itemBus, watcher, view, QStringLiteral("SelectMenu"),
                        {id, 5})), "item cannot select a private menu action");
    require(call(shell, watcher, view, QStringLiteral("Activate"),
                 {id, 2, 3, false}).arguments().value(0).toBool(),
            "shell activates a registered item");
    for (int i = 0; i < 40 && !item.activations; ++i) {
        QCoreApplication::processEvents(); QThread::msleep(5);
    }
    require(item.activations == 1, "item receives Activate");
    constexpr char revoke[] = "1\trevoke\n";
    require(send(ends[0], revoke, sizeof(revoke)-1, MSG_NOSIGNAL) ==
            sizeof(revoke)-1, "revoke shell");
    bool revoked = false;
    for (int i = 0; i < 40; ++i) {
        if (denied(call(shell, watcher, view, QStringLiteral("Snapshot")))) {
            revoked = true; break;
        }
        QThread::msleep(25);
    }
    require(revoked, "old shell loses tray access");
    require(send(ends[0], authorize.constData(), authorize.size(), MSG_NOSIGNAL) ==
            authorize.size(), "authorize restarted shell");
    bool restored = false;
    for (int i = 0; i < 40; ++i) {
        const auto result = call(shell, watcher, view, QStringLiteral("Snapshot"));
        if (result.type() == QDBusMessage::ReplyMessage &&
            result.arguments().value(0).toString().contains(id)) {
            restored = true; break;
        }
        QThread::msleep(25);
    }
    require(restored, "registered item survives shell restart");
    const QString itemOwner = itemBus.baseService();
    itemBus = QDBusConnection::sessionBus();
    QDBusConnection::disconnectFromBus(QStringLiteral("tray-item"));
    bool busLeft = false;
    for (int i = 0; i < 80; ++i) {
        const auto registered = shell.interface()->isServiceRegistered(itemOwner);
        if (registered.isValid() && !registered.value()) { busLeft = true; break; }
        QThread::msleep(25);
    }
    require(busLeft, "test item connection has left session bus");
    bool removed = false;
    for (int i = 0; i < 80; ++i) {
        auto result = call(shell, watcher, view, QStringLiteral("Snapshot"));
        if (result.type() == QDBusMessage::ReplyMessage &&
            !result.arguments().value(0).toString().contains(id)) {
            removed = true; break;
        }
        QThread::msleep(25);
    }
    require(removed, "item removed when sender leaves bus");
    close(ends[0]);
    int status = 0;
    require(waitpid(pid, &status, 0) == pid && WIFEXITED(status) &&
            WEXITSTATUS(status) == 3, "daemon exits on private channel loss");
    return 0;
}

#include "tray_dbus_test.moc"
