#pragma once

#include <QObject>
#include <QTimer>
#include <QVariantList>

class QDBusServiceWatcher;

class Tray final : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList entries READ entries NOTIFY changed)
    Q_PROPERTY(bool online READ online NOTIFY changed)
public:
    explicit Tray(QObject *parent = nullptr);
    QVariantList entries() const { return m_entries; }
    bool online() const { return m_online; }
    static bool parseSnapshot(const QString &json, QVariantList *entries);
    Q_INVOKABLE void activate(const QString &id, int x, int y, bool context);
    Q_INVOKABLE void requestMenu(const QString &id, int parentId);
    Q_INVOKABLE void selectMenu(const QString &id, int menuId);
public slots:
    void refresh();
signals:
    void changed();
private:
    void setState(QVariantList entries, bool online);
    QVariantList m_entries;
    bool m_online = false;
    quint64 m_request = 0;
    QDBusServiceWatcher *m_watcher = nullptr;
    QTimer m_retry;
};
