// SPDX-License-Identifier: MIT
// Observation only: this executable neither captures pixels nor injects input.
#include "payload.h"
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusContext>
#include <QDBusInterface>
#include <QDBusReply>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTextStream>
#include <unistd.h>

static void emitEvent(QJsonObject object) {
    object.insert("version", 1);
    QTextStream stream(stdout);
    stream << QJsonDocument(object).toJson(QJsonDocument::Compact) << '\n';
    stream.flush();
}
class Observer final : public QObject, protected QDBusContext {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.forge.WindowObserver1")
public:
    explicit Observer(QObject *parent = nullptr) : QObject(parent) {}
public slots:
    void Observe(const QString &payload) {
        const auto owner = QDBusConnection::sessionBus().interface()->serviceOwner("org.kde.KWin");
        if (!calledFromDBus() || !owner.isValid() || message().service() != owner.value()) {
            sendErrorReply(QDBusError::AccessDenied, "Only the current KWin bus owner may observe"); return;
        }
        const auto bytes = payload.toUtf8();
        if (!validObservation(bytes)) { sendErrorReply(QDBusError::InvalidArgs, "Invalid observation"); return; }
        emitEvent(QJsonDocument::fromJson(bytes).object());
    }
    void ActiveChanged(bool active, const QDBusMessage &signal) {
        const auto owner = QDBusConnection::sessionBus().interface()->serviceOwner("org.freedesktop.ScreenSaver");
        if (!owner.isValid() || signal.service() != owner.value()) return;
        emitEvent({{"type", "lock"}, {"locked", active}});
    }
};
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    if (getuid() == 0) return 1;
    auto bus = QDBusConnection::sessionBus();
    if (!bus.isConnected()) return 2;
    Observer observer;
    if (!bus.registerService("org.forge.WindowObserver1")
        || !bus.registerObject("/WindowObserver", &observer, QDBusConnection::ExportAllSlots)) return 3;
    // Start closed; a missing locker is never interpreted as unlocked.
    emitEvent({{"type", "lock"}, {"locked", true}});
    QDBusServiceWatcher watcher("org.kde.KWin", bus, QDBusServiceWatcher::WatchForOwnerChange);
    watcher.addWatchedService("org.freedesktop.ScreenSaver");
    QObject::connect(&watcher, &QDBusServiceWatcher::serviceOwnerChanged, &app,
        [&app](const QString &, const QString &, const QString &) {
            emitEvent({{"type", "lock"}, {"locked", true}});
            emitEvent({{"type", "disconnected"}}); app.exit(4);
        });
    bus.connect("org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver",
        "ActiveChanged", &observer, SLOT(ActiveChanged(bool,QDBusMessage)));
    QDBusInterface locker("org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver", bus);
    const QDBusReply<bool> active = locker.call("GetActive");
    if (active.isValid()) emitEvent({{"type", "lock"}, {"locked", active.value()}});
    emitEvent({{"type", "capabilities"}, {"capture", false}, {"atomic_input", false}});
    return app.exec();
}
#include "main.moc"
