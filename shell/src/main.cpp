#include "model.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickImageProvider>
#include <QQuickWindow>
#include <QSocketNotifier>
#include <QIcon>
#include <QPainter>
#include <QtEndian>
#include <sys/socket.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>

class Icons:public QQuickImageProvider{
 Model&m;
public:explicit Icons(Model&model):QQuickImageProvider(Pixmap),m(model){}
 QPixmap requestPixmap(const QString&id,QSize*size,const QSize&requested)override{
  int n=requested.width()>0?qMin(requested.width(),128):48;QString name=m.icon(id);QIcon icon=name.startsWith('/')?QIcon(name):QIcon::fromTheme(name);QPixmap result=icon.pixmap(n,n);
  if(result.isNull()){result=QPixmap(n,n);result.fill(Qt::transparent);QPainter p(&result);p.setRenderHint(QPainter::Antialiasing);p.setPen(Qt::NoPen);p.setBrush(QColor::fromHsv(qHash(id)%360,135,205));p.drawRoundedRect(result.rect(),n/5,n/5);p.setPen(Qt::white);p.drawText(result.rect(),Qt::AlignCenter,id.left(1).toUpper());}if(size)*size=result.size();return result;
 }
};
int main(int argc,char**argv){
 if(geteuid()==0)return 1;
 // The sole control capability is inherited stdin; prevent all desktop launches
 // from inheriting it, including GIO's Exec and D-Bus activation paths.
 int flags=fcntl(STDIN_FILENO,F_GETFD);if(flags<0 || fcntl(0,F_SETFD,flags|FD_CLOEXEC)<0)return 1;
 int status=fcntl(0,F_GETFL);if(status<0 || fcntl(0,F_SETFL,status|O_NONBLOCK)<0)return 1;
 int kind=0;socklen_t length=sizeof(kind);if(getsockopt(0,SOL_SOCKET,SO_TYPE,&kind,&length)<0 || kind!=SOCK_STREAM)return 1;
 qputenv("QT_QUICK_BACKEND","software");qputenv("QSG_RENDER_LOOP","basic");
 QGuiApplication app(argc,argv);app.setQuitOnLastWindowClosed(false);app.setApplicationName("ForgeDesktop");app.setDesktopFileName("org.forge.Desktop");QIcon::setThemeName("Adwaita");
 Model model;model.scanApplications();QQmlApplicationEngine engine;engine.rootContext()->setContextProperty("desktop",&model);engine.addImageProvider("apps",new Icons(model));
 QByteArray input,output;QSocketNotifier reader(0,QSocketNotifier::Read),writer(0,QSocketNotifier::Write);writer.setEnabled(false);
 auto flush=[&](){while(!output.isEmpty()){auto n=::send(0,output.constData(),output.size(),MSG_NOSIGNAL);if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK))break;if(n<=0){app.exit(1);return;}output.remove(0,n);}writer.setEnabled(!output.isEmpty());};
 QObject::connect(&writer,&QSocketNotifier::activated,&app,[&]{flush();});
 QObject::connect(&model,&Model::command,&app,[&](const QByteArray&command){if(command.size()>128||output.size()>4096){app.exit(1);return;}char header[4];qToBigEndian<quint32>(command.size(),header);output.append(header,4);output.append(command);flush();});
 QObject::connect(&reader,&QSocketNotifier::activated,&app,[&]{
  char bytes[16384];auto n=::recv(0,bytes,sizeof(bytes),0);if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK))return;if(n<=0){app.exit(1);return;}input.append(bytes,n);if(input.size()>131072){app.exit(1);return;}
  for(int count=0;count<8 && input.size()>=4;count++){quint32 size=qFromBigEndian<quint32>(input.constData());if(size==0||size>65536){app.exit(1);return;}if(input.size()<size+4)break;if(!model.consume(input.mid(4,size))){app.exit(1);return;}input.remove(0,size+4);}
 });
 QObject::connect(&engine,&QQmlApplicationEngine::objectCreationFailed,&app,[]{QCoreApplication::exit(1);},Qt::QueuedConnection);
 engine.load(QUrl("qrc:/qml/Desktop.qml"));
 for(auto root:engine.rootObjects()){for(auto window:root->findChildren<QQuickWindow*>()){if(window->title()=="forge.launcher")QObject::connect(window,&QQuickWindow::frameSwapped,&model,&Model::launcherFrame);}}
 return app.exec();
}
