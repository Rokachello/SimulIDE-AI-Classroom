// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "aiassistant.h"
#include "circuit.h"
#include <QApplication>
#include <QDialog>
#include <QComboBox>
#include <QLineEdit>
#include <QLabel>
#include <QPushButton>
#include <QPlainTextEdit>
#include <QTextEdit>
#include <QTimer>
#include <QInputDialog>
#include <QFileDialog>
#include <QFileInfo>
#include <QAction>
#include <memory>
#include <cstdlib>
inline void runAiClassroomTest(QWidget* window) {
    fprintf(stderr,"CLASSROOM START\n");
    Circuit::self()->createComponent("Voltage Source","ClassroomV",QPoint(-100,-100));
    AiAssistant* dock;
    // AiAssistant has no Q_OBJECT; find by dock object name and static cast.
    dock=static_cast<AiAssistant*>(window->findChild<QDockWidget*>("AiAssistantDock"));
    if (!dock) { fprintf(stderr,"CLASSROOM FAIL: no dock\n"); std::exit(1); return; }
    dock->close();
    auto* openAssistant=window->findChild<QAction*>("aiOpenAssistantAction");
    if (!openAssistant) { fprintf(stderr,"CLASSROOM FAIL: no reopen action\n"); std::exit(1); return; }
    openAssistant->trigger();
    if (dock->isHidden()) { fprintf(stderr,"CLASSROOM FAIL: reopen action did not show dock\n"); std::exit(1); return; }
    fprintf(stderr,"CLASSROOM PASS: closed assistant reopened using toolbar action\n");
    auto step=std::make_shared<int>(0); auto ticks=std::make_shared<int>(0);
    auto* timer=new QTimer(window);
    QObject::connect(timer,&QTimer::timeout,window,[dock,step,ticks,timer] {
        if (++*ticks>300) { fprintf(stderr,"CLASSROOM FAIL: timeout, stage %d\n",*step); std::exit(1); return; }
        if (*ticks % 20 == 0) fprintf(stderr,"CLASSROOM stage=%d status=%s\n",*step,qPrintable(dock->findChild<QLabel*>("aiStatus")->text()));
        auto* modal=qobject_cast<QDialog*>(QApplication::activeModalWidget());
        if (*step==0) { *step=1; QTimer::singleShot(0,dock,[dock] { dock->findChild<QPushButton*>("aiLoginButton")->click(); }); }
        else if (*step==1 && modal && modal->findChild<QLineEdit*>("aiUsername")) {
            modal->findChild<QLineEdit*>("aiServer")->setText("http://127.0.0.1:8765");
            modal->findChild<QLineEdit*>("aiUsername")->setText("teststudent");
            modal->findChild<QLineEdit*>("aiPassword")->setText("testpass123"); *step=2; modal->accept();
        } else if (*step==2 && modal && modal->findChild<QComboBox*>("aiLessonChoice")) {
            auto* combo=modal->findChild<QComboBox*>("aiLessonChoice"); combo->setCurrentIndex(combo->findData(1)); *step=3; modal->accept();
        } else if (*step==3 && dock->findChild<QPushButton*>("aiSendButton")->isEnabled() && dock->findChild<QLabel*>("aiStatus")->text().contains(QString::fromUtf8("Pogovor je shranjen"))) {
            dock->findChild<QPlainTextEdit*>("aiQuestion")->setPlainText("native-classroom-test"); *step=4; dock->findChild<QPushButton*>("aiSendButton")->click();
        } else if (*step==4 && dock->findChild<QTextEdit*>("aiTranscript")->toPlainText().contains("[DEMO")) {
            if (!qgetenv("SIMULIDE_UI_CAPTURE").isEmpty()) dock->grab().save(QString::fromUtf8(qgetenv("SIMULIDE_UI_CAPTURE"))+"-chat.png");
            if (!qgetenv("SIMULIDE_LEARNING_TEST").isEmpty()) { *step=5; QTimer::singleShot(0,dock,[dock] { dock->findChild<QPushButton*>("aiHelpButton")->click(); }); return; }
            fprintf(stderr,"CLASSROOM PASS: native login, lesson, snapshot, send and response\n"); timer->stop();
            if (!qgetenv("SIMULIDE_UI_CAPTURE").isEmpty()) dock->grab().save(QString::fromUtf8(qgetenv("SIMULIDE_UI_CAPTURE")));
            std::exit(0);
        } else if (*step==5 && qobject_cast<QInputDialog*>(modal)) {
            auto* input=qobject_cast<QInputDialog*>(modal); input->setTextValue(QString::fromUtf8("Potrebujem učitelja pri vezavi uporov.")); *step=6; input->accept();
        } else if (*step==6 && dock->findChild<QPushButton*>("aiHelpButton")->isEnabled()) {
            if (!dock->findChild<QPushButton*>("aiChallengeButton")->isEnabled()) { fprintf(stderr,"CLASSROOM FAIL: challenge disabled\n"); std::exit(1); }
            *step=7; QTimer::singleShot(0,dock,[dock] { dock->findChild<QPushButton*>("aiChallengeButton")->click(); });
        } else if (*step==7 && qobject_cast<QFileDialog*>(modal)) {
            auto* file=qobject_cast<QFileDialog*>(modal); file->setDirectory(QFileInfo(QString::fromUtf8(qgetenv("SIMULIDE_TEST_ORIGINAL"))).absolutePath()); file->selectFile("original.sim2"); *step=8; QTimer::singleShot(250,file,[file] { auto* name=file->findChild<QLineEdit*>("fileNameEdit"); if(name) name->setText("original.sim2"); QMetaObject::invokeMethod(file,"accept",Qt::DirectConnection); });
        } else if (*step==8 && dock->findChild<QComboBox*>("aiChallengeChoices")->count()>0 && dock->findChild<QPushButton*>("aiChallengeSubmit")->isEnabled()) {
            const QString original=QString::fromUtf8(qgetenv("SIMULIDE_TEST_ORIGINAL"));
            if (!QFileInfo::exists(original) || Circuit::self()->getFilePath()==original || !Circuit::self()->getFilePath().contains("-izziv-")) { fprintf(stderr,"CLASSROOM FAIL: original/copy not protected\n"); std::exit(1); }
            dock->findChild<QComboBox*>("aiChallengeChoices")->setCurrentIndex(0); *step=9; dock->findChild<QPushButton*>("aiChallengeSubmit")->click();
        } else if (*step==9 && dock->findChild<QComboBox*>("aiChallengeChoices")->count()==0 && dock->findChild<QPushButton*>("aiChallengeSubmit")->isEnabled()) {
            if (!qgetenv("SIMULIDE_UI_CAPTURE").isEmpty()) dock->grab().save(QString::fromUtf8(qgetenv("SIMULIDE_UI_CAPTURE")));
            dock->findChild<QPlainTextEdit*>("aiChallengeAnswer")->setPlainText(QString::fromUtf8("3,75 V; delež spodnjega upora se poveča.")); *step=10; dock->findChild<QPushButton*>("aiChallengeSubmit")->click();
        } else if (*step==10 && dock->findChild<QPushButton*>("aiChallengeSubmit")->isEnabled()) {
            dock->findChild<QPlainTextEdit*>("aiChallengeAnswer")->setPlainText("1"); *step=11; dock->findChild<QPushButton*>("aiChallengeSubmit")->click();
        } else if (*step==11 && !dock->findChild<QPushButton*>("aiChallengeSubmit")->isVisible()) {
            fprintf(stderr,"CLASSROOM PASS: native help, safe experiment copy, prediction and three challenge answers\n"); timer->stop(); std::exit(0);
        }
    }); timer->start(100);
}
