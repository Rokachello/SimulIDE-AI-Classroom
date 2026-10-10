// SPDX-License-Identifier: GPL-3.0-or-later
#include "aiassistant.h"
#include "aicontext.h"
#include "circuit.h"
#include "circuitwidget.h"
#include "airender.h"
#include <QTextBrowser>
#include <QScrollBar>
#include <QTextEdit>
#include <QPlainTextEdit>
#include <QLineEdit>
#include <QPushButton>
#include <QLabel>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QFormLayout>
#include <QDialog>
#include <QDialogButtonBox>
#include <QComboBox>
#include <QSettings>
#include <QNetworkAccessManager>
#include <QNetworkRequest>
#include <QNetworkReply>
#include <QHostAddress>
#include <QTimer>
#include <QCheckBox>
#include <QShortcut>
#include <QSizePolicy>
#include <QUuid>
#include <QJsonArray>
#include <QJsonDocument>
#include <QFile>
#include <QCoreApplication>
#include <QInputDialog>
#include <QFileDialog>
#include <QFileInfo>
#include <QSaveFile>
#include <QScrollArea>
#include <QMessageBox>
#include <QDir>
#include <QCryptographicHash>
#include <QSignalBlocker>

static QVariant savedDraft(const QString& key) {
    QSettings cfg(QSettings::IniFormat,QSettings::UserScope,"SimulIDE","ClassroomDrafts");
    return cfg.value(key);
}

