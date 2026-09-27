#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QThread>

#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>

class Signals final : public QObject {
    Q_OBJECT
public:
    quint32 actionId = 0;
    QString actionKey;
    quint32 closedId = 0;
    quint32 closedReason = 0;
public slots:
    void onAction(uint id, const QString &key) { actionId = id; actionKey = key; }
    void onClosed(uint id, uint reason) { closedId = id; closedReason = reason; }
};

namespace {
constexpr auto Service = "org.freedesktop.Notifications";
constexpr auto Path = "/org/freedesktop/Notifications";

void require(bool condition, const char *reason) {
    if (!condition) {
        std::fprintf(stderr, "notification D-Bus test: %s\n", reason);
        std::exit(1);
    }
}
QDBusMessage call(const QDBusConnection &bus, const QString &iface,
                  const QString &method, const QVariantList &arguments = {}) {
    auto message = QDBusMessage::createMethodCall(
        QString::fromLatin1(Service), QString::fromLatin1(Path), iface, method);
    message.setArguments(arguments);
    return bus.call(message, QDBus::Block, 3000);
}
QDBusMessage notify(const QDBusConnection &bus, quint32 replacesId = 0) {
    return call(bus, QString::fromLatin1(Service), QStringLiteral("Notify"),
        {QStringLiteral("Sample"), replacesId, QString(), QStringLiteral("你好"),
         QStringLiteral("private body"), QStringList{QStringLiteral("open"),
             QStringLiteral("Open")}, QVariantMap{}, 0});
}
bool denied(const QDBusMessage &message) {
    return message.type() == QDBusMessage::ErrorMessage &&
           message.errorName() == QStringLiteral("org.freedesktop.DBus.Error.AccessDenied");
}
}

