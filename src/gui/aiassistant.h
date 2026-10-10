// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QDockWidget>
#include <QJsonObject>
#include <QJsonArray>
#include <QPointer>
#include <functional>
#include <QVector>
class QVBoxLayout;
class QTextEdit;
class QPlainTextEdit;
class QPushButton;
class QLabel;
class QComboBox;
class QNetworkAccessManager;
class QNetworkReply;

class AiAssistant : public QDockWidget {
public:
    explicit AiAssistant(QWidget* parent = nullptr);
private:
    void send();
    void requestHelp();
    void startChallenge();
    void refreshChallenge();
    void refreshWork();
    void showWork(const QJsonObject& state);
    void submitWork();
    void startQuiz();
    void finishQuiz();
    void openQuizCircuit();
    void applyQuizLock();
    QString draftKey(const QString& kind, int id) const;
    void saveQuizDraft();
    void showChallenge(const QJsonObject& state);
    void answerChallenge();
    void hintChallenge();
    bool prepareExperimentCopy();
    void settings();
    void preview();
    void reset();
    void busy(bool active);
    void append(const QString& who, const QString& text);
    void loadLesson();
    void chooseLesson(const QJsonArray& lessons);
    void call(const QString& path, const QJsonObject& payload,
              std::function<void(const QJsonObject&, int)> done);
    QTextEdit* transcript;
    QPlainTextEdit* question;
    QPushButton *sendButton, *cancelButton, *settingsButton, *newButton, *previewButton, *taskButton;
    QLabel *status, *lessonLabel, *draftLabel;
    QWidget* challengePanel;
    QLabel *challengeTitle, *challengePrompt, *challengeFeedback;
    QComboBox* challengeChoices;
    QPlainTextEdit* challengeAnswer;
    QPushButton *helpButton, *challengeButton, *challengeSubmit, *challengeHint;
    int challengeId = 0, challengeStep = 0;
    bool challengeComplete = false, challengeEnabled = false;
    QString helpRequestId, helpReason, experimentPath;
    QJsonObject helpSnapshot;
    QWidget *quizPanel, *quizContent;
    QVBoxLayout* quizLayout;
    QLabel* quizTitle;
    QPushButton *workButton, *quizButton, *quizFinish, *quizCircuit;
    QVector<QWidget*> quizAnswers;
    QJsonArray quizQuestions;
    int quizAttemptId = 0, quizLessonId = 0;
    bool quizLocked = false, quizAvailable = false, quizHasCircuit = false;
    QString workRequestId, workComment, workCircuit;
    QJsonObject workSnapshot;
    QNetworkAccessManager* network;
    QPointer<QNetworkReply> reply;
    QString server, username, token, requestId, retryQuestion;
    QString taskInstructions, taskObjectives;
    QJsonObject retrySnapshot;
    int lessonId = 0;
    bool lessonOpen = false;
};
