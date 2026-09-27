#pragma once
#include <QObject>
#include <QVariantList>
#include <QTimer>
#include <QElapsedTimer>
class Model: public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantList windows READ windows NOTIFY stateChanged)
 Q_PROPERTY(QVariantList applications READ applications NOTIFY applicationsChanged)
 Q_PROPERTY(int desktopWidth MEMBER m_width NOTIFY stateChanged)
 Q_PROPERTY(int desktopHeight MEMBER m_height NOTIFY stateChanged)
 Q_PROPERTY(int workspace MEMBER m_workspace NOTIFY stateChanged)
 Q_PROPERTY(bool launcher MEMBER m_launcher NOTIFY stateChanged)
 Q_PROPERTY(QString error READ error NOTIFY errorChanged)
 Q_PROPERTY(QString clock MEMBER m_clock NOTIFY metricsChanged)
 Q_PROPERTY(QString metrics MEMBER m_metrics NOTIFY metricsChanged)
public:
 explicit Model(QObject* parent=nullptr);
 bool consume(const QByteArray&);
 QVariantList windows() const {return m_windows;}
 QVariantList applications() const {return m_apps;}
 Q_INVOKABLE bool launch(const QString&);
 Q_INVOKABLE void windowCommand(const QString&,const QString&);
 Q_INVOKABLE void switchWorkspace(int);
 Q_INVOKABLE void moveWindow(const QString&,int);
 Q_INVOKABLE void showLauncher(bool);
 void scanApplications();
 void launcherFrame();
 QString icon(const QString&) const;
 QString error() const {return m_error;}
 static bool visibleEntry(const QString&);
signals:
 void stateChanged();void applicationsChanged();void errorChanged();void metricsChanged();
 void command(const QByteArray&);
private:
 QVariantList m_windows,m_apps;
 QString m_error,m_clock,m_metrics;
 int m_width=1280,m_height=800,m_workspace=0;
 bool m_launcher=false;
 quint64 m_cpuTotal=0,m_cpuIdle=0,m_net=0;
 QTimer m_timer;QElapsedTimer m_sample;
 QElapsedTimer m_launcherLatency;int m_perfSamples=0;
 quint32 m_launcherSerial=0;bool m_launcherFrameLogged=false;
 void sampleMetrics();
};
