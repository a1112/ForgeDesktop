#include "store.h"
#include "authority.h"

#include <QCoreApplication>
#include <QDBusAbstractAdaptor>
#include <QDBusConnection>
#include <QDBusContext>
#include <QDBusError>
#include <QDBusMessage>
#include <QDebug>
#include <QSocketNotifier>
#include <cerrno>
#include <fcntl.h>
#include <sys/socket.h>
#include <unistd.h>

class NotificationObject final : public QObject, public QDBusContext {
    Q_OBJECT
public:
    explicit NotificationObject(NotificationStore *store, ShellAuthority *authority)
        : m_store(store), m_authority(authority) {}
    NotificationStore *store() const { return m_store; }
    bool authorizeView() {
        if (calledFromDBus() && m_authority->allowed(message().service())) return true;
        if (calledFromDBus())
            sendErrorReply(QStringLiteral("org.freedesktop.DBus.Error.AccessDenied"),
                           QStringLiteral("notification center requires the live desktop shell"));
        return false;
    }
private:
    NotificationStore *m_store;
    ShellAuthority *m_authority;
};

class FreedesktopAdaptor final : public QDBusAbstractAdaptor {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.freedesktop.Notifications")
public:
    explicit FreedesktopAdaptor(NotificationObject *object)
        : QDBusAbstractAdaptor(object), m_object(object) {
        connect(object->store(), &NotificationStore::closed, this,
                &FreedesktopAdaptor::NotificationClosed);
        connect(object->store(), &NotificationStore::actionInvoked, this,
                &FreedesktopAdaptor::ActionInvoked);
    }
public slots:
    QStringList GetCapabilities() const {
        return {QStringLiteral("body"), QStringLiteral("actions")};
    }
    void GetServerInformation(QString &name, QString &vendor, QString &version,
                              QString &specVersion) const {
        name = QStringLiteral("ForgeDesktop");
        vendor = QStringLiteral("ForgeOS");
        version = QStringLiteral("0.1.0");
        specVersion = QStringLiteral("1.3");
    }
    quint32 Notify(const QString &appName, quint32 replacesId,
                   const QString &appIcon, const QString &summary, const QString &body,
                   const QStringList &actions, const QVariantMap &hints, int expireTimeout) {
        if (!m_object->calledFromDBus()) return 0;
        if (hints.size() > 32) {
            m_object->sendErrorReply(QDBusError::InvalidArgs, QStringLiteral("too many hints"));
            return 0;
        }
        const auto result = m_object->store()->add(m_object->message().service(), appName, replacesId,
                                         appIcon, summary, body, actions, expireTimeout);
        if (result.result == NotificationStore::Result::WrongSender)
            m_object->sendErrorReply(QStringLiteral("org.freedesktop.DBus.Error.AccessDenied"),
                           QStringLiteral("notification belongs to another sender"));
        else if (result.result != NotificationStore::Result::Ok)
            m_object->sendErrorReply(QDBusError::InvalidArgs, QStringLiteral("invalid notification"));
        return result.id;
    }
    void CloseNotification(quint32 id) {
        if (!m_object->calledFromDBus()) return;
        const auto result = m_object->store()->close(id, NotificationStore::ClientClosed,
                                           m_object->message().service());
        if (result == NotificationStore::Result::WrongSender)
            m_object->sendErrorReply(QStringLiteral("org.freedesktop.DBus.Error.AccessDenied"),
                           QStringLiteral("notification belongs to another sender"));
        else if (result != NotificationStore::Result::Ok)
            m_object->sendErrorReply(QDBusError::InvalidArgs, QStringLiteral("unknown notification"));
    }
signals:
    void NotificationClosed(quint32 id, quint32 reason);
    void ActionInvoked(quint32 id, const QString &action);
private:
    NotificationObject *m_object;
};

class ViewAdaptor final : public QDBusAbstractAdaptor {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.forge.DesktopNotifications1")
public:
    explicit ViewAdaptor(NotificationObject *object)
        : QDBusAbstractAdaptor(object), m_object(object), m_store(object->store()) {
        connect(m_store, &NotificationStore::changed, this, &ViewAdaptor::Changed);
    }
public slots:
    QString Snapshot() {
        return m_object->authorizeView() ? m_store->snapshot() : QString();
    }
    bool Dismiss(quint32 id) {
        if (!m_object->authorizeView()) return false;
        return m_store->close(id, NotificationStore::Dismissed) ==
               NotificationStore::Result::Ok;
    }
    bool Invoke(quint32 id, const QString &action) {
        if (!m_object->authorizeView()) return false;
        return m_store->invoke(id, action) == NotificationStore::Result::Ok;
    }
signals:
    void Changed();
private:
    NotificationObject *m_object;
    NotificationStore *m_store;
};

int main(int argc, char **argv) {
    if (geteuid() == 0) return 1;
    int flags = fcntl(STDIN_FILENO, F_GETFD);
    if (flags < 0 || fcntl(STDIN_FILENO, F_SETFD, flags | FD_CLOEXEC) < 0) return 1;
    flags = fcntl(STDIN_FILENO, F_GETFL);
    if (flags < 0 || fcntl(STDIN_FILENO, F_SETFL, flags | O_NONBLOCK) < 0) return 1;
    int kind = 0;
    socklen_t length = sizeof(kind);
    if (getsockopt(STDIN_FILENO, SOL_SOCKET, SO_TYPE, &kind, &length) < 0 ||
        kind != SOCK_STREAM) return 1;
    QCoreApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("Forge Notifications"));
    NotificationStore store;
    ShellAuthority authority;
    NotificationObject object(&store, &authority);
    new FreedesktopAdaptor(&object);
    new ViewAdaptor(&object);
    QSocketNotifier reader(STDIN_FILENO, QSocketNotifier::Read);
    QObject::connect(&reader, &QSocketNotifier::activated, &app, [&] {
        char bytes[256];
        const ssize_t n = recv(STDIN_FILENO, bytes, sizeof(bytes), 0);
        if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) return;
        if (n <= 0 || !authority.feed(QByteArray(bytes, n))) app.exit(3);
    });
    QDBusConnection bus = QDBusConnection::sessionBus();
    if (!bus.isConnected() ||
        !bus.registerObject(QStringLiteral("/org/freedesktop/Notifications"), &object,
                            QDBusConnection::ExportAdaptors) ||
        !bus.registerService(QStringLiteral("org.freedesktop.Notifications"))) {
        qCritical() << "Forge notification service could not own session bus name:"
                    << bus.lastError().message();
        return 2;
    }
    return app.exec();
}

#include "main.moc"
