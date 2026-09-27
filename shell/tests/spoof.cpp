// Same title/app-id, different PID: must remain an ordinary 640x480 window.
#include <QApplication>
#include <QWidget>
#include <QResizeEvent>
#include <cstdio>
class Probe:public QWidget{void resizeEvent(QResizeEvent*e)override{std::printf("spoof-size:%dx%d\n",e->size().width(),e->size().height());std::fflush(stdout);}};
int main(int argc,char**argv){QApplication app(argc,argv);app.setDesktopFileName("org.forge.Desktop");Probe p;p.setWindowTitle("forge.panel");p.resize(640,480);p.show();return app.exec();}
