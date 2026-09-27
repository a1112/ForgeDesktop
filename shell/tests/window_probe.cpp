// Deterministic Wayland client pixels and input, for policy acceptance only.
#include <QApplication>
#include <QWidget>
#include <QPainter>
#include <QKeyEvent>
#include <QMouseEvent>
#include <QResizeEvent>
#include <cstdio>
class Probe:public QWidget {
 QColor color;
public:explicit Probe(bool second):color(second?QColor(40,100,220):QColor(32,180,100)) {setWindowFlags(Qt::FramelessWindowHint);setFocusPolicy(Qt::StrongFocus);setWindowTitle(second?"Policy secondary":"Policy primary");resize(640,480);}
 void paintEvent(QPaintEvent*)override{QPainter p(this);p.fillRect(rect(),color);p.setPen(Qt::white);p.drawText(20,50,windowTitle());}
 void keyPressEvent(QKeyEvent*e)override{std::printf("key:%s\n",e->text().toUtf8().constData());std::fflush(stdout);}
 void mousePressEvent(QMouseEvent*e)override{std::printf("click:%d,%d\n",int(e->position().x()),int(e->position().y()));std::fflush(stdout);setFocus();}
 void resizeEvent(QResizeEvent*e)override{std::printf("size:%dx%d\n",e->size().width(),e->size().height());std::fflush(stdout);}
};
int main(int argc,char**argv){QApplication app(argc,argv);Probe p(argc>1);p.show();return app.exec();}
