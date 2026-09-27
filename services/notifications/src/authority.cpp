#include "authority.h"

#include <algorithm>

namespace {
constexpr qsizetype MaxLine = 128;
bool uniqueName(const QByteArray &name) {
    if (name.size() < 4 || name.size() > 32 || !name.startsWith(":1.")) return false;
    return std::all_of(name.cbegin() + 3, name.cend(), [](char ch) {
        return ch >= '0' && ch <= '9';
    });
}
}

bool ShellAuthority::feed(const QByteArray &bytes) {
    if (m_pending.size() + bytes.size() > MaxLine * 2) {
        m_sender.clear();
        return false;
    }
    m_pending.append(bytes);
    for (;;) {
        const qsizetype end = m_pending.indexOf('\n');
        if (end < 0) {
            if (m_pending.size() > MaxLine) {
                m_sender.clear();
                return false;
            }
            return true;
        }
        if (end < 1 || end > MaxLine) {
            m_sender.clear();
            return false;
        }
        const QByteArray line = m_pending.left(end);
        m_pending.remove(0, end + 1);
        if (line == "1\trevoke") {
            m_sender.clear();
        } else if (line.startsWith("1\tauthorize\t") &&
                   uniqueName(line.mid(sizeof("1\tauthorize\t") - 1))) {
            m_sender = QString::fromLatin1(line.mid(sizeof("1\tauthorize\t") - 1));
        } else {
            m_sender.clear();
            return false;
        }
    }
}

bool ShellAuthority::allowed(const QString &sender) const {
    return !m_sender.isEmpty() && sender == m_sender;
}
