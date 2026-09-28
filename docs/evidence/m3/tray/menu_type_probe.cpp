// Lab-only: inspect Qt's decoded DBusMenu GetLayout reply in the isolated VM.
#include <QCoreApplication>
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDebug>
#include <cstdio>

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    if (argc != 2) return 2;
    auto bus = QDBusConnection::sessionBus();
    auto request = QDBusMessage::createMethodCall(QString::fromLocal8Bit(argv[1]),
        QStringLiteral("/MenuBar"), QStringLiteral("com.canonical.dbusmenu"),
        QStringLiteral("GetLayout"));
    request.setArguments({0, 1, QStringList{}});
    const auto reply = bus.call(request, QDBus::Block, 2000);
    std::fprintf(stderr, "reply=%d error=%s count=%lld\n", int(reply.type()),
                 reply.errorName().toUtf8().constData(),
                 static_cast<long long>(reply.arguments().size()));
    for (const auto &value : reply.arguments()) {
        std::fprintf(stderr, "arg=%s\n", value.metaType().name());
        if (value.metaType() == QMetaType::fromType<QDBusArgument>()) {
            const QDBusArgument data = value.value<QDBusArgument>();
            std::fprintf(stderr, "type=%d signature=%s\n", int(data.currentType()),
                         data.currentSignature().toUtf8().constData());
            if (data.currentType() == QDBusArgument::StructureType) {
                data.beginStructure();
                std::fprintf(stderr, "after_begin=%d signature=%s\n",
                             int(data.currentType()),
                             data.currentSignature().toUtf8().constData());
            }
        }
    }
    return 0;
}
