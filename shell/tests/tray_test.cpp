#include "tray.h"

#include <QDBusConnection>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTest>

class TrayViewFixture final : public QObject {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.forge.DesktopTray1")
public:
    QString title = QStringLiteral("输入法");
    int requests = 0;
    int selections = 0;
public slots:
    QString Snapshot() const {
        return QString::fromUtf8(QJsonDocument(QJsonObject{
            {"version", 1}, {"items", QJsonArray{QJsonObject{
                {"id", ":1.7/StatusNotifierItem"}, {"title", title},
                {"iconName", "input-keyboard"}, {"status", "Active"},
                {"hasMenu", true}, {"menuParent", 0},
                {"menu", QJsonArray{QJsonObject{{"id", 5}, {"label", "Settings"},
                    {"enabled", true}, {"separator", false},
                    {"submenu", false}, {"checked", false}}}}}}}})
            .toJson(QJsonDocument::Compact));
    }
    bool RequestMenu(const QString &, int) { ++requests; return true; }
    bool SelectMenu(const QString &, int) { ++selections; return true; }
};

class TrayTest : public QObject {
    Q_OBJECT
private slots:
    void parsesBoundedItems() {
        QVariantList items;
        QVERIFY(Tray::parseSnapshot(R"({"version":1,"items":[{"id":":1.7/StatusNotifierItem","title":"输入法","iconName":"input-keyboard","status":"Active"}]})", &items));
        QCOMPARE(items.size(), 1);
        QCOMPARE(items.first().toMap().value("title").toString(), QStringLiteral("输入法"));
        QVERIFY(Tray::parseSnapshot(R"({"version":1,"items":[{"id":":1.7/StatusNotifierItem","title":"输入法","iconName":"input-keyboard","status":"Active","hasMenu":true,"itemIsMenu":true,"menuParent":0,"menu":[{"id":5,"label":"Settings","enabled":true,"separator":false,"submenu":false,"checked":false}]}]})", &items));
        QCOMPARE(items.first().toMap().value("menu").toList().size(), 1);
        QVERIFY(items.first().toMap().value("itemIsMenu").toBool());
        QVERIFY(!Tray::parseSnapshot(R"({"version":2,"items":[]})", &items));
        QVERIFY(Tray::parseSnapshot(R"({"version":1,"items":[{"id":"bad","title":"X","iconName":"x","status":"Active"}]})", &items));
        QVERIFY(items.isEmpty());
        QVERIFY(Tray::parseSnapshot(R"({"version":1,"items":[{"id":":1.7/StatusNotifierItem","title":"X","iconName":"../secret","status":"Active"}]})", &items));
        QVERIFY(items.isEmpty());
        QVERIFY(Tray::parseSnapshot(R"({"version":1,"items":[{"id":":1.7/StatusNotifierItem","title":"Good","iconName":"ok","status":"Active"},{"id":":1.8/StatusNotifierItem","title":"Bad","iconName":"ok","status":"Unknown"}]})", &items));
        QCOMPARE(items.size(), 1);
        QCOMPARE(items.first().toMap().value("title").toString(), QStringLiteral("Good"));
    }
    void reconstructsUpdatedServiceSnapshot() {
        auto bus = QDBusConnection::sessionBus();
        QVERIFY(bus.isConnected());
        TrayViewFixture fixture;
        QVERIFY(bus.registerObject(QStringLiteral("/StatusNotifierWatcher"), &fixture,
                                   QDBusConnection::ExportAllSlots));
        QVERIFY(bus.registerService(QStringLiteral("org.kde.StatusNotifierWatcher")));
        Tray client;
        QTRY_VERIFY_WITH_TIMEOUT(client.online(), 2000);
        QCOMPARE(client.entries().first().toMap().value("title").toString(),
                 QStringLiteral("输入法"));
        const QString id = client.entries().first().toMap().value("id").toString();
        client.requestMenu(id, 0);
        client.selectMenu(id, 5);
        QTRY_COMPARE_WITH_TIMEOUT(fixture.requests, 1, 1000);
        QTRY_COMPARE_WITH_TIMEOUT(fixture.selections, 1, 1000);
        client.selectMenu(id, 99);
        QTest::qWait(30);
        QCOMPARE(fixture.selections, 1);
        fixture.title = QStringLiteral("中文输入");
        client.refresh();
        QTRY_COMPARE_WITH_TIMEOUT(client.entries().first().toMap().value("title").toString(),
                                  QStringLiteral("中文输入"), 2000);
        bus.unregisterService(QStringLiteral("org.kde.StatusNotifierWatcher"));
        bus.unregisterObject(QStringLiteral("/StatusNotifierWatcher"));
    }
};

QTEST_GUILESS_MAIN(TrayTest)
#include "tray_test.moc"