AiAssistant::AiAssistant(QWidget* parent) : QDockWidget(QString::fromUtf8("AI asistent · V0.12"), parent) {
    setObjectName("AiAssistantDock"); setMinimumWidth(340);
    QSettings cfg;
    server = cfg.value("AiClassroom/server", "http://127.0.0.1:8765").toString();
    username = cfg.value("AiClassroom/username").toString();
    // Portable classroom configuration contains only a public server address.
    QFile file(QCoreApplication::applicationDirPath()+"/classroom.json");
    if (file.open(QIODevice::ReadOnly)) {
        QString bundled = QJsonDocument::fromJson(file.readAll()).object().value("server_url").toString();
        if (!bundled.isEmpty()) server = bundled;
    }
    auto* body = new QWidget(this); auto* layout = new QVBoxLayout(body); layout->setContentsMargins(10,10,10,10); layout->setSpacing(8);
    body->setStyleSheet("QPushButton { padding: 7px 10px; border: 1px solid #bac8d6; border-radius: 5px; background: #f7f9fc; color: #22354a; } QPushButton:hover { background: #e9f0f8; } QPushButton:disabled { color: #8392a2; background: #f2f4f6; } QPlainTextEdit { background: white; color: #182c40; border: 1px solid #bac8d6; border-radius: 5px; padding: 5px; }");
    auto* top = new QHBoxLayout;
    settingsButton = new QPushButton(QString::fromUtf8("Prijava / ura")); settingsButton->setObjectName("aiLoginButton");
    taskButton = new QPushButton(QString::fromUtf8("Naloga")); taskButton->setObjectName("aiTaskButton"); taskButton->setEnabled(false);
    connect(taskButton,&QPushButton::clicked,this,[this] {
        QDialog dlg(this); dlg.setWindowTitle(QString::fromUtf8("Moja naloga")); dlg.resize(520,420);
        auto* content=new QVBoxLayout(&dlg); auto* text=new QPlainTextEdit; text->setReadOnly(true);
        text->setPlainText(QString::fromUtf8("UČNI CILJI\n")+taskObjectives+QString::fromUtf8("\n\nNALOGA\n")+taskInstructions); content->addWidget(text);
        auto* buttons=new QDialogButtonBox(QDialogButtonBox::Close); content->addWidget(buttons); connect(buttons,&QDialogButtonBox::rejected,&dlg,&QDialog::reject); dlg.exec();
    });
    previewButton = new QPushButton(QString::fromUtf8("Kontekst"));
    newButton = new QPushButton(QString::fromUtf8("Osveži pogovor"));
    auto* moreButton = new QPushButton(QString::fromUtf8("Možnosti ▾")); moreButton->setObjectName("aiOptionsButton"); moreButton->setCheckable(true);
    top->addWidget(settingsButton); top->addWidget(taskButton); top->addStretch(); top->addWidget(moreButton); layout->addLayout(top);
    lessonLabel = new QLabel(QString::fromUtf8("Ni prijave. Izberi Prijava / ura.")); lessonLabel->setWordWrap(true); layout->addWidget(lessonLabel);
    auto* advanced = new QWidget; advanced->setObjectName("aiOptionsPanel");
    auto* advancedLayout = new QVBoxLayout(advanced); advancedLayout->setContentsMargins(0,0,0,0);
    auto* contextActions = new QHBoxLayout; contextActions->addWidget(previewButton); contextActions->addWidget(newButton); advancedLayout->addLayout(contextActions);
    auto* advancedScroll = new QScrollArea; advancedScroll->setWidgetResizable(true); advancedScroll->setMaximumHeight(175); advancedScroll->setWidget(advanced);
    layout->addWidget(advancedScroll); advancedScroll->hide();
    connect(moreButton, &QPushButton::toggled, advancedScroll, &QWidget::setVisible);
    auto* note = new QLabel(QString::fromUtf8("Vprašanje in trenutno vezje se shranita na učiteljevem strežniku ter pošljeta OpenAI. Učitelj lahko pregleda pogovor."));
    note->setWordWrap(true); advancedLayout->addWidget(note);
    auto* timelineToggle = new QCheckBox(QString::fromUtf8("Zajemaj časovni potek (zadnjih 100 vzorcev)"));
    timelineToggle->setObjectName("aiTimelineToggle");
    timelineToggle->setChecked(cfg.value("AiClassroom/timeline", true).toBool());
    setAiTimelineEnabled(timelineToggle->isChecked()); advancedLayout->addWidget(timelineToggle);
    auto* timelineInfo = new QLabel; timelineInfo->setWordWrap(true); advancedLayout->addWidget(timelineInfo);
    auto* timelineTimer = new QTimer(this); timelineTimer->setInterval(200);
    connect(timelineToggle, &QCheckBox::toggled, this, [](bool enabled) {
        setAiTimelineEnabled(enabled); QSettings().setValue("AiClassroom/timeline", enabled);
    });
    connect(timelineTimer, &QTimer::timeout, this, [timelineToggle, timelineInfo] {
        if (!timelineToggle->isChecked()) { timelineInfo->setText(QString::fromUtf8("Časovni potek je izključen.")); return; }
        const auto snapshot = captureAiContext();
        if (snapshot.contains("error")) { timelineInfo->setText(QString::fromUtf8("Zajem čaka na konec urejanja vezja.")); return; }
        const auto trace = snapshot["simulation"].toObject()["timeline"].toObject();
        auto samples = trace["samples"].toArray();
        double span = samples.size() > 1 ? samples.last().toObject()["time_s"].toDouble() - samples.first().toObject()["time_s"].toDouble() : 0;
        timelineInfo->setText(QString::fromUtf8("Potek: %1 vzorcev · %2 signalov · %3 s simulacije. Hitri prehodi so lahko izpuščeni.")
            .arg(samples.size()).arg(trace["channels"].toArray().size()).arg(span, 0, 'g', 4));
    });
    timelineTimer->start();
    auto* browser = new QTextBrowser; browser->setOpenLinks(false); browser->setOpenExternalLinks(false);
    transcript = browser; transcript->setDocument(new AiRender::Document); transcript->document()->setParent(transcript);
    transcript->setFont(QFont("Segoe UI", 11)); transcript->document()->setDocumentMargin(12);
    transcript->setStyleSheet("QTextEdit { background: #ffffff; color: #182c40; border: 1px solid #cbd5df; border-radius: 6px; }");
    transcript->setMinimumHeight(120);
    transcript->setReadOnly(true); transcript->setObjectName("aiTranscript"); layout->addWidget(transcript, 1);
    question = new QPlainTextEdit; question->setObjectName("aiQuestion"); question->setMaximumHeight(95); question->setMinimumHeight(65); question->setFont(QFont("Segoe UI",11));
    question->setPlaceholderText(QString::fromUtf8("Vprašaj o vezju ali simulaciji …")); layout->addWidget(question);
    draftLabel=new QLabel; draftLabel->setObjectName("aiDraftStatus"); draftLabel->setWordWrap(true); layout->addWidget(draftLabel);
    draftLabel->setStyleSheet("color: #52657b; font-size: 11px;");
    connect(question,&QPlainTextEdit::textChanged,this,[this] {
        if (lessonId<=0 || token.isEmpty()) return;
        QSettings cfg(QSettings::IniFormat,QSettings::UserScope,"SimulIDE","ClassroomDrafts"); cfg.setValue(draftKey("chat",lessonId),question->toPlainText()); cfg.sync();
        draftLabel->setText(cfg.status()!=QSettings::NoError?QString::fromUtf8("Osnutka ni mogoče shraniti na ta računalnik."):question->toPlainText().isEmpty()?QString():QString::fromUtf8("Osnutek je shranjen na tem računalniku; še ni poslan."));
    });
    auto* actions = new QHBoxLayout;
    sendButton = new QPushButton(QString::fromUtf8("Pošlji")); sendButton->setObjectName("aiSendButton");
    cancelButton = new QPushButton(QString::fromUtf8("Prekini")); cancelButton->setEnabled(false);
    sendButton->setToolTip(QString::fromUtf8("Pošlje vprašanje, trenutno vezje in zajeti časovni potek. Bližnjica: Ctrl+Enter."));
    sendButton->setStyleSheet("QPushButton { background: #1760ab; color: white; border: 1px solid #1760ab; font-weight: bold; } QPushButton:disabled { background: #d9e3ef; color: #677d95; }");
    auto* sendShortcut = new QShortcut(QKeySequence("Ctrl+Return"), body); sendShortcut->setContext(Qt::WidgetWithChildrenShortcut);
    connect(sendShortcut, &QShortcut::activated, this, [this] { if (sendButton->isEnabled() && question->isVisible()) send(); });
    actions->addWidget(sendButton, 1); actions->addWidget(cancelButton); layout->addLayout(actions);
    auto* learningActions = new QHBoxLayout;
    helpButton = new QPushButton(QString::fromUtf8("Potrebujem učitelja")); helpButton->setObjectName("aiHelpButton");
    challengeButton = new QPushButton(QString::fromUtf8("Izziv")); challengeButton->setObjectName("aiChallengeButton"); challengeButton->setEnabled(false);
    learningActions->addWidget(helpButton); layout->addLayout(learningActions);
    auto* workActions = new QHBoxLayout;
    workButton = new QPushButton(QString::fromUtf8("Oddaj nalogo")); workButton->setObjectName("aiWorkSubmitButton");
    quizButton = new QPushButton(QString::fromUtf8("Končni kviz")); quizButton->setObjectName("aiQuizButton");
    learningActions->addWidget(challengeButton); challengeButton->hide();
    challengeButton->setToolTip(QString::fromUtf8("Zaključni izziv, ki ga je omogočil učitelj."));
    workActions->addWidget(workButton); workActions->addWidget(quizButton); layout->addLayout(workActions);
    auto* quizScroll = new QScrollArea; quizScroll->setWidgetResizable(true); quizScroll->setMinimumHeight(220);
    quizPanel=quizScroll; quizPanel->setObjectName("aiQuizPanel");
    quizContent=new QWidget; quizScroll->setWidget(quizContent); quizLayout=new QVBoxLayout(quizContent);
    quizLayout->setSizeConstraint(QLayout::SetMinimumSize);
    quizTitle=new QLabel; quizTitle->setObjectName("aiQuizTitle"); quizTitle->setWordWrap(true); quizTitle->setTextFormat(Qt::PlainText); quizLayout->addWidget(quizTitle);
    quizCircuit=new QPushButton(QString::fromUtf8("Odpri vezje kviza")); quizCircuit->setObjectName("aiQuizCircuitButton"); quizLayout->addWidget(quizCircuit);
    quizFinish=new QPushButton(QString::fromUtf8("Oddaj kviz + zajemi vezje")); quizFinish->setObjectName("aiQuizFinishButton"); quizLayout->addWidget(quizFinish);
    layout->addWidget(quizPanel,1); quizPanel->hide();
    auto* challengeScroll = new QScrollArea; challengeScroll->setWidgetResizable(true); challengeScroll->setMinimumHeight(220); challengeScroll->setMaximumHeight(340);
    challengePanel = challengeScroll; challengePanel->setObjectName("aiChallengePanel");
    auto* challengeContent = new QWidget; challengeScroll->setWidget(challengeContent);
    auto* challengeLayout = new QVBoxLayout(challengeContent); challengeLayout->setSizeConstraint(QLayout::SetMinimumSize); challengeLayout->setContentsMargins(8,8,8,8);
    challengeTitle = new QLabel; challengeTitle->setTextFormat(Qt::PlainText);
    challengePrompt = new QLabel; challengePrompt->setWordWrap(true); challengePrompt->setTextFormat(Qt::PlainText);
    challengeChoices = new QComboBox; challengeChoices->setObjectName("aiChallengeChoices");
    challengeAnswer = new QPlainTextEdit; challengeAnswer->setObjectName("aiChallengeAnswer"); challengeAnswer->setMaximumHeight(75);
    challengeAnswer->setPlaceholderText(QString::fromUtf8("Tvoj odgovor oziroma meritev in pojasnilo …"));
    challengeFeedback = new QLabel; challengeFeedback->setTextFormat(Qt::PlainText); challengeFeedback->setWordWrap(true);
    auto* challengeActions = new QHBoxLayout;
    challengeSubmit = new QPushButton(QString::fromUtf8("Oddaj odgovor + zajemi vezje")); challengeSubmit->setObjectName("aiChallengeSubmit");
    challengeHint = new QPushButton(QString::fromUtf8("Namig")); challengeHint->setObjectName("aiChallengeHint");
    challengeActions->addWidget(challengeSubmit); challengeActions->addWidget(challengeHint);
    challengeLayout->addWidget(challengeTitle); challengeLayout->addWidget(challengePrompt); challengeLayout->addWidget(challengeChoices);
    challengeLayout->addWidget(challengeAnswer); challengeLayout->addLayout(challengeActions); challengeLayout->addWidget(challengeFeedback);
    layout->addWidget(challengePanel); challengePanel->hide();
    status = new QLabel; status->setObjectName("aiStatus"); status->setWordWrap(true); layout->addWidget(status);
    status->setTextFormat(Qt::PlainText); lessonLabel->setTextFormat(Qt::PlainText);
    setWidget(body); network = new QNetworkAccessManager(this);
    connect(workButton, &QPushButton::clicked, this, [this] { submitWork(); });
    connect(quizButton, &QPushButton::clicked, this, [this] { startQuiz(); });
    connect(quizCircuit, &QPushButton::clicked, this, [this] { openQuizCircuit(); });
    connect(quizFinish, &QPushButton::clicked, this, [this] { finishQuiz(); });
    connect(helpButton, &QPushButton::clicked, this, [this] { requestHelp(); });
    connect(challengeButton, &QPushButton::clicked, this, [this] { startChallenge(); });
    connect(challengeSubmit, &QPushButton::clicked, this, [this] { answerChallenge(); });
    connect(challengeHint, &QPushButton::clicked, this, [this] { hintChallenge(); });
    connect(sendButton, &QPushButton::clicked, this, [this] { send(); });
    connect(settingsButton, &QPushButton::clicked, this, [this] { settings(); });
    connect(previewButton, &QPushButton::clicked, this, [this] { preview(); });
    connect(newButton, &QPushButton::clicked, this, [this] { loadLesson(); });
    connect(cancelButton, &QPushButton::clicked, this, [this] { if (reply) reply->abort(); });
    status->setText(QString::fromUtf8("Prijavi se z računom, ki ti ga je pripravil učitelj."));
    append(QString::fromUtf8("Dobrodošel"), QString::fromUtf8("1. Klikni Prijava / ura.\n2. Izberi svojo učno uro.\n3. Sestavi vezje in vprašaj asistenta.\n\nOb vprašanju se priloži trenutno vezje. Pogovor lahko pregleda učitelj."));
    busy(false);
}
void AiAssistant::reset() {
    taskInstructions.clear(); taskObjectives.clear(); taskButton->setEnabled(false);
    draftLabel->clear();
    quizLocked=false; quizAttemptId=0; quizLessonId=0; quizAvailable=false; quizHasCircuit=false; quizPanel->hide();
    workRequestId.clear(); workSnapshot=QJsonObject(); workCircuit.clear(); workComment.clear();
    workButton->setEnabled(false); quizButton->setEnabled(false);
    challengeId=0; challengeStep=0; challengeComplete=false; challengeEnabled=false; challengeButton->setEnabled(false); challengePanel->hide(); challengeAnswer->clear(); experimentPath.clear();
    helpRequestId.clear(); helpReason.clear(); helpSnapshot=QJsonObject();
    transcript->show(); question->show(); sendButton->show(); cancelButton->show();
    auto* doc = new AiRender::Document; doc->setParent(transcript); doc->setDefaultFont(transcript->font()); doc->setDocumentMargin(12);
    auto* old = transcript->document(); transcript->setDocument(doc); delete old; requestId.clear(); retryQuestion.clear(); retrySnapshot = QJsonObject();
}
void AiAssistant::busy(bool active) {
    taskButton->setEnabled(!active && !quizLocked && !token.isEmpty() && lessonId>0);
    helpButton->setEnabled(!active && !token.isEmpty() && (lessonOpen || quizLocked));
    challengeButton->setVisible(challengeEnabled && !quizLocked);
    challengeButton->setEnabled(!active && challengeEnabled && !quizLocked);
    workButton->setEnabled(!active && lessonOpen && !quizLocked && !token.isEmpty());
    quizButton->setEnabled(!active && !token.isEmpty() && (quizLocked || (quizAvailable && lessonOpen)));
    quizFinish->setEnabled(!active && quizLocked && quizAttemptId>0);
    quizCircuit->setEnabled(!active && quizLocked && quizHasCircuit);
    for (auto* field : quizAnswers) field->setEnabled(!active);
    challengeSubmit->setEnabled(!active && !challengeComplete && !quizLocked); challengeHint->setEnabled(!active && !challengeComplete && !quizLocked);
    challengeAnswer->setEnabled(!active); challengeChoices->setEnabled(!active);
    sendButton->setEnabled(!active && !quizLocked && !token.isEmpty() && lessonOpen);
    question->setEnabled(!active && !quizLocked && !token.isEmpty() && lessonOpen);
    cancelButton->setVisible(active && !quizLocked && !challengePanel->isVisible());
    settingsButton->setEnabled(!active && !quizLocked); newButton->setEnabled(!active && !token.isEmpty());
    previewButton->setEnabled(!active); cancelButton->setEnabled(active);
}
void AiAssistant::append(const QString& who, const QString& text) {
    QTextCursor cursor(transcript->document()); cursor.movePosition(QTextCursor::End);
    cursor.insertHtml(AiRender::message(who,text,transcript->document()));
    transcript->verticalScrollBar()->setValue(transcript->verticalScrollBar()->maximum());
}
void AiAssistant::call(const QString& path, const QJsonObject& payload, std::function<void(const QJsonObject&, int)> done) {
    if (reply) return;
    QNetworkRequest req(QUrl(server+path));
    req.setHeader(QNetworkRequest::ContentTypeHeader,"application/json");
    req.setAttribute(QNetworkRequest::RedirectPolicyAttribute,QNetworkRequest::ManualRedirectPolicy);
    if (!token.isEmpty()) req.setRawHeader("Authorization","Bearer "+token.toUtf8());
    auto* pending = network->post(req,QJsonDocument(payload).toJson(QJsonDocument::Compact)); reply = pending; busy(true);
    auto* timeout = new QTimer(pending); timeout->setSingleShot(true); timeout->start(170000);
    connect(timeout,&QTimer::timeout,pending,[pending] { pending->abort(); });
    connect(pending,&QNetworkReply::finished,this,[this,pending,done] {
        int code = pending->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        const QByteArray bytes = pending->readAll();
        QJsonParseError parse; auto doc = QJsonDocument::fromJson(bytes,&parse);
        QJsonObject obj = doc.object();
        if (pending->error()!=QNetworkReply::NoError || code<200 || code>=300) {
            if (!obj.contains("error")) obj["error"] = QString::fromUtf8("Spojitev ni uspela (HTTP %1): %2").arg(code).arg(pending->errorString());
        } else if (parse.error!=QJsonParseError::NoError || !doc.isObject()) {
            obj["error"] = QString::fromUtf8("Strežnik ni vrnil veljavnega odgovora JSON."); code = 0;
        }
        pending->deleteLater(); reply = nullptr; busy(false);
        if (code==401) { token.clear(); lessonId=0; lessonOpen=false; challengePanel->hide(); lessonLabel->setText(QString::fromUtf8("Prijava je potekla.")); }
        done(obj,code);
    });
}
static bool permittedServer(const QUrl& url) {
    if (!url.isValid() || url.host().isEmpty() || !url.userInfo().isEmpty() || url.hasQuery() || url.hasFragment() || (url.path()!="" && url.path()!="/")) return false;
    if (url.scheme()=="https") return true;
    if (url.scheme()!="http") return false;
    QHostAddress address(url.host());
    return url.host()=="localhost" || address.isLoopback();
}
void AiAssistant::settings() {
    if (quizLocked && !token.isEmpty()) { status->setText(QString::fromUtf8("Najprej oddaj začeti kviz. Med kvizom pomoč asistenta in menjava ure nista na voljo.")); return; }
    QDialog dlg(this); dlg.setWindowTitle(QString::fromUtf8("Prijava v učilnico")); dlg.resize(540,300);
    auto* form = new QFormLayout(&dlg);
    auto* serverEdit = new QLineEdit(server); serverEdit->setObjectName("aiServer");
    auto* userEdit = new QLineEdit(username); userEdit->setObjectName("aiUsername");
    auto* password = new QLineEdit; password->setObjectName("aiPassword"); password->setEchoMode(QLineEdit::Password); password->setMaxLength(256);
    form->addRow(QString::fromUtf8("Uporabniško ime"),userEdit); form->addRow(QString::fromUtf8("Geslo študenta"),password);
    auto* showPassword = new QCheckBox(QString::fromUtf8("Pokaži geslo")); form->addRow(showPassword);
    connect(showPassword, &QCheckBox::toggled, password, [password](bool show) { password->setEchoMode(show?QLineEdit::Normal:QLineEdit::Password); });
    auto* connection = new QPushButton(QString::fromUtf8("Nastavitve povezave ▾")); connection->setCheckable(true); form->addRow(connection);
    form->addRow(QString::fromUtf8("Naslov strežnika"),serverEdit);
    auto* serverCaption = form->labelForField(serverEdit); serverEdit->hide(); serverCaption->hide();
    connect(connection, &QPushButton::toggled, serverEdit, &QWidget::setVisible);
    connect(connection, &QPushButton::toggled, serverCaption, &QWidget::setVisible);
    userEdit->setFocus();
    auto* note = new QLabel(QString::fromUtf8("Uporabi uporabniško ime in geslo, ki ti ju je dal učitelj. Ob ponovnem zagonu se prijaviš znova; shranjeni pogovori te čakajo pri izbrani uri.")); note->setWordWrap(true); form->addRow(note);
    if (!token.isEmpty()) {
        auto* change = new QPushButton(QString::fromUtf8("Izberi drugo uro brez nove prijave")); form->addRow(change);
        connect(change,&QPushButton::clicked,&dlg,[this,&dlg] {
            dlg.reject();
            call("/api/lessons",{},[this](const QJsonObject& obj,int code) {
                if (code!=200 || obj.contains("error")) { status->setText(obj.value("error").toString()); return; }
                chooseLesson(obj.value("lessons").toArray());
            });
        });
        auto* signout = new QPushButton(QString::fromUtf8("Odjava")); form->addRow(signout);
        connect(signout,&QPushButton::clicked,&dlg,[this,&dlg] {
            dlg.reject();
            call("/api/logout",{},[this](const QJsonObject&,int) {
                token.clear(); lessonId=0; lessonOpen=false; reset(); question->clear();
                lessonLabel->setText(QString::fromUtf8("Odjavljen.")); status->setText(QString::fromUtf8("Za nadaljevanje se prijavi."));
            });
        });
    }
    auto* buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel); form->addRow(buttons);
    buttons->button(QDialogButtonBox::Ok)->setText(QString::fromUtf8("Prijava")); buttons->button(QDialogButtonBox::Cancel)->setText(QString::fromUtf8("Prekliči"));
    connect(buttons,&QDialogButtonBox::accepted,&dlg,&QDialog::accept); connect(buttons,&QDialogButtonBox::rejected,&dlg,&QDialog::reject);
    if (dlg.exec()!=QDialog::Accepted) return;
    QString candidate = serverEdit->text().trimmed(); while (candidate.endsWith('/')) candidate.chop(1);
    if (!permittedServer(QUrl(candidate))) { status->setText(QString::fromUtf8("Vnesi naslov HTTPS ali za lokalni preizkus http://127.0.0.1:8765.")); return; }
    server=candidate; username=userEdit->text().trimmed(); token.clear(); lessonId=0; lessonOpen=false; reset(); question->clear();
    status->setText(QString::fromUtf8("Prijavljam …")); lessonLabel->setText(QString::fromUtf8("Prijavljam …"));
    call("/api/login",{{"username",username},{"password",password->text()}},[this](const QJsonObject& obj,int code) {
        if (code!=200 || obj.contains("error")) { status->setText(obj.value("error").toString()); lessonLabel->setText(QString::fromUtf8("Ni prijave.")); return; }
        token=obj.value("token").toString(); QSettings cfg; cfg.setValue("AiClassroom/server",server); cfg.setValue("AiClassroom/username",username);
        chooseLesson(obj.value("lessons").toArray());
    });
}
void AiAssistant::chooseLesson(const QJsonArray& lessons) {
    if (quizLocked && !token.isEmpty()) { refreshWork(); return; }
    if (lessons.isEmpty()) { status->setText(QString::fromUtf8("Učitelj mora najprej ustvariti uro.")); return; }
    QDialog dlg(this); dlg.setWindowTitle(QString::fromUtf8("Izberi učno uro")); dlg.resize(570,160);
    auto* layout = new QVBoxLayout(&dlg); auto* combo = new QComboBox; combo->setObjectName("aiLessonChoice");
    for (const auto& v : lessons) { const auto l=v.toObject(); combo->addItem(QString("#%1 · %2 · %3 · %4%5").arg(l.value("id").toInt()).arg(l.value("title").toString(),l.value("lesson_date").toString(),l.value("group_name").toString(),l.value("active").toInt()?"":QString::fromUtf8(" [zaključena]")),l.value("id").toInt()); }
    layout->addWidget(combo); auto* buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel); layout->addWidget(buttons);
    connect(buttons,&QDialogButtonBox::accepted,&dlg,&QDialog::accept); connect(buttons,&QDialogButtonBox::rejected,&dlg,&QDialog::reject);
    if (dlg.exec()!=QDialog::Accepted) { status->setText(QString::fromUtf8("Ura ni izbrana. Ponovno odpri Prijava / ura.")); return; }
    if (lessonId!=combo->currentData().toInt()) { reset(); QSignalBlocker blocked(question); question->clear(); }
    lessonId=combo->currentData().toInt(); loadLesson();
}
void AiAssistant::loadLesson() {
    if (token.isEmpty() || !lessonId) { status->setText(QString::fromUtf8("Najprej se prijavi in izberi uro.")); return; }
    quizLocked=true; applyQuizLock();
    status->setText(QString::fromUtf8("Nalagam shranjeni pogovor …"));
    call("/api/select",{{"lesson_id",lessonId}},[this](const QJsonObject& obj,int code) {
        if (code!=200 || obj.contains("error")) { status->setText(obj.value("error").toString()); return; }
        // Refresh must retain the request ID for a cancelled or disconnected send.
        transcript->clear(); auto l=obj.value("lesson").toObject(); lessonOpen=l.value("active").toInt()!=0;
        taskInstructions=obj.value("instructions").toString(); taskObjectives=obj.value("objectives").toString();
        challengeEnabled=lessonOpen && l.value("challenge_mode").toString("off")!="off"; challengeButton->setEnabled(challengeEnabled);
        lessonLabel->setText(QString("%1 · #%2 %3 · %4 · %5").arg(username).arg(lessonId).arg(l.value("title").toString(),l.value("lesson_date").toString(),lessonOpen?QString::fromUtf8("odprta"):QString::fromUtf8("zaključena")));
        if (!obj.value("objectives").toString().isEmpty()) append(QString::fromUtf8("Učni cilji"),obj.value("objectives").toString());
        if (!obj.value("instructions").toString().isEmpty()) append(QString::fromUtf8("Naloga"),obj.value("instructions").toString());
        for (const auto& v : obj.value("history").toArray()) { auto h=v.toObject(); append(QString::fromUtf8("Ti"),h.value("question").toString()); if (h.value("status").toString()=="pending") append("Status",QString::fromUtf8("Zahteva še teče ali je bila prekinjena.")); else append(h.value("status").toString()=="complete"?QString::fromUtf8("Asistent"):"Status",h.value("answer").toString()); }
        status->setText(QString::fromUtf8("Pogovor je shranjen pri tej uri. Vsako vprašanje zajame trenutno vezje."));
        if (question->toPlainText().isEmpty()) {
            const QString draft=savedDraft(draftKey("chat",lessonId)).toString();
            if (!draft.isEmpty()) question->setPlainText(draft);
        }
        refreshChallenge();
    });
}
void AiAssistant::preview() {
    QDialog dlg(this); dlg.setWindowTitle(QString::fromUtf8("Trenutni posnetek vezja")); dlg.resize(760,600);
    auto* layout = new QVBoxLayout(&dlg); auto* text = new QPlainTextEdit(QString::fromUtf8(QJsonDocument(captureAiContext()).toJson(QJsonDocument::Indented)));
    text->setReadOnly(true); layout->addWidget(text); auto* buttons = new QDialogButtonBox(QDialogButtonBox::Close); layout->addWidget(buttons);
    connect(buttons,&QDialogButtonBox::rejected,&dlg,&QDialog::reject); dlg.exec();
}
void AiAssistant::send() {
    if (reply || quizLocked) return;
    const QString q=question->toPlainText().trimmed(); if (q.isEmpty()) return;
    if (token.isEmpty() || !lessonId) { status->setText(QString::fromUtf8("Najprej se prijavi in izberi uro.")); return; }
    if (!lessonOpen) { status->setText(QString::fromUtf8("Ta ura je zaključena. Učitelj jo lahko ponovno odpre.")); return; }
    // A retry after interruption uses exactly the same ID and snapshot. The server deduplicates it.
    if (requestId.isEmpty() || q!=retryQuestion) {
        auto snapshot=captureAiContext(); if (snapshot.contains("error")) { status->setText(snapshot.value("error").toString()); return; }
        if (QJsonDocument(snapshot).toJson().size()>512000 || q.toUtf8().size()>24000) { status->setText(QString::fromUtf8("Vezje ali vprašanje je preveliko.")); return; }
        retrySnapshot=snapshot; retryQuestion=q; requestId=QUuid::createUuid().toString(QUuid::WithoutBraces);
    }
    status->setText(QString::fromUtf8("Čakam na odgovor … simulacija se lahko nadaljuje."));
    call("/api/chat",{{"lesson_id",lessonId},{"question",q},{"snapshot",retrySnapshot},{"request_id",requestId}},[this,q](const QJsonObject& obj,int code) {
        if (code!=200 || obj.contains("error")) {
            QString message=obj.value("error").toString();
            if (code==0 || obj.value("retry_same").toBool() || (code>=500 && !obj.contains("retry_same"))) message+=QString::fromUtf8("\nStrežnik lahko še obdeluje vprašanje. Pusti besedilo enako in znova pritisni Pošlji za preverjanje iste zahteve.");
            else requestId.clear();
            status->setText(message); if (code==423) refreshWork(); return;
        }
        append(QString::fromUtf8("Ti"),q); append(QString::fromUtf8("Asistent"),obj.value("answer").toString());
        requestId.clear(); retryQuestion.clear(); retrySnapshot=QJsonObject(); question->clear();
        status->setText(QString::fromUtf8("Odgovor in posnetek vezja sta shranjena pri tej uri."));
    });
}

