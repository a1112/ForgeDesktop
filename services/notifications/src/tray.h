#pragma once

#include <QHash>
#include <QJsonArray>
#include <QObject>
#include <QSet>
#include <QStringList>
#include <QTimer>

class QDBusMessage;

// Stores only D-Bus identities and bounded display metadata. The compositor's
// private authorization channel gates all shell-facing read/action methods.
class TrayStore final : public QObject {
    Q_OBJECT
public:
    explicit TrayStore(QObject *parent = nullptr);
    bool registerItem(const QString &sender, const QString &spec,
                      const QString &interface, QString *error);
    bool registerHost(const QString &sender, const QString &spec, QString *error);
    QStringList registeredItems() const { return m_order; }
    bool hostRegistered() const { return !m_hosts.isEmpty(); }
    QString snapshot() const;
    bool activate(const QString &id, int x, int y, bool context);
    bool requestMenu(const QString &id, int parentId);
    bool selectMenu(const QString &id, int menuId);
signals:
    void changed();
    void itemRegistered(const QString &id);
    void itemUnregistered(const QString &id);
    void hostBecameRegistered();
    void hostBecameUnregistered();
private slots:
    void nameOwnerChanged(const QString &name, const QString &oldOwner,
                          const QString &newOwner);
    void itemSignal(const QDBusMessage &message);
    void statusSignal(const QString &status, const QDBusMessage &message);
private:
    struct Item {
        QString owner;
        QString service;
        QString path;
        QString interface;
        QString title;
        QString iconName;
        QString menuPath;
        bool itemIsMenu = false;
        QString status = QStringLiteral("Active");
        QJsonArray menu;
        bool menuLoading = false;
        bool menuFailed = false;
        int menuParent = 0;
        QSet<int> visibleMenuIds;
        QSet<int> submenuIds;
        quint64 request = 0;
        bool refreshPending = false;
        bool refreshQueued = false;
        quint64 menuRequest = 0;
    };
    bool ownedBy(const QString &sender, const QString &service) const;
    void refresh(const QString &id);
    void scheduleRefresh(const QString &id);
    void remove(const QString &id);
    void refreshSignal(const QDBusMessage &message);
    QHash<QString, Item> m_items;
    QStringList m_order;
    QHash<QString, QString> m_hosts;
    QSet<QString> m_dirtyItems;
    QTimer m_refreshTimer;
    quint64 m_nextRequest = 0;
    quint64 m_nextMenuRequest = 0;
};
