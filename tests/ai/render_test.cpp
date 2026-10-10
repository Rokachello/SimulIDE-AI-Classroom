// SPDX-License-Identifier: GPL-3.0-or-later
#include "airender.h"
#include <QApplication>
#include <QTextBrowser>
#include <QFile>
#include <QTextBlock>
#include <QTextFragment>
#include <cstdio>
#define REQUIRE(x) do { if(!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); return 1; } } while(0)
int main(int argc,char** argv) {
    QApplication app(argc,argv); QTextBrowser browser;
    browser.setDocument(new AiRender::Document); browser.document()->setParent(&browser);
    browser.setOpenLinks(false); browser.setFont(QFont("DejaVu Sans",11)); browser.document()->setDocumentMargin(12);
    QString answer=QString::fromUtf8("**Napetostni delilnik**\n\nOba upora sta enaka, zato je izhodna napetost polovica vhodne.\n\n\\[U_{out} = U_{in} \\times \\frac{R_2}{R_1 + R_2} = 5\\,V \\times \\frac{100\\,\\Omega}{100\\,\\Omega + 100\\,\\Omega} = 2{,}5\\,V\\]\n\n- Vhodna napetost je **5 V**.\n- Oba upora imata **100 Ω**.\n\nZa izhodno napetost 3 V potrebuješ drugačno razmerje uporov. **Kateri upor bi povečal?**");
    auto add=[&](QString who,QString text) { QTextCursor c(browser.document()); c.movePosition(QTextCursor::End); c.insertHtml(AiRender::message(who,text,browser.document())); };
    add(QString::fromUtf8("Ti"),QString::fromUtf8("Zakaj dobim 2,5 V? Rad bi imel 3 V.")); add("Asistent",answer);
    REQUIRE(!browser.toPlainText().contains("\\frac")); REQUIRE(browser.toHtml().contains("ai-math:")); REQUIRE(browser.toPlainText().contains(QString::fromUtf8("Kateri upor")));
    int pictures=0; bool bold=false;
    for(auto b=browser.document()->begin(); b.isValid(); b=b.next()) for(auto it=b.begin(); !it.atEnd(); ++it) { auto f=it.fragment(); if(f.charFormat().isImageFormat()) { ++pictures; auto name=f.charFormat().toImageFormat().name(); auto resource=browser.document()->resource(QTextDocument::ImageResource,QUrl(name)); REQUIRE(resource.canConvert<QImage>()); } if(f.text().contains("Napetostni delilnik")) bold=f.charFormat().fontWeight()>=QFont::Bold; }
    REQUIRE(pictures>=3); REQUIRE(bold);
    AiRender::Document safe; QString html=AiRender::content("![secret](file:///etc/passwd)\n<img src='https://example.com/a.png'>\n<script>bad()</script>",&safe);
    REQUIRE(!html.contains("<img")); REQUIRE(!html.contains("<script")); REQUIRE(!safe.resource(QTextDocument::ImageResource,QUrl("file:///etc/passwd")).isValid());
    REQUIRE(AiRender::content("`\\frac{1}{2}`",&safe).contains("\\frac"));
    REQUIRE(AiRender::equation("\\unknown{a}",&safe).contains("<code>"));
    REQUIRE(AiRender::equation(QString(40,'{')+"x"+QString(40,'}'),&safe).contains("<code>"));
    browser.resize(500,720); browser.show(); app.processEvents(); browser.grab().save(argc>1?argv[1]:"render-preview.png");
    printf("PASS: screenshot equation, subscripts/fractions, Markdown, unavailable syntax fallback, bounded nesting and blocked image resources\n"); return 0;
}