void AiAssistant::requestHelp() {
    if (reply) return;
    if (token.isEmpty() || !lessonId || (!lessonOpen && !quizLocked)) { status->setText(QString::fromUtf8("Za pomoč izberi odprto učno uro.")); return; }
    bool ok=false;
    const QString reason=QInputDialog::getMultiLineText(this,QString::fromUtf8("Potrebujem učitelja"),QString::fromUtf8("Kje se je ustavilo? Npr. ne razumem naloge ali vezje ne deluje."),helpReason,&ok).trimmed();
    if (!ok || reason.isEmpty()) return;
    if (reason.toUtf8().size()>4000) { status->setText(QString::fromUtf8("Razlog skrajšaj na nekaj stavkov.")); return; }
    if (helpRequestId.isEmpty() || reason!=helpReason) {
        helpSnapshot=captureAiContext(); if (helpSnapshot.contains("error")) { status->setText(helpSnapshot.value("error").toString()); return; }
        helpReason=reason; helpRequestId=QUuid::createUuid().toString(QUuid::WithoutBraces);
    }
    call("/api/help",{{"lesson_id",quizLocked && quizLessonId?quizLessonId:lessonId},{"request_id",helpRequestId},{"reason",helpReason},{"snapshot",helpSnapshot}},[this](const QJsonObject& obj,int code) {
        if (code!=200 || obj.contains("error")) { status->setText(obj.value("error").toString()+QString::fromUtf8(" Ponovni klik z enakim razlogom preveri isto prošnjo.")); return; }
        status->setText(obj.value("message").toString(QString::fromUtf8("Prošnja je shranjena v učiteljevem pregledu. Med čakanjem lahko nadaljuješ.")));
        helpRequestId.clear(); helpReason.clear(); helpSnapshot=QJsonObject();
    });
}
bool AiAssistant::prepareExperimentCopy() {
    if (!experimentPath.isEmpty() && Circuit::self()->getFilePath()==experimentPath) return true;
    QString path=QFileDialog::getSaveFileName(this,QString::fromUtf8("Shrani prvotno vajo pred izzivom"),Circuit::self()->getFilePath(),QString::fromUtf8("Vezje SimulIDE (*.sim2)"));
    if (path.isEmpty()) return false;
    if (!path.endsWith(".sim2",Qt::CaseInsensitive)) path+=".sim2";
    const QByteArray bytes=Circuit::self()->circuitToString().toUtf8();
    QSaveFile original(path);
    if (!original.open(QIODevice::WriteOnly) || original.write(bytes)!=bytes.size() || !original.commit()) {
        status->setText(QString::fromUtf8("Prvotnega vezja ni mogoče shraniti. Izberi drugo mesto.")); return false;
    }
    const QFileInfo info(path);
    const QString copy=info.absolutePath()+"/"+info.completeBaseName()+"-izziv-"+QUuid::createUuid().toString(QUuid::WithoutBraces).left(8)+".sim2";
    CircuitWidget::self()->saveCirc(copy);
    if (Circuit::self()->getFilePath()!=copy || !QFile::exists(copy)) {
        status->setText(QString::fromUtf8("Prvotna vaja je shranjena, kopije za izziv pa ni bilo mogoče ustvariti.")); return false;
    }
    experimentPath=copy;
    status->setText(QString::fromUtf8("Prvotna vaja je shranjena. Delaš v kopiji za izziv: %1").arg(QFileInfo(copy).fileName()));
    status->setToolTip(QString::fromUtf8("Prvotna vaja: %1\nKopija: %2").arg(path,copy));
    return true;
}
void AiAssistant::startChallenge() {
    if (reply || quizLocked) return;
    if (token.isEmpty() || !lessonId || !lessonOpen) { status->setText(QString::fromUtf8("Za izziv izberi odprto učno uro.")); return; }
    if (!challengeEnabled) { status->setText(QString::fromUtf8("Učitelj za to uro še ni omogočil izzivov.")); return; }
    if (challengeId && !challengeComplete) {
        const bool show=!challengePanel->isVisible(); challengePanel->setVisible(show);
        challengeButton->setText(show?QString::fromUtf8("Skrij izziv"):QString::fromUtf8("Izziv"));
        transcript->setVisible(!show); question->setVisible(!show); sendButton->setVisible(!show); cancelButton->setVisible(!show); return;
    }
    if (!prepareExperimentCopy()) return;
    auto snapshot=captureAiContext(); if (snapshot.contains("error")) { status->setText(snapshot.value("error").toString()); return; }
    call("/api/challenge/start",{{"lesson_id",lessonId},{"snapshot",snapshot},{"retry",challengeComplete}},[this](const QJsonObject& obj,int code) {
        if (code!=200 || obj.contains("error")) { status->setText(obj.value("error").toString()); return; }
        showChallenge(obj);
    });
}
void AiAssistant::refreshChallenge() {
    call("/api/challenge/current",{{"lesson_id",lessonId}},[this](const QJsonObject& obj,int code) {
        if (code==200 && !obj.contains("error") && !(obj.contains("available") && !obj.value("available").toBool())) showChallenge(obj);
        else { challengePanel->hide(); challengeId=0; }
        if (quizLocked) applyQuizLock();
        refreshWork();
    });
}
void AiAssistant::showChallenge(const QJsonObject& obj) {
    challengeId=obj.value("id").toInt(); challengeStep=obj.value("step").toInt(); challengeComplete=obj.value("completed").toBool();
    if (!challengeId) { challengePanel->hide(); return; }
    challengeTitle->setText(challengeComplete ? QString::fromUtf8("Izziv zaključen · %1 točk za dejavnost").arg(obj.value("points").toInt()) : QString::fromUtf8("Izziv %1/3 · %2 točk za dejavnost").arg(challengeStep+1).arg(obj.value("points").toInt()));
    challengePrompt->setText(obj.value("prompt").toString());
    challengePrompt->setMinimumHeight(challengePrompt->heightForWidth(qMax(260,challengePanel->width()-40)));
    challengeFeedback->setText(obj.value("message").toString());
    challengeChoices->clear();
    for (auto value : obj.value("choices").toArray()) challengeChoices->addItem(value.toString());
    challengeChoices->setCurrentIndex(-1); challengeChoices->setVisible(challengeChoices->count()>0 && !challengeComplete);
    challengeAnswer->clear(); challengeAnswer->setVisible(!challengeComplete && challengeChoices->count()==0);
    challengeButton->setText(challengeComplete?QString::fromUtf8("Ponovi"):QString::fromUtf8("Skrij izziv"));
    challengeSubmit->setVisible(!challengeComplete); challengeHint->setVisible(!challengeComplete);
    challengeSubmit->setEnabled(!challengeComplete); challengeHint->setEnabled(!challengeComplete);
    transcript->setVisible(challengeComplete); question->setVisible(challengeComplete); sendButton->setVisible(challengeComplete); cancelButton->setVisible(challengeComplete);
    challengePanel->setVisible(!challengeComplete);
    if (challengeComplete) append(QString::fromUtf8("Izziv zaključen"),challengeTitle->text()+"\n"+challengeFeedback->text());
}
void AiAssistant::answerChallenge() {
    if (reply || quizLocked || !challengeId || challengeComplete) return;
    QString answer=challengeAnswer->toPlainText().trimmed();
    if (challengeChoices->currentIndex()>=0) answer=challengeChoices->currentText();
    if (answer.isEmpty()) { challengeFeedback->setText(QString::fromUtf8("Najprej izberi ali napiši odgovor.")); return; }
    if (answer.toUtf8().size()>12000) { challengeFeedback->setText(QString::fromUtf8("Odgovor skrajšaj.")); return; }
    // Resuming on another document also preserves that document before experiments.
    if (experimentPath.isEmpty() || Circuit::self()->getFilePath()!=experimentPath) if (!prepareExperimentCopy()) return;
    auto snapshot=captureAiContext(); if (snapshot.contains("error")) { status->setText(snapshot.value("error").toString()); return; }
    call("/api/challenge/answer",{{"challenge_id",challengeId},{"step",challengeStep},{"answer",answer},{"snapshot",snapshot}},[this](const QJsonObject& obj,int code) {
        if (code!=200 || obj.contains("error")) { challengeFeedback->setText(obj.value("error").toString()+QString::fromUtf8(" Osveži pogovor za preverjanje shranjenega koraka.")); return; }
        showChallenge(obj);
    });
}
void AiAssistant::hintChallenge() {
    if (reply || quizLocked || !challengeId || challengeComplete) return;
    call("/api/challenge/hint",{{"challenge_id",challengeId},{"step",challengeStep}},[this](const QJsonObject& obj,int code) {
        if (code!=200 || obj.contains("error")) { challengeFeedback->setText(obj.value("error").toString()); return; }
        challengeFeedback->setText(obj.value("hint").toString());
    });
}


