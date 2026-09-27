#include "model.h"
#include <QDateTime>
#include <QFile>
#include <QRegularExpression>
#include <QStorageInfo>
#include <QDir>
#include <QSet>
#include <algorithm>
#include <cstdio>
#undef signals
#include <gio/gdesktopappinfo.h>

static bool integer(const QByteArray&s,int lo,int hi,int&out){bool ok=false;out=s.toInt(&ok);return ok && out>=lo && out<=hi;}
static bool handle(const QByteArray&s){static const QRegularExpression r("^w[0-9a-f]{16}$");return r.match(QString::fromLatin1(s)).hasMatch();}
static bool hex(const QByteArray&s){return s.size()<=512 && s.size()%2==0 && std::all_of(s.begin(),s.end(),[](char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');});}
Model::Model(QObject*parent):QObject(parent){connect(&m_timer,&QTimer::timeout,this,&Model::sampleMetrics);m_timer.start(2000);m_sample.start();sampleMetrics();}
bool Model::consume(const QByteArray&payload){
 if(payload.size()>65536)return false;
 if(payload.startsWith("1\tpresented\t")){auto p=payload.split('\t');bool ok=false;quint32 serial=p.value(2).toUInt(&ok);if(p.size()!=3||!ok)return false;if(serial==m_launcherSerial && m_launcherLatency.isValid()){if(m_perfSamples<10000)std::fprintf(stderr,"ForgeDesktop launcher-compositor-submit-us=%lld\n",static_cast<long long>(m_launcherLatency.nsecsElapsed()/1000));m_launcherLatency.invalidate();}return true;}
 auto lines=payload.split('\n');if(lines.empty())return false;
 auto h=lines.takeFirst().split('\t');int w,hgt,workspace,launcher;
 if(h.size()!=6 || h[0]!="1" || h[1]!="state" || !integer(h[2],64,16384,w) || !integer(h[3],64,16384,hgt) || !integer(h[4],0,3,workspace) || !integer(h[5],0,1,launcher))return false;
 QVariantList windows,outputs;QSet<QByteArray> ids,outputIds;bool pending=false,displayRow=false;
 for(const auto&line:lines){if(line.isEmpty())continue;auto f=line.split('\t');int ws,mini,maxi,full,focus;
  if(f[0]=="d"){int v;if(displayRow||f.size()!=2||!integer(f[1],0,1,v))return false;displayRow=true;pending=v;continue;}
  if(f[0]=="o"){int id,scale,x,y,pw,ph;if(outputs.size()>=4||f.size()!=7||outputIds.contains(f[1])||!integer(f[1],1,2147483647,id)||!integer(f[2],1000,2000,scale)||(scale!=1000&&scale!=1500&&scale!=2000)||!integer(f[3],0,16384,x)||!integer(f[4],0,16384,y)||!integer(f[5],64,8192,pw)||!integer(f[6],64,8192,ph))return false;outputIds.insert(f[1]);outputs.append(QVariantMap{{"id",id},{"scale",scale},{"x",x},{"y",y},{"width",pw},{"height",ph}});continue;}
  if(windows.size()>=68 || f.size()!=8 || !handle(f[0]) || ids.contains(f[0]) || !hex(f[1]) || !hex(f[2]) || !integer(f[3],0,3,ws) || !integer(f[4],0,1,mini) || !integer(f[5],0,1,maxi) || !integer(f[6],0,1,full) || !integer(f[7],0,1,focus))return false;
  ids.insert(f[0]);windows.append(QVariantMap{{"id",QString::fromLatin1(f[0])},{"title",QString::fromUtf8(QByteArray::fromHex(f[1]))},{"appId",QString::fromUtf8(QByteArray::fromHex(f[2]))},{"workspace",ws},{"minimized",bool(mini)},{"maximized",bool(maxi)},{"fullscreen",bool(full)},{"focused",bool(focus)}});
 }
 m_windows=windows;m_outputs=outputs;m_displayPending=pending;m_width=w;m_height=hgt;m_workspace=workspace;m_launcher=launcher;emit stateChanged();return true;
}
void Model::configureOutput(int id,int scale,int x,int y){if(id<=0||(scale!=1000&&scale!=1500&&scale!=2000)||x<0||x>16384||y<0||y>16384)return;emit command("1\toutput\t"+QByteArray::number(id)+'\t'+QByteArray::number(scale)+'\t'+QByteArray::number(x)+'\t'+QByteArray::number(y));}
void Model::confirmDisplay(bool keep){emit command(keep?"1\tdisplay-confirm":"1\tdisplay-revert");}
bool Model::visibleEntry(const QString&file){auto a=g_desktop_app_info_new_from_filename(file.toUtf8().constData());if(!a)return false;bool visible=!g_desktop_app_info_get_is_hidden(a) && !g_desktop_app_info_get_nodisplay(a) && g_desktop_app_info_get_show_in(a,"ForgeDesktop");g_object_unref(a);return visible;}
void Model::scanApplications(){
 QVariantList apps;auto all=g_app_info_get_all();
 for(auto l=all;l;l=l->next){auto a=G_APP_INFO(l->data);if(!G_IS_DESKTOP_APP_INFO(a))continue;auto d=G_DESKTOP_APP_INFO(a);auto id=g_app_info_get_id(a);if(!id || g_desktop_app_info_get_is_hidden(d) || g_desktop_app_info_get_nodisplay(d) || !g_desktop_app_info_get_show_in(d,"ForgeDesktop"))continue;
  auto icon=g_app_info_get_icon(a);QString iconName;if(icon && G_IS_THEMED_ICON(icon)){auto names=g_themed_icon_get_names(G_THEMED_ICON(icon));if(names&&*names)iconName=QString::fromUtf8(*names);}else if(icon && G_IS_FILE_ICON(icon)){char*path=g_file_get_path(g_file_icon_get_file(G_FILE_ICON(icon)));iconName=QString::fromUtf8(path?path:"");g_free(path);}
  auto wm=g_desktop_app_info_get_startup_wm_class(d);
  apps.append(QVariantMap{{"id",QString::fromUtf8(id)},{"name",QString::fromUtf8(g_app_info_get_display_name(a))},{"description",QString::fromUtf8(g_app_info_get_description(a)?g_app_info_get_description(a):"")},{"icon",iconName},{"wmClass",QString::fromUtf8(wm?wm:"")}});
  if(apps.size()>=2048)break;
 }
 g_list_free_full(all,g_object_unref);std::sort(apps.begin(),apps.end(),[](const QVariant&a,const QVariant&b){return QString::localeAwareCompare(a.toMap()["name"].toString(),b.toMap()["name"].toString())<0;});m_apps=apps;emit applicationsChanged();
}
QString Model::icon(const QString&id)const{for(const auto&a:m_apps){auto m=a.toMap();QString desktopId=m["id"].toString();if(desktopId.compare(id,Qt::CaseInsensitive)==0 || desktopId.compare(id+".desktop",Qt::CaseInsensitive)==0 || (!id.isEmpty()&&m["wmClass"].toString().compare(id,Qt::CaseInsensitive)==0))return m["icon"].toString();}return {};}
bool Model::launch(const QString&id){
 auto a=g_desktop_app_info_new(id.toUtf8().constData());if(!a){m_error="Application is no longer installed: "+id;emit errorChanged();return false;}
 if(g_desktop_app_info_get_is_hidden(a)||g_desktop_app_info_get_nodisplay(a)||!g_desktop_app_info_get_show_in(a,"ForgeDesktop")){g_object_unref(a);m_error="Application is hidden in this desktop";emit errorChanged();return false;}
 GError*error=nullptr;auto context=g_app_launch_context_new();g_app_launch_context_setenv(context,"XDG_CURRENT_DESKTOP","ForgeDesktop");g_app_launch_context_unsetenv(context,"QT_WAYLAND_DISABLE_WINDOWDECORATION");bool ok=g_app_info_launch(G_APP_INFO(a),nullptr,context,&error);g_object_unref(context);g_object_unref(a);
 m_error=ok?QString():QString::fromUtf8(error?error->message:"Application launch failed");if(error)g_error_free(error);emit errorChanged();if(ok)showLauncher(false);return ok;
}
void Model::windowCommand(const QString&action,const QString&id){static const QStringList allowed={"activate","close","minimize","restore","maximize","fullscreen","normal","left","right"};if(allowed.contains(action)&&handle(id.toLatin1()))emit command("1\t"+action.toUtf8()+"\t"+id.toUtf8());}
void Model::switchWorkspace(int n){if(n>=0&&n<4)emit command("1\tworkspace\t"+QByteArray::number(n));}
void Model::moveWindow(const QString&id,int n){if(handle(id.toLatin1())&&n>=0&&n<4)emit command("1\tmove\t"+id.toUtf8()+"\t"+QByteArray::number(n));}
void Model::showLauncher(bool show){++m_launcherSerial;m_launcherFrameLogged=false;if(show && !m_launcher && qEnvironmentVariableIsSet("FORGE_DESKTOP_PERF_FILE"))m_launcherLatency.start();else m_launcherLatency.invalidate();emit command(QByteArray(show?"1\tlauncher\t1\t":"1\tlauncher\t0\t")+QByteArray::number(m_launcherSerial));}
void Model::launcherFrame(){if(m_launcher && m_launcherLatency.isValid() && !m_launcherFrameLogged){if(m_perfSamples++<10000)std::fprintf(stderr,"ForgeDesktop launcher-submit-us=%lld\n",static_cast<long long>(m_launcherLatency.nsecsElapsed()/1000));m_launcherFrameLogged=true;}}
static QByteArray read(const QString&p){QFile f(p);return f.open(QIODevice::ReadOnly)?f.readAll():QByteArray();}
void Model::sampleMetrics(){
 m_clock=QDateTime::currentDateTime().toString("ddd  MMM d   HH:mm");
 auto cpu=read("/proc/stat").split('\n').value(0).simplified().split(' ');quint64 total=0,idle=0;for(int i=1;i<cpu.size()&&i<=8;i++)total+=cpu[i].toULongLong();if(cpu.size()>5)idle=cpu[4].toULongLong()+cpu[5].toULongLong();
 QString percent="—";if(m_cpuTotal&&total>m_cpuTotal)percent=QString::number(100.0*(1.0-double(idle-m_cpuIdle)/double(total-m_cpuTotal)),'f',0)+"%";m_cpuTotal=total;m_cpuIdle=idle;
 quint64 ram=0,available=0;for(const auto&line:read("/proc/meminfo").split('\n')){auto a=line.simplified().split(' ');if(a.value(0)=="MemTotal:")ram=a.value(1).toULongLong();if(a.value(0)=="MemAvailable:")available=a.value(1).toULongLong();}
 quint64 net=0;for(const auto&line:read("/proc/net/dev").split('\n')){auto a=line.simplified().split(' ');if(a.size()>=17&&a[0]!="lo:"){net+=a[1].toULongLong()+a[9].toULongLong();}}
 qint64 elapsed=m_sample.restart();QString rate="—";if(m_net&&elapsed>0&&net>=m_net)rate=QString::number(double(net-m_net)*1000/elapsed/1024,'f',0)+" KiB/s";m_net=net;
 QStorageInfo disk(QDir::homePath());QString storage=disk.isValid()?QString::number(double(disk.bytesAvailable())/(1024*1024*1024),'f',1)+" GiB free":"—";
 m_metrics=QString("CPU %1   RAM %2/%3 GiB   Disk %4   Net %5").arg(percent).arg(double(ram-available)/(1024*1024),0,'f',1).arg(double(ram)/(1024*1024),0,'f',1).arg(storage,rate);emit metricsChanged();
}
