// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "aiassistant.h"
#include "circuit.h"
#include <QDialog>
#include <QComboBox>
#include <QLineEdit>
#include <QLabel>
#include <QPushButton>
#include <QPlainTextEdit>
#include <QMessageBox>
#include <QFileDialog>
#include <QFileInfo>
#include <QTimer>
#include <memory>
#include <cstdlib>
inline void runAiQuizTest(QWidget* window) {
    Circuit::self()->createComponent("Voltage Source","QuizOriginal",QPoint(-100,-100));
    auto* dock=static_cast<AiAssistant*>(window->findChild<QDockWidget*>("AiAssistantDock"));
    if (!dock) { fprintf(stderr,"QUIZ FAIL no dock\n"); std::exit(1); }
    auto stage=std::make_shared<int>(0); auto ticks=std::make_shared<int>(0);
    auto* timer=new QTimer(window);
    const bool resume=!qgetenv("SIMULIDE_QUIZ_RESUME").isEmpty();
    QObject::connect(timer,&QTimer::timeout,window,[dock,stage,ticks,resume] {
        if (++*ticks>350) { fprintf(stderr,"QUIZ FAIL timeout stage=%d\n",*stage); std::exit(1); }
        if (*ticks%30==0) fprintf(stderr,"QUIZ stage=%d status=%s\n",*stage,qPrintable(dock->findChild<QLabel*>("aiStatus")->text()));
        auto* modal=qobject_cast<QDialog*>(QApplication::activeModalWidget());
        auto click=[dock](const char* name) { dock->findChild<QPushButton*>(name)->click(); };
        if (*stage==0) { *stage=1; QTimer::singleShot(0,dock,[click] { click("aiLoginButton"); }); }
        else if (*stage==1 && modal && modal->findChild<QLineEdit*>("aiUsername")) {
            modal->findChild<QLineEdit*>("aiServer")->setText("http://127.0.0.1:8765");
            modal->findChild<QLineEdit*>("aiUsername")->setText("teststudent");
            modal->findChild<QLineEdit*>("aiPassword")->setText("testpass123"); *stage=2; modal->accept();
        } else if (*stage==2 && modal && modal->findChild<QComboBox*>("aiLessonChoice")) {
            modal->findChild<QComboBox*>("aiLessonChoice")->setCurrentIndex(0); *stage=3; modal->accept();
        } else if (*stage==3 && dock->findChild<QPushButton*>("aiQuizButton")->isEnabled()) {
            if (resume) { *stage=9; return; }
            dock->findChild<QPlainTextEdit*>("aiQuestion")->setPlainText(QString::fromUtf8("Neodposlano vprašanje za obnovitev."));
            *stage=4; QTimer::singleShot(0,dock,[click] { click("aiWorkSubmitButton"); });
        } else if (*stage==4 && modal && modal->findChild<QPlainTextEdit*>()) {
            modal->findChild<QPlainTextEdit*>()->setPlainText(QString::fromUtf8("Oddaja iz domačega vmesnika.")); *stage=5; modal->accept();
        } else if (*stage==5 && dock->findChild<QPushButton*>("aiQuizButton")->isEnabled()) {
            *stage=6; QTimer::singleShot(0,dock,[click] { click("aiQuizButton"); });
        } else if (*stage==6 && qobject_cast<QMessageBox*>(modal)) {
            *stage=7; qobject_cast<QMessageBox*>(modal)->button(QMessageBox::Yes)->click();
        } else if (*stage==7 && dock->findChild<QPushButton*>("aiQuizCircuitButton")->isEnabled()) {
            if (dock->findChild<QPushButton*>("aiSendButton")->isEnabled() || dock->findChild<QPushButton*>("aiChallengeHint")->isEnabled()) { fprintf(stderr,"QUIZ FAIL tutor unlocked\n"); std::exit(1); }
            *stage=8; QTimer::singleShot(0,dock,[click] { click("aiQuizCircuitButton"); });
        } else if (*stage==8 && qobject_cast<QFileDialog*>(modal)) {
            auto* dialog=qobject_cast<QFileDialog*>(modal); const QFileInfo target(QString::fromUtf8(qgetenv("SIMULIDE_QUIZ_BACKUP"))); dialog->setDirectory(target.absolutePath()); dialog->selectFile(target.fileName()); *stage=12;
        } else if (*stage==12 && qobject_cast<QFileDialog*>(modal)) {
            auto* dialog=qobject_cast<QFileDialog*>(modal);
            auto* fileName=dialog->findChild<QLineEdit*>("fileNameEdit");
            if (fileName) fileName->setText(QString::fromUtf8(qgetenv("SIMULIDE_QUIZ_BACKUP")));
            fprintf(stderr,"QUIZ save=%s\n",qPrintable(dialog->selectedFiles().join(";"))); *stage=10; QMetaObject::invokeMethod(dialog,"accept",Qt::DirectConnection);
        } else if (*stage==10 && !modal && Circuit::self()->getFilePath().contains("/kviz-") && dock->findChild<QPushButton*>("aiQuizFinishButton")->isEnabled()) {
            dock->findChild<QComboBox*>("aiQuizAnswer0")->setCurrentIndex(1);
            dock->findChild<QPlainTextEdit*>("aiQuizAnswer1")->setPlainText("3,02");
            dock->findChild<QPlainTextEdit*>("aiQuizAnswer2")->setPlainText(QString::fromUtf8("Obnovi ta osnutek."));
            fprintf(stderr,"QUIZ PASS submission, tutor lock and attachment opened; exit before finish to test resume\n"); std::exit(0);
        } else if (*stage==9 && dock->findChild<QPushButton*>("aiQuizFinishButton")->isEnabled()) {
            if (dock->findChild<QComboBox*>("aiQuizAnswer0")->currentIndex()!=1 || dock->findChild<QPlainTextEdit*>("aiQuizAnswer1")->toPlainText()!="3,02" || dock->findChild<QPlainTextEdit*>("aiQuizAnswer2")->toPlainText()!=QString::fromUtf8("Obnovi ta osnutek.")) { fprintf(stderr,"QUIZ FAIL answers not restored after restart\n"); std::exit(1); }
            fprintf(stderr,"QUIZ PASS draft answers restored after process restart\n");
            if (dock->findChild<QPushButton*>("aiSendButton")->isEnabled()) { fprintf(stderr,"QUIZ FAIL resume unlocked\n"); std::exit(1); }
            dock->findChild<QComboBox*>("aiQuizAnswer0")->setCurrentIndex(1);
            dock->findChild<QPlainTextEdit*>("aiQuizAnswer1")->setPlainText("3,02");
            dock->findChild<QPlainTextEdit*>("aiQuizAnswer2")->setPlainText(QString::fromUtf8("Napetost je odvisna od razmerja uporov."));
            if (!qgetenv("SIMULIDE_UI_CAPTURE").isEmpty()) dock->grab().save(QString::fromUtf8(qgetenv("SIMULIDE_UI_CAPTURE")));
            *stage=11; QTimer::singleShot(0,dock,[click] { click("aiQuizFinishButton"); });
        } else if (*stage==11 && dock->findChild<QPushButton*>("aiSendButton")->isEnabled()) {
            if (dock->findChild<QPlainTextEdit*>("aiQuestion")->toPlainText()!=QString::fromUtf8("Neodposlano vprašanje za obnovitev.")) { fprintf(stderr,"QUIZ FAIL chat draft not restored\n"); std::exit(1); }
            fprintf(stderr,"QUIZ PASS lock resumed after restart; answers submitted and tutor unlocked\n"); std::exit(0);
        }
    }); timer->start(100);
}