// A locked attempt lives on the server, so closing the dock or restarting cannot restore tutor access.
void AiAssistant::applyQuizLock() {
    draftLabel->setVisible(!quizLocked);
    if (quizLocked) {
        challengePanel->hide(); transcript->hide(); question->hide(); sendButton->hide(); cancelButton->hide(); quizPanel->show();
    } else {
        quizPanel->hide();
        const bool challengeShown=challengePanel->isVisible();
        transcript->setVisible(!challengeShown); question->setVisible(!challengeShown); sendButton->setVisible(!challengeShown); cancelButton->setVisible(!challengeShown);
    }
    busy(bool(reply));
}
void AiAssistant::refreshWork() {
    if (token.isEmpty() || !lessonId) return;
    call("/api/work/current",{{"lesson_id",lessonId}},[this](const QJsonObject& obj,int code) {
        if (code!=200 || obj.contains("error")) {
            // Fail closed until the server confirms that no assessment is active.
            quizLocked=true; quizTitle->setText(QString::fromUtf8("Stanja kviza ni mogoče preveriti. Osveži pogovor; pomoč asistenta ostaja zaklenjena."));
            status->setText(obj.value("error").toString()); applyQuizLock(); return;
        }
        showWork(obj);
    });
}
void AiAssistant::showWork(const QJsonObject& obj) {
    const int attempt=obj.value("attempt_id").toInt();
    quizAvailable=obj.value("quiz_available").toBool() && !obj.value("completed").toBool(); quizLocked=obj.value("quiz_locked").toBool();
    quizButton->setText(obj.value("completed").toBool()?QString::fromUtf8("Kviz je oddan"):QString::fromUtf8("Končni kviz"));
    quizHasCircuit=obj.value("has_circuit").toBool(); quizLessonId=obj.value("lesson_id").toInt(lessonId);
    quizTitle->setText(obj.value("quiz_title").toString(QString::fromUtf8("Končni kviz"))+QString::fromUtf8("\nMed kvizom je AI pomoč zaklenjena. Osnutki odgovorov se shranjujejo na tem računalniku in se po ponovni prijavi obnovijo. Učitelj jih prejme šele ob oddaji. Vezje shrani posebej s Ctrl+S."));
    quizCircuit->setVisible(quizHasCircuit);
    if (quizLocked && (attempt!=quizAttemptId || quizAnswers.isEmpty())) {
        quizAttemptId=attempt;
        const QJsonArray draft=QJsonDocument::fromJson(savedDraft(draftKey("quiz",attempt)).toByteArray()).array();
        // Keep existing answers on refresh of the same attempt.
        while (quizLayout->count()>3) { auto* item=quizLayout->takeAt(2); if (item->widget()) delete item->widget(); delete item; }
        quizAnswers.clear(); quizQuestions=obj.value("questions").toArray();
        int position=2, index=0;
        for (const auto& entry : quizQuestions) {
            auto q=entry.toObject(); auto* label=new QLabel(QString("%1. %2 (%3 točk)").arg(index+1).arg(q.value("prompt").toString()).arg(q.value("points").toDouble()));
            label->setTextFormat(Qt::PlainText); label->setWordWrap(true); quizLayout->insertWidget(position++,label);
            QWidget* field;
            if (q.value("kind").toString()=="choice") {
                auto* choice=new QComboBox;
                for (const auto& option : q.value("options").toArray()) choice->addItem(option.toString());
                choice->setCurrentIndex(-1); field=choice;
            } else {
                auto* text=new QPlainTextEdit; text->setMaximumHeight(100);
                text->setPlaceholderText(q.value("kind").toString()=="number"?QString::fromUtf8("Številčna vrednost v enoti, navedeni v vprašanju"):QString::fromUtf8("Tvoja razlaga …")); field=text;
            }
            field->setObjectName(QString("aiQuizAnswer%1").arg(index)); quizAnswers.append(field); quizLayout->insertWidget(position++,field);
            if (auto* choice=qobject_cast<QComboBox*>(field)) {
                if (index<draft.size() && draft[index].isDouble()) {
                    int saved=draft[index].toInt(-1); if (saved>=-1 && saved<choice->count()) choice->setCurrentIndex(saved);
                }
                connect(choice,QOverload<int>::of(&QComboBox::currentIndexChanged),this,[this](int) { saveQuizDraft(); });
            } else if (auto* text=qobject_cast<QPlainTextEdit*>(field)) {
                if (index<draft.size() && draft[index].isString()) text->setPlainText(draft[index].toString());
                connect(text,&QPlainTextEdit::textChanged,this,[this] { saveQuizDraft(); });
            }
            ++index;
        }
    }
    quizAttemptId=attempt;
    workButton->setText(obj.value("submitted").toBool()?QString::fromUtf8("Oddaj novo različico"):QString::fromUtf8("Oddaj nalogo"));
    quizButton->setText(quizLocked ? QString::fromUtf8("Kviz v teku") : obj.value("completed").toBool() ? QString::fromUtf8("Kviz oddan") : QString::fromUtf8("Končni kviz"));
    quizButton->setToolTip(quizLocked ? QString::fromUtf8("Nadaljuj začeti kviz. AI pomoč je zaklenjena.") : quizAvailable ? QString::fromUtf8("Učitelj je objavil kviz. Ob začetku se pomoč zaklene do oddaje.") : QString::fromUtf8("Učitelj za to uro še ni objavil kviza ali je ta že oddan."));
    applyQuizLock();
    if (quizLocked) status->setText(QString::fromUtf8("Kviz je začet. AI pomoč ostane zaklenjena do uspešne oddaje."));
    else if (obj.value("submitted").toBool()) status->setText(QString::fromUtf8("Naloga je oddana in vidna učitelju."));
}
void AiAssistant::submitWork() {
    if (reply || quizLocked || !lessonOpen || token.isEmpty()) return;
    bool ok=false;
    const QString comment=QInputDialog::getMultiLineText(this,QString::fromUtf8("Oddaja naloge"),QString::fromUtf8("Kratko opiši rezultat, meritve ali težave. Oddano bo tudi trenutno vezje."),workComment,&ok).trimmed();
    if (!ok) return;
    const QString circuit=Circuit::self()->circuitToString();
    if (workRequestId.isEmpty() || workComment!=comment || workCircuit!=circuit) {
        workSnapshot=captureAiContext(); if (workSnapshot.contains("error")) { status->setText(workSnapshot.value("error").toString()); return; }
        workComment=comment; workCircuit=circuit; workRequestId=QUuid::createUuid().toString(QUuid::WithoutBraces);
    }
    call("/api/work/submit",{{"lesson_id",lessonId},{"comment",workComment},{"circuit",workCircuit},{"snapshot",workSnapshot},{"request_id",workRequestId}},[this](const QJsonObject& obj,int code) {
        if (code!=200 || obj.contains("error")) { status->setText(obj.value("error").toString()+QString::fromUtf8(" Ponovi oddajo za preverjanje.")); return; }
        const QString receipt=QString::fromUtf8("Oddaja #%1 je potrjena in vidna učitelju. Shranjeno je vezje ob oddaji.").arg(obj.value("submission_id").toInt());
        status->setText(receipt); append(QString::fromUtf8("Potrdilo o oddaji"),receipt); workButton->setText(QString::fromUtf8("Oddaj novo različico")); workRequestId.clear();
    });
}
void AiAssistant::startQuiz() {
    if (reply || token.isEmpty()) return;
    if (quizLocked) { applyQuizLock(); return; }
    if (!lessonOpen || !quizAvailable) return;
    if (QMessageBox::question(this,QString::fromUtf8("Začni končni kviz"),QString::fromUtf8("Po začetku kviza se AI pomoč in prejšnji odgovori skrijejo do oddaje. Nadaljuješ?"))!=QMessageBox::Yes) return;
    // Lock before sending: an interrupted request may already have started the attempt.
    quizLocked=true; applyQuizLock();
    call("/api/quiz/start",{{"lesson_id",lessonId}},[this](const QJsonObject& obj,int code) {
        if (code!=200 || obj.contains("error")) { status->setText(obj.value("error").toString()); refreshWork(); return; }
        showWork(obj);
    });
}
void AiAssistant::finishQuiz() {
    if (reply || !quizLocked || !quizAttemptId) return;
    QJsonArray answers;
    for (auto* field : quizAnswers) {
        if (auto* choice=qobject_cast<QComboBox*>(field)) {
            if (choice->currentIndex()<0) { status->setText(QString::fromUtf8("Izberi odgovor na označeno vprašanje.")); static_cast<QScrollArea*>(quizPanel)->ensureWidgetVisible(choice); choice->setFocus(); return; }
            answers.append(choice->currentIndex());
        } else if (auto* text=qobject_cast<QPlainTextEdit*>(field)) {
            if (text->toPlainText().trimmed().isEmpty()) { status->setText(QString::fromUtf8("Dopolni označeni odgovor pred oddajo.")); static_cast<QScrollArea*>(quizPanel)->ensureWidgetVisible(text); text->setFocus(); return; }
            answers.append(text->toPlainText().trimmed());
        }
    }
    auto snapshot=captureAiContext(); if (snapshot.contains("error")) { status->setText(snapshot.value("error").toString()); return; }
    call("/api/quiz/finish",{{"attempt_id",quizAttemptId},{"answers",answers},{"circuit",Circuit::self()->circuitToString()},{"snapshot",snapshot}},[this](const QJsonObject& obj,int code) {
        if (code!=200 || obj.contains("error") || !obj.value("completed").toBool()) { status->setText(obj.value("error").toString(QString::fromUtf8("Oddaja ni potrjena. Kviz ostaja zaklenjen; ponovi oddajo."))); return; }
        QSettings cfg(QSettings::IniFormat,QSettings::UserScope,"SimulIDE","ClassroomDrafts"); cfg.remove(draftKey("quiz",quizAttemptId)); cfg.sync();
        quizLocked=false; quizAvailable=false; quizButton->setText(QString::fromUtf8("Kviz je oddan")); applyQuizLock();
        const QString result=obj.value("message").toString(QString::fromUtf8("Kviz je oddan."))+QString::fromUtf8("\nTočke: %1 / %2%3").arg(obj.value("score").toDouble()).arg(obj.value("max_score").toDouble()).arg(obj.value("pending_review").toBool()?QString::fromUtf8(" · razlage čakajo na učiteljev pregled"):QString());
        append(QString::fromUtf8("Končni kviz"),result); status->setText(result);
    });
}
void AiAssistant::openQuizCircuit() {
    if (reply || !quizLocked || !quizAttemptId || !quizHasCircuit) return;
    call("/api/quiz/circuit",{{"lesson_id",quizLessonId},{"attempt_id",quizAttemptId}},[this](const QJsonObject& obj,int code) {
        if (code!=200 || obj.contains("error")) { status->setText(obj.value("error").toString()); return; }
        const QByteArray attached=obj.value("circuit").toString().toUtf8();
        if (attached.isEmpty()) { status->setText(QString::fromUtf8("Priloženo vezje je prazno.")); return; }
        QString original=QFileDialog::getSaveFileName(this,QString::fromUtf8("Shrani trenutno vezje pred odprtjem kviza"),Circuit::self()->getFilePath(),QString::fromUtf8("Vezje SimulIDE (*.sim2)"));
        if (original.isEmpty()) return;
        if (!original.endsWith(".sim2",Qt::CaseInsensitive)) original+=".sim2";
        const QByteArray current=Circuit::self()->circuitToString().toUtf8(); QSaveFile backup(original);
        if (!backup.open(QIODevice::WriteOnly) || backup.write(current)!=current.size() || !backup.commit()) { status->setText(QString::fromUtf8("Trenutnega vezja ni mogoče shraniti. Odpiranje je preklicano.")); return; }
        CircuitWidget::self()->saveCirc(original);
        const QString path=QFileInfo(original).absolutePath()+"/kviz-"+QString::number(quizAttemptId)+"-"+QUuid::createUuid().toString(QUuid::WithoutBraces).left(8)+".sim2";
        QSaveFile copy(path);
        if (!copy.open(QIODevice::WriteOnly) || copy.write(attached)!=attached.size() || !copy.commit()) { status->setText(QString::fromUtf8("Kopije priloženega vezja ni mogoče ustvariti.")); return; }
        CircuitWidget::self()->loadCirc(path);
        status->setText(Circuit::self()->getFilePath()==path?QString::fromUtf8("Prvotno vezje je shranjeno. Odprta je tvoja kopija vezja kviza."):QString::fromUtf8("Odpiranje vezja je bilo preklicano. Kviz ostaja zaklenjen."));
    });
}

QString AiAssistant::draftKey(const QString& kind, int id) const {
    const QByteArray identity=server.toUtf8()+QByteArray("\n")+username.toUtf8();
    return "AiClassroom/drafts/"+QString::fromLatin1(QCryptographicHash::hash(identity,QCryptographicHash::Sha256).toHex())+"/"+kind+"/"+QString::number(id);
}
void AiAssistant::saveQuizDraft() {
    if (!quizLocked || quizAttemptId<=0 || token.isEmpty()) return;
    QJsonArray answers;
    for (auto* field : quizAnswers) {
        if (auto* choice=qobject_cast<QComboBox*>(field)) answers.append(choice->currentIndex());
        else if (auto* text=qobject_cast<QPlainTextEdit*>(field)) answers.append(text->toPlainText());
    }
    QSettings cfg(QSettings::IniFormat,QSettings::UserScope,"SimulIDE","ClassroomDrafts"); cfg.setValue(draftKey("quiz",quizAttemptId),QJsonDocument(answers).toJson(QJsonDocument::Compact)); cfg.sync();
    if (cfg.status()!=QSettings::NoError) status->setText(QString::fromUtf8("Osnutka ni mogoče shraniti na ta računalnik. Programa pred oddajo ne zapiraj."));
}
