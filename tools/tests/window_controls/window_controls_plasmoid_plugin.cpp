// Test-only implementation of the Plasma attached properties used by the
// production QML. This does not implement or qualify a real Plasma runtime.
#include <QObject>
#include <QVariant>
#include <QAccessible>
#include <QQmlExtensionPlugin>
#include <qqml.h>

class TestConfiguration : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString displayRole MEMBER displayRole CONSTANT)
public:
    using QObject::QObject;
    QString displayRole = QStringLiteral("controls");
    Q_INVOKABLE QVariantList waylandIds() const {
        return {QStringLiteral("{9cf0e382-caa6-4b59-8758-7e90e398ab01}")};
    }
    Q_INVOKABLE QVariantList x11Ids() const {
        return {QVariant::fromValue<quint64>(4294967295)};
    }
    Q_INVOKABLE bool accessiblePress(QObject *button) const {
        QAccessible::setActive(true);
        auto *interface = QAccessible::queryAccessibleInterface(button);
        if (!interface || !interface->actionInterface())
            return false;
        auto *action = interface->actionInterface();
        const auto press = QAccessibleActionInterface::pressAction();
        if (!action->actionNames().contains(press))
            return false;
        action->doAction(press);
        return true;
    }
};

class TestPlasmoidAttached : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString title MEMBER title)
    Q_PROPERTY(int backgroundHints MEMBER backgroundHints)
    Q_PROPERTY(QObject *configuration READ configuration CONSTANT)
public:
    explicit TestPlasmoidAttached(QObject *parent) : QObject(parent), config(this) {}
    QString title;
    int backgroundHints = 0;
    TestConfiguration config;
    QObject *configuration() { return &config; }
};

class TestPlasmoid : public QObject {
    Q_OBJECT
public:
    using QObject::QObject;
    static TestPlasmoidAttached *qmlAttachedProperties(QObject *object) {
        return new TestPlasmoidAttached(object);
    }
};
QML_DECLARE_TYPEINFO(TestPlasmoid, QML_HAS_ATTACHED_PROPERTIES)

class WindowControlsPlasmoidPlugin : public QQmlExtensionPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QQmlExtensionInterface_iid)
public:
    void registerTypes(const char *uri) override {
        qmlRegisterType<TestPlasmoid>(uri, 1, 0, "Plasmoid");
    }
};

#include "window_controls_plasmoid_plugin.moc"
