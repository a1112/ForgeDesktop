#pragma once

#include <QHash>
#include <QJsonArray>
#include <QObject>
#include <QStringList>
#include <QTimer>

class NotificationStore final : public QObject {
    Q_OBJECT
public:
    enum CloseReason : quint32 { Expired = 1, Dismissed = 2, ClientClosed = 3, Evicted = 4 };
    enum class Result { Ok, Unknown, WrongSender, Invalid };
    struct AddResult { Result result; quint32 id; };

    explicit NotificationStore(QObject *parent = nullptr);
    AddResult add(const QString &sender, const QString &app, quint32 replacesId,
                  const QString &icon, const QString &summary, const QString &body,
                  const QStringList &actions, int timeoutMs);
    Result close(quint32 id, CloseReason reason, const QString &sender = {});
    Result invoke(quint32 id, const QString &action);
    QString snapshot() const;
    qsizetype size() const { return m_items.size(); }

signals:
    void changed();
    void closed(quint32 id, quint32 reason);
    void actionInvoked(quint32 id, const QString &action);

private:
    struct Item {
        QString sender, app, icon, summary, body;
        QStringList actions;
        QTimer *timer = nullptr;
        quint64 order = 0;
    };
    QHash<quint32, Item> m_items;
    quint32 m_nextId = 1;
    quint64 m_order = 0;
    static constexpr qsizetype MaxItems = 64;
    quint32 nextId();
    void resetTimer(quint32 id, int timeoutMs);
};