int main(int argc, char **argv) {
    require(argc == 2, "daemon path required");
    int ends[2];
    require(socketpair(AF_UNIX, SOCK_STREAM, 0, ends) == 0, "socketpair");
    const pid_t pid = fork();
    require(pid >= 0, "fork");
    if (pid == 0) {
        close(ends[0]);
        if (dup2(ends[1], STDIN_FILENO) < 0) _exit(127);
        close(ends[1]);
        execl(argv[1], argv[1], static_cast<char *>(nullptr));
        _exit(127);
    }
    close(ends[1]);
    QCoreApplication app(argc, argv);
    auto shell = QDBusConnection::sessionBus();
    const auto other = QDBusConnection::connectToBus(QDBusConnection::SessionBus,
                                                     QStringLiteral("other-client"));
    require(shell.isConnected() && other.isConnected() &&
            shell.baseService() != other.baseService(), "distinct session bus senders");
    bool ready = false;
    for (int i = 0; i < 40; ++i) {
        auto info = call(shell, QString::fromLatin1(Service),
                         QStringLiteral("GetServerInformation"));
        if (info.type() == QDBusMessage::ReplyMessage) { ready = true; break; }
        QThread::msleep(50);
    }
    require(ready, "daemon owns standard notification name");

    const auto item = notify(shell);
    require(item.type() == QDBusMessage::ReplyMessage &&
            item.arguments().size() == 1 && item.arguments()[0].toUInt() > 0,
            "standard Notify remains public");
    const quint32 id = item.arguments()[0].toUInt();
    Signals observed;
    require(shell.connect(QString::fromLatin1(Service), QString::fromLatin1(Path),
                          QString::fromLatin1(Service), QStringLiteral("ActionInvoked"),
                          &observed, SLOT(onAction(uint,QString))) &&
            shell.connect(QString::fromLatin1(Service), QString::fromLatin1(Path),
                          QString::fromLatin1(Service), QStringLiteral("NotificationClosed"),
                          &observed, SLOT(onClosed(uint,uint))), "subscribe to standard signals");
    const QString view = QStringLiteral("org.forge.DesktopNotifications1");
    require(denied(call(shell, view, QStringLiteral("Snapshot"))),
            "unregistered sender cannot read snapshot");
    require(denied(call(other, view, QStringLiteral("Dismiss"), {id})),
            "other sender cannot dismiss");
    require(denied(call(other, view, QStringLiteral("Invoke"),
                        {id, QStringLiteral("open")})),
            "other sender cannot invoke an action");

    const QByteArray authorize = "1\tauthorize\t" + shell.baseService().toLatin1() + '\n';
    require(send(ends[0], authorize.constData(), authorize.size(), MSG_NOSIGNAL) ==
            authorize.size(), "send private shell authorization");
    bool authorized = false;
    for (int i = 0; i < 40; ++i) {
        auto result = call(shell, view, QStringLiteral("Snapshot"));
        if (result.type() == QDBusMessage::ReplyMessage &&
            result.arguments().value(0).toString().contains(QStringLiteral("private body"))) {
            authorized = true; break;
        }
        QThread::msleep(25);
    }
    require(authorized, "live shell can read snapshot");
    require(denied(call(other, view, QStringLiteral("Snapshot"))),
            "other sender cannot read body after authorization");
    require(denied(call(other, QString::fromLatin1(Service),
                        QStringLiteral("CloseNotification"), {id})),
            "other producer cannot close an owned notice");
    require(denied(notify(other, id)), "other producer cannot replace an owned notice");
    require(call(shell, view, QStringLiteral("Invoke"),
                 {id, QStringLiteral("open")}).arguments().value(0).toBool(),
            "live shell can invoke an action");
    for (int i = 0; i < 40 && observed.actionId != id; ++i) {
        QCoreApplication::processEvents(); QThread::msleep(5);
    }
    require(observed.actionId == id && observed.actionKey == QStringLiteral("open"),
            "action signal reports the selected key");

    constexpr char revoke[] = "1\trevoke\n";
    require(send(ends[0], revoke, sizeof(revoke) - 1, MSG_NOSIGNAL) == sizeof(revoke) - 1,
            "send revocation");
    bool revoked = false;
    for (int i = 0; i < 40; ++i) {
        if (denied(call(shell, view, QStringLiteral("Snapshot")))) { revoked = true; break; }
        QThread::msleep(25);
    }
    require(revoked, "old shell sender revoked");
    require(send(ends[0], authorize.constData(), authorize.size(), MSG_NOSIGNAL) ==
            authorize.size(), "reauthorize current shell");
    bool dismissed = false;
    for (int i = 0; i < 40; ++i) {
        auto result = call(shell, view, QStringLiteral("Dismiss"), {id});
        if (result.type() == QDBusMessage::ReplyMessage &&
            result.arguments().value(0).toBool()) { dismissed = true; break; }
        QThread::msleep(25);
    }
    require(dismissed, "live shell can dismiss");
    for (int i = 0; i < 40 && observed.closedId != id; ++i) {
        QCoreApplication::processEvents(); QThread::msleep(5);
    }
    require(observed.closedId == id && observed.closedReason == 2,
            "dismissal emits user-dismissed reason");
    const auto clientItem = notify(shell);
    require(clientItem.type() == QDBusMessage::ReplyMessage, "second notice created");
    const quint32 clientId = clientItem.arguments()[0].toUInt();
    require(call(shell, QString::fromLatin1(Service),
                 QStringLiteral("CloseNotification"), {clientId}).type() ==
                 QDBusMessage::ReplyMessage, "owner can close its notice");
    for (int i = 0; i < 40 && observed.closedId != clientId; ++i) {
        QCoreApplication::processEvents(); QThread::msleep(5);
    }
    require(observed.closedId == clientId && observed.closedReason == 3,
            "client close emits reason 3");
    close(ends[0]);
    int status = 0;
    require(waitpid(pid, &status, 0) == pid && WIFEXITED(status) && WEXITSTATUS(status) == 3,
            "daemon exits on private channel loss");
    QDBusConnection::disconnectFromBus(QStringLiteral("other-client"));
    return 0;
}

#include "dbus_test.moc"
