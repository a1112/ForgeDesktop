#include "store.h"
#include "authority.h"

#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>
#include <QTest>

class StoreTest : public QObject {
    Q_OBJECT
private slots:
    void replacementAndOwnership() {
        NotificationStore store;
        QSignalSpy closed(&store, &NotificationStore::closed);
        const auto first = store.add(":1.10", "Mail", 0, "mail", "Inbox", "one", {}, 0);
        QCOMPARE(first.result, NotificationStore::Result::Ok);
        QVERIFY(first.id > 0);
        QCOMPARE(store.add(":1.11", "Other", first.id, "", "x", "", {}, 0).result,
                 NotificationStore::Result::WrongSender);
        const auto replacement = store.add(":1.10", "Mail", first.id, "mail",
                                           "Inbox", "two", {}, 0);
        QCOMPARE(replacement.id, first.id);
        QCOMPARE(store.size(), 1);
        QCOMPARE(store.close(first.id, NotificationStore::ClientClosed, ":1.11"),
                 NotificationStore::Result::WrongSender);
        QCOMPARE(store.close(first.id, NotificationStore::ClientClosed, ":1.10"),
                 NotificationStore::Result::Ok);
        QCOMPARE(closed.size(), 1);
        QCOMPARE(closed.takeFirst().at(1).toUInt(), 3u);
    }
    void unknownReplacementKeepsRequestedId() {
        NotificationStore store;
        const auto replacement = store.add(":1.10", "Mail", 900, "", "New", "", {}, 0);
        QCOMPARE(replacement.result, NotificationStore::Result::Ok);
        QCOMPARE(replacement.id, 900u);
        const auto fresh = store.add(":1.10", "Mail", 0, "", "Other", "", {}, 0);
        QCOMPARE(fresh.id, 1u);
        QCOMPARE(store.size(), 2);
    }
    void boundsAndEviction() {
        NotificationStore store;
        QSignalSpy closed(&store, &NotificationStore::closed);
        QCOMPARE(store.add(":1.1", "a", 0, "", QString(1025, 'x'), "", {}, 0).result,
                 NotificationStore::Result::Invalid);
        quint32 oldest = 0;
        for (int i = 0; i < 65; ++i) {
            const auto result = store.add(":1.1", "a", 0, "", QString::number(i), "", {}, 0);
            QCOMPARE(result.result, NotificationStore::Result::Ok);
            if (i == 0) oldest = result.id;
        }
        QCOMPARE(store.size(), 64);
        QCOMPARE(store.close(oldest, NotificationStore::Dismissed),
                 NotificationStore::Result::Unknown);
        QCOMPARE(closed.size(), 1);
        QCOMPARE(closed.takeFirst().at(1).toUInt(), 4u);
        const auto snapshot = QJsonDocument::fromJson(store.snapshot().toUtf8()).object();
        QCOMPARE(snapshot.value("version").toInt(), 1);
        QCOMPARE(snapshot.value("notifications").toArray().size(), 64);
    }
    void maximumEscapedSnapshotFitsShellBudget() {
        NotificationStore store;
        const QString escaped(16384, QChar(1));
        const QStringList actions(16, QString(256, QChar(1)));
        for (int i = 0; i < 64; ++i) {
            const auto result = store.add(":1.1", QString(128, QChar(1)), 0,
                QString(256, QChar(1)), QString(1024, QChar(1)), escaped,
                actions, 0);
            QCOMPARE(result.result, NotificationStore::Result::Ok);
        }
        QCOMPARE(store.size(), 64);
        const QByteArray bytes = store.snapshot().toUtf8();
        QVERIFY(bytes.size() > 2 * 1024 * 1024);
        QVERIFY(bytes.size() < 10 * 1024 * 1024);
    }
    void expiresAndInvokes() {
        NotificationStore store;
        QSignalSpy closed(&store, &NotificationStore::closed);
        QSignalSpy action(&store, &NotificationStore::actionInvoked);
        const auto item = store.add(":1.2", "a", 0, "", "s", "b",
                                    {"open", "Open"}, 25);
        QCOMPARE(store.invoke(item.id, "unknown"), NotificationStore::Result::Invalid);
        QCOMPARE(store.invoke(item.id, "open"), NotificationStore::Result::Ok);
        QCOMPARE(action.size(), 1);
        QTRY_COMPARE_WITH_TIMEOUT(closed.size(), 1, 1000);
        QCOMPARE(closed.takeFirst().at(1).toUInt(), 1u);
        QCOMPARE(store.size(), 0);
    }
    void privateShellAuthorityRequiresLiveUniqueSender() {
        ShellAuthority authority;
        QVERIFY(!authority.allowed(QStringLiteral(":1.42")));
        QVERIFY(authority.feed("1\tauthorize\t:1.42\n"));
        QVERIFY(authority.allowed(QStringLiteral(":1.42")));
        QVERIFY(!authority.allowed(QStringLiteral(":1.43")));
        QVERIFY(authority.feed("1\trevoke\n"));
        QVERIFY(!authority.allowed(QStringLiteral(":1.42")));
    }
    void privateShellAuthorityRejectsMalformedOrUnboundedFrames() {
        ShellAuthority authority;
        QVERIFY(authority.feed("1\tauthor"));
        QVERIFY(!authority.allowed(QStringLiteral(":1.42")));
        QVERIFY(authority.feed("ize\t:1.42\n"));
        QVERIFY(authority.allowed(QStringLiteral(":1.42")));
        for (const QByteArray &bad : {QByteArray("1\tauthorize\torg.fake\n"),
                                      QByteArray("1\tauthorize\t:1.1;rm\n"),
                                      QByteArray(256, 'x')}) {
            ShellAuthority other;
            QVERIFY(!other.feed(bad));
            QVERIFY(!other.allowed(QStringLiteral(":1.42")));
        }
    }
};

QTEST_MAIN(StoreTest)
#include "store_test.moc"
