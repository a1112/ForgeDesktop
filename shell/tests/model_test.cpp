#include "model.h"
#include <QtTest>
#include <QTemporaryDir>
class Tests:public QObject{
 Q_OBJECT
private slots:
 void outputs(){Model m;QVERIFY(m.consume("1\tstate\t1280\t800\t0\t0\nd\t1\no\t27\t1500\t1280\t0\t1280\t800\n"));QVERIFY(!m.consume("1\tstate\t1280\t800\t0\t0\no\t27\t0\t0\t0\t1280\t800\n"));}
 void reconciliation(){Model m;QVERIFY(m.consume("1\tstate\t1280\t800\t0\t0\nw0000000000000001\t4142\t7174\t0\t0\t0\t0\t1\n"));QCOMPARE(m.windows().size(),1);QCOMPARE(m.windows()[0].toMap()["title"].toString(),"AB");QVERIFY(m.consume("1\tstate\t1280\t800\t1\t0\n"));QVERIFY(m.windows().isEmpty());}
 void rejection(){Model m;QVERIFY(!m.consume("2\tstate\t1280\t800\t0\t0\n"));QVERIFY(!m.consume(QByteArray(65537,'x')));QVERIFY(!m.consume("1\tstate\t1280\t800\t9\t0\n"));QVERIFY(!m.consume("1\tstate\t1280\t800\t0\t0\n../../x\t\t\t0\t0\t0\t0\t0\n"));}
 void desktopFiles(){QTemporaryDir d;auto put=[&](const QString& name,const QByteArray& fields){QString p=d.path()+"/"+name+".desktop";QFile f(p);if(!f.open(QIODevice::WriteOnly))return QString();f.write("[Desktop Entry]\nType=Application\nName=Test\nExec=/usr/bin/true\n"+fields);return p;};QVERIFY(Model::visibleEntry(put("show","")));QVERIFY(!Model::visibleEntry(put("hidden","Hidden=true\n")));QVERIFY(!Model::visibleEntry(put("nodisplay","NoDisplay=true\n")));QVERIFY(!Model::visibleEntry(put("other","OnlyShowIn=UnrelatedDesktop;\n")));}
 void launchFailure(){Model m;QVERIFY(!m.launch("org.forge.does-not-exist.desktop"));QVERIFY(!m.error().isEmpty());}
};
QTEST_GUILESS_MAIN(Tests)
#include "model_test.moc"
