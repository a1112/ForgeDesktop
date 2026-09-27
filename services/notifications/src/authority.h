#pragma once

#include <QByteArray>
#include <QString>

// The compositor sends the current shell's D-Bus unique name over an
// inherited socket. D-Bus itself supplies each method call's real sender.
class ShellAuthority final {
public:
    bool feed(const QByteArray &bytes);
    bool allowed(const QString &sender) const;
private:
    QByteArray m_pending;
    QString m_sender;
};
