// Isolated M1 integration fixture: an actual Qt 6 Wayland client.
#include <QApplication>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QVBoxLayout>
#include <QWidget>
#include <QResizeEvent>
#include <QWheelEvent>
#include <QMenu>
#include <QWidgetAction>
#include <iostream>
class ProbeWindow : public QWidget {
    void wheelEvent(QWheelEvent *event) override {
        std::cout << "qt-wheel:" << event->angleDelta().x() << "," << event->angleDelta().y() << std::endl;
        event->accept();
    }
    void resizeEvent(QResizeEvent *event) override {
        std::cout << "qt-size:" << event->size().width() << "x" << event->size().height() << std::endl;
        QWidget::resizeEvent(event);
    }
};
int main(int argc, char **argv) {
    QApplication app(argc, argv);
    ProbeWindow window;
    window.setWindowTitle("ForgeDesktop Qt native probe");
    window.resize(640, 480);
    auto *layout = new QVBoxLayout(&window);
    layout->setContentsMargins(24, 24, 24, 24);
    layout->addWidget(new QLabel(QString::fromUtf8("Real Qt 6 / Wayland / Pixman\nChinese text: 中文输入验证")));
    auto *entry = new QLineEdit;
    entry->setPlaceholderText("Keyboard input is logged by this fixture");
    layout->addWidget(entry);
    auto *button = new QPushButton("Native Qt button");
    layout->addWidget(button);
    if (argc > 1 && QByteArray(argv[1]) == "popup") {
        QObject::connect(button, &QPushButton::clicked, [&] {
            auto *menu = new QMenu(&window);
            auto *action = new QWidgetAction(menu);
            auto *popupEntry = new QLineEdit(menu);
            popupEntry->setMinimumWidth(220);
            action->setDefaultWidget(popupEntry);
            menu->addAction(action);
            menu->popup(window.mapToGlobal(QPoint(100, 200)));
            popupEntry->setFocus();
            // A reused IME surface must not be inserted twice in the root tree.
        });
    }
    QObject::connect(entry, &QLineEdit::textChanged, [](const QString &text) {
        std::cout << "qt-entry:" << text.toUtf8().constData() << std::endl;
    });
    window.show();
    entry->setFocus();
    std::cout << "qt-ready" << std::endl;
    return app.exec();
}
