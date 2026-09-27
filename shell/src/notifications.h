#pragma once

#include <QObject>
#include <QVariantList>
#include <QTimer>

class QDBusServiceWatcher;

class Notifications final : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList entries READ entries NOTIFY changed)
    Q_PROPERTY(bool online READ online NOTIFY changed)
public:
    explicit Notifications(QObject *parent = nullptr);
    QVariantList entries() const { return m_entries; }
    bool online() const { return m_online; }
    Q_INVOKABLE void dismiss(quint32 id);
    Q_INVOKABLE void invoke(quint32 id, const QString &action);
    static bool parseSnapshot(const QString &json, QVariantList *entries);
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
