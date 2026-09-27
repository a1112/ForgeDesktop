#include "notifications.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QDBusConnection>
#include <QDBusContext>
#include <QTest>

class NotificationServiceFixture final : public QObject, public QDBusContext {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.forge.DesktopNotifications1")
public:
    bool authorized = false;
    int denied = 0;
public slots:
    QString Snapshot() {
        if (!authorized) {
            ++denied;
            sendErrorReply(QStringLiteral("org.freedesktop.DBus.Error.AccessDenied"),
                           QStringLiteral("shell has not registered yet"));
            return {};
        }
        return QStringLiteral(R"({"version":1,"notifications":[{"id":1,"app":"Mail","summary":"Existing","body":"still here","actions":[]}]})");
    }
};

class NotificationsTest : public QObject {
    Q_OBJECT
private slots:
    void parsesBoundedPlainText() {
        QVariantList entries;
        QVERIFY(Notifications::parseSnapshot(
            R"({"version":1,"notifications":[{"id":1,"app":"Mail","summary":"<b>Inbox</b>","body":"你好","actions":["open","Open"]}]})",
            &entries));
        QCOMPARE(entries.size(), 1);
        const QVariantMap item = entries.first().toMap();
        QCOMPARE(item.value("summary").toString(), QStringLiteral("<b>Inbox</b>"));
        QCOMPARE(item.value("body").toString(), QStringLiteral("你好"));
        QCOMPARE(item.value("actionKeys").toList().first().toString(), QStringLiteral("open"));
    }
    void rejectsInvalidSnapshots() {
        QVariantList entries;
        QVERIFY(!Notifications::parseSnapshot("not-json", &entries));
        QVERIFY(!Notifications::parseSnapshot(R"({"version":2,"notifications":[]})", &entries));
        QVERIFY(!Notifications::parseSnapshot(R"({"version":1,"notifications":[{"id":0,"app":"x","summary":"s","body":"b","actions":[]}]})", &entries));
        QVERIFY(!Notifications::parseSnapshot(R"({"version":1,"notifications":[{"id":1,"app":"x","summary":"s","body":"b","actions":["open"]}]})", &entries));
    }
    void acceptsFullStoreWithEscapedBodies() {
        QJsonArray items;
        for (int id = 1; id <= 64; ++id) {
            items.append(QJsonObject{{"id", id}, {"app", "Sample"},
                {"summary", "Notice"}, {"body", QString(16384, QChar(1))},
                {"actions", QJsonArray{}}});
        }
        const QString snapshot = QString::fromUtf8(QJsonDocument(
            QJsonObject{{"version", 1}, {"notifications", items}})
            .toJson(QJsonDocument::Compact));
        QVERIFY(snapshot.toUtf8().size() > 2 * 1024 * 1024);
        QVariantList entries;
        QVERIFY(Notifications::parseSnapshot(snapshot, &entries));
        QCOMPARE(entries.size(), 64);
    }
    void initialDenialRecoversWithoutChangedSignal() {
        QDBusConnection bus = QDBusConnection::sessionBus();
        QVERIFY(bus.isConnected());
        NotificationServiceFixture service;
        QVERIFY(bus.registerObject(QStringLiteral("/org/freedesktop/Notifications"),
                                   &service, QDBusConnection::ExportAllSlots));
        QVERIFY(bus.registerService(QStringLiteral("org.freedesktop.Notifications")));
        Notifications client;
        QTRY_VERIFY_WITH_TIMEOUT(service.denied > 0, 1000);
        QVERIFY(!client.online());
        service.authorized = true;
        QTRY_VERIFY_WITH_TIMEOUT(client.online(), 3000);
        QCOMPARE(client.entries().size(), 1);
        QCOMPARE(client.entries().first().toMap().value("body").toString(),
                 QStringLiteral("still here"));
        bus.unregisterService(QStringLiteral("org.freedesktop.Notifications"));
        bus.unregisterObject(QStringLiteral("/org/freedesktop/Notifications"));
    }
};

QTEST_GUILESS_MAIN(NotificationsTest)
#include "notifications_test.moc"
