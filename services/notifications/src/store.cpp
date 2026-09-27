#include "store.h"

#include <QJsonDocument>
#include <QJsonObject>
#include <algorithm>
#include <limits>

NotificationStore::NotificationStore(QObject *parent) : QObject(parent) {}

quint32 NotificationStore::nextId() {
    for (quint64 attempts = 0; attempts <= std::numeric_limits<quint32>::max(); ++attempts) {
        const quint32 id = m_nextId++;
        if (m_nextId == 0) m_nextId = 1;
        if (id != 0 && !m_items.contains(id)) return id;
    }
    return 0;
}

NotificationStore::AddResult NotificationStore::add(
    const QString &sender, const QString &app, quint32 replacesId,
    const QString &icon, const QString &summary, const QString &body,
    const QStringList &actions, int timeoutMs) {
    if (sender.isEmpty() || app.size() > 128 || icon.size() > 256 ||
        summary.size() > 1024 || body.size() > 16384 || actions.size() > 16 ||
        actions.size() % 2 != 0 || timeoutMs < -1) return {Result::Invalid, 0};
    for (const QString &action : actions) {
        if (action.isEmpty() || action.size() > 256) return {Result::Invalid, 0};
    }
    if (replacesId && m_items.contains(replacesId) &&
        m_items.value(replacesId).sender != sender) return {Result::WrongSender, 0};

    quint32 id = replacesId ? replacesId : nextId();
    if (!id) return {Result::Invalid, 0};
    if (!m_items.contains(id) && m_items.size() == MaxItems) {
        auto oldest = std::min_element(m_items.cbegin(), m_items.cend(),
            [](const Item &a, const Item &b) { return a.order < b.order; });
        close(oldest.key(), Evicted);
    }
    Item &item = m_items[id];
    item.sender = sender;
    item.app = app;
    item.icon = icon;
    item.summary = summary;
    item.body = body;
    item.actions = actions;
    item.order = ++m_order;
    resetTimer(id, timeoutMs);
    emit changed();
    return {Result::Ok, id};
}

void NotificationStore::resetTimer(quint32 id, int timeoutMs) {
    Item &item = m_items[id];
    if (!item.timer) {
        item.timer = new QTimer(this);
        item.timer->setSingleShot(true);
        connect(item.timer, &QTimer::timeout, this, [this, id] { close(id, Expired); });
    }
    item.timer->stop();
    if (timeoutMs == 0) return;
    const int bounded = timeoutMs == -1 ? 5000 : std::min(timeoutMs, 300000);
    item.timer->start(bounded);
}

NotificationStore::Result NotificationStore::close(quint32 id, CloseReason reason,
                                                    const QString &sender) {
    auto it = m_items.find(id);
    if (it == m_items.end()) return Result::Unknown;
    if (!sender.isEmpty() && it->sender != sender) return Result::WrongSender;
    QTimer *timer = it->timer;
    m_items.erase(it);
    if (timer) timer->deleteLater();
    emit closed(id, reason);
    emit changed();
    return Result::Ok;
}

NotificationStore::Result NotificationStore::invoke(quint32 id, const QString &action) {
    const auto it = m_items.constFind(id);
    if (it == m_items.cend()) return Result::Unknown;
    for (qsizetype i = 0; i < it->actions.size(); i += 2) {
        if (it->actions[i] == action) {
            emit actionInvoked(id, action);
            return Result::Ok;
        }
    }
    return Result::Invalid;
}

QString NotificationStore::snapshot() const {
    QList<quint32> ids = m_items.keys();
    std::sort(ids.begin(), ids.end(), [this](quint32 a, quint32 b) {
        return m_items.value(a).order > m_items.value(b).order;
    });
    QJsonArray entries;
    for (quint32 id : ids) {
        const Item &item = m_items[id];
        QJsonArray actions;
        for (const QString &part : item.actions) actions.append(part);
        entries.append(QJsonObject{{"id", static_cast<qint64>(id)},
            {"app", item.app}, {"icon", item.icon}, {"summary", item.summary},
            {"body", item.body}, {"actions", actions}});
    }
    return QString::fromUtf8(QJsonDocument(QJsonObject{{"version", 1},
                                             {"notifications", entries}}).toJson(QJsonDocument::Compact));
}
