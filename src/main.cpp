#ifdef AI_SELF_TEST
#include "../tests/ai/context_test.h"
#include "../tests/ai/classroom_test.h"
#include "../tests/ai/quiz_test.h"
#endif
/***************************************************************************
 *   Copyright (C) 2012 by Santiago González                               *
 *                                                                         *
 ***( see copyright.txt file at root folder )*******************************/

#include <QApplication>
#include <QSslSocket>
#include <QTranslator>
#include <QStandardPaths>
#include <QtGui>

#include "mainwindow.h"
#include "circuitwidget.h"
#include "editorwindow.h"
#include "batchtest.h"

void myMessageOutput( QtMsgType type, const QMessageLogContext &context, const QString &msg )
{
    QByteArray localMsg = msg.toLocal8Bit();
    const char* file     = context.file ? context.file : "";
    const char* function = context.function ? context.function : "";
    switch (type) {
    case QtDebugMsg:
        if( CircuitWidget::self() ) CircuitWidget::self()->simDebugMessage( msg );
        fprintf( stderr, "%s \n", localMsg.constData() );
        break;
    case QtInfoMsg:
        fprintf(stderr, "Info: %s (%s:%u, %s)\n", localMsg.constData(), file, context.line, function);
        break;
    case QtWarningMsg:
        fprintf(stderr, "Warning: %s (%s:%u, %s)\n", localMsg.constData(), file, context.line, function);
        break;
    case QtCriticalMsg:
        fprintf(stderr, "Critical: %s (%s:%u, %s)\n", localMsg.constData(), file, context.line, function);
        break;
    case QtFatalMsg:
        fprintf(stderr, "Fatal: %s (%s:%u, %s)\n", localMsg.constData(), file, context.line, function);
        break;
    }
}

QString langFile( QString locale )
{
    QString langF = ":/simulide_"+locale+".qm";

    if( !QFile::exists( langF ) ) langF = "";

    return langF;
}

int main( int argc, char *argv[] )
{
    qInstallMessageHandler( myMessageOutput );

#ifdef _WIN32
    if (AttachConsole(ATTACH_PARENT_PROCESS)) {
        freopen("CONOUT$", "w", stdout);
        freopen("CONOUT$", "w", stderr);
    }
#endif

    QApplication app( argc, argv );
    if (app.arguments().contains("-ai-check-tls")) {
        const bool supported = QSslSocket::supportsSsl();
        fprintf(stderr, "AI TLS: %s; compiled=%s; runtime=%s\n", supported ? "OK" : "MISSING",
                qPrintable(QSslSocket::sslLibraryBuildVersionString()),
                qPrintable(QSslSocket::sslLibraryVersionString()));
        return supported ? 0 : 2;
    }

    QSettings settings( QStandardPaths::standardLocations( QStandardPaths::AppDataLocation).first()+"/simulide.ini",  QSettings::IniFormat, 0l );

    QString locale = QLocale::system().name();
    if( settings.contains( "language" ) ) locale = settings.value( "language" ).toString();

    QString langF = langFile( locale );
    if( langF == "" )
    {
        locale = QLocale::system().name().split("_").first();
        langF = langFile( locale );
    }
    if( langF == "" ) langF = ":/simulide_en.qm";

    QTranslator translator;
    if( translator.load( langF ) )
        app.installTranslator( &translator );

    app.setApplicationVersion( APP_VERSION );

    MainWindow window;
    window.setLoc( locale );
    window.show();

#ifdef AI_SELF_TEST
    if (app.arguments().contains("-ai-quiz-test")) {
        QTimer::singleShot(0, [&window] { runAiQuizTest(&window); });
        return app.exec();
    }
    if (app.arguments().contains("-ai-classroom-test")) {
        QTimer::singleShot(0, [&window] { runAiClassroomTest(&window); });
        return app.exec();
    }
    if (app.arguments().contains("-ai-self-test")) {
        QTimer::singleShot(0, [] { runAiContextTest(); });
        return app.exec();
    }
#endif
    bool noGui = false;

    for( int i=1; i<argc; ++i )
    {
        QString arg = QString::fromStdString( argv[i] );

        if( arg == "-nogui")
        {
            window.hideGui();
            noGui = true;
        }
        else if( arg == "-test" )
        {
            i++;
            if( i >= argc ){
                qDebug() <<"ERROR: missing argument for"<< arg;
                break;
            }
            arg = QString::fromStdString( argv[i] );
            QTimer::singleShot( 500, [arg](){ BatchTest::doBatchTest( arg ); } );
            break;
        }
        else{
            QString file = "file://";
            if( arg.startsWith( file ) ) arg.replace( file, "" ).replace("\r\n", "" ).replace("%20", " ");
#ifdef _WIN32
            if( arg.startsWith( "/" )) arg.remove( 0, 1 );
#endif
            if( !QFile::exists( arg ) ){
                qDebug() <<"ERROR: unrecognized argument"<< arg;
                break;
            }
            if( arg.endsWith(".sim2") || arg.endsWith(".sim1"))
            {
                QTimer::singleShot( 500, CircuitWidget::self()
                                  , [arg,noGui]()->void{ CircuitWidget::self()->loadCirc( arg );
                                                   if( noGui ) MainWindow::self()->hideGui(); } );
            }
            else{
                QTimer::singleShot( 500, CircuitWidget::self()
                                   , [arg]()->void{ EditorWindow::self()->loadFile( arg ); } );
            }
            break;
        }
    }

    return app.exec();
}

