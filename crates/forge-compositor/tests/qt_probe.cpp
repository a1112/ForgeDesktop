// Isolated M1 integration fixture: an actual Qt 6 Wayland client.
#include <QApplication>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QVBoxLayout>
#include <QWidget>
#include <QResizeEvent>
#include <iostream>
class ProbeWindow : public QWidget {
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
    layout->addWidget(new QPushButton("Native Qt button"));
    QObject::connect(entry, &QLineEdit::textChanged, [](const QString &text) {
        std::cout << "qt-entry:" << text.toUtf8().constData() << std::endl;
    });
    window.show();
    entry->setFocus();
    std::cout << "qt-ready" << std::endl;
    return app.exec();
}
