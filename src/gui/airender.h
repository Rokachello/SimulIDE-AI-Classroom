// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QTextDocument>
#include <QTextCursor>
#include <QTextImageFormat>
#include <QPainter>
#include <QFontMetricsF>
#include <QRegularExpression>
#include <QUuid>
#include <functional>
#include <QtMath>
#include <QMap>

namespace AiRender {
// Markdown may contain URLs, but a reply must never fetch images or local files.
class Document : public QTextDocument {
protected:
    QVariant loadResource(int, const QUrl&) override { return QVariant(); }
};
struct Box {
    qreal width=0, above=0, below=0;
    std::function<void(QPainter&,qreal,qreal)> draw;
};
inline Box word(QString s, qreal size) {
    QFont font("DejaVu Sans"); font.setPixelSize(qRound(size));
    QFontMetricsF m(font); Box b;
    b.width=m.horizontalAdvance(s); b.above=m.ascent(); b.below=m.descent();
    b.draw=[s,font](QPainter& p,qreal x,qreal y) { p.setFont(font); p.drawText(QPointF(x,y),s); }; return b;
}
inline Box row(const QVector<Box>& items) {
    Box b; for (const auto& a:items) { b.width+=a.width; b.above=qMax(b.above,a.above); b.below=qMax(b.below,a.below); }
    b.draw=[items](QPainter& p,qreal x,qreal y) { for (const auto& a:items) { if(a.draw) a.draw(p,x,y); x+=a.width; } }; return b;
}
class Math {
    QString source; int pos=0, depth=0; bool valid=true;
    Box group(qreal size) {
        if (++depth>16) { valid=false; pos=source.size(); --depth; return word("?",size); }
        while(pos<source.size() && source[pos].isSpace()) ++pos;
        Box b;
        if(pos<source.size() && source[pos]=='{') { ++pos; b=sequence(size,true); }
        else b=atom(size);
        --depth; return b;
    }
    Box atom(qreal size) {
        if(pos>=source.size()) { valid=false; return word("?",size); }
        QChar ch=source[pos++];
        if(ch=='{') { --pos; return group(size); }
        if(ch!='\\') return word(QString(ch),size);
        int start=pos; while(pos<source.size() && source[pos].isLetter()) ++pos;
        QString cmd=source.mid(start,pos-start);
        if(cmd.isEmpty()) { if(pos<source.size()) { QChar c=source[pos++]; if(c==',' || c==';' || c==':' || c==' ') return word(" ",size); if(c=='!') return word("",size); return word(QString(c),size); } valid=false; return word("?",size); }
        if(cmd=="frac" || cmd=="dfrac" || cmd=="tfrac") {
            auto n=group(size*.9), d=group(size*.9); Box b;
            b.width=qMax(n.width,d.width)+10; b.above=n.above+n.below+7; b.below=d.above+d.below+5;
            b.draw=[n,d,b](QPainter& p,qreal x,qreal y) { n.draw(p,x+(b.width-n.width)/2,y-5-n.below); p.drawLine(QPointF(x+2,y-2),QPointF(x+b.width-2,y-2)); d.draw(p,x+(b.width-d.width)/2,y+3+d.above); }; return b;
        }
        if(cmd=="text" || cmd=="mathrm" || cmd=="mathbf" || cmd=="operatorname") return group(size);
        if(cmd=="left" || cmd=="right") return word("",size);
        if(cmd=="sqrt") { auto a=group(size); auto root=word(QString::fromUtf8("√"),size); return row({root,a}); }
        static const QMap<QString,QString> symbols={{"times",QString::fromUtf8(" × ")},{"cdot",QString::fromUtf8(" · ")},{"Omega",QString::fromUtf8("Ω")},{"omega",QString::fromUtf8("ω")},{"alpha",QString::fromUtf8("α")},{"beta",QString::fromUtf8("β")},{"Delta",QString::fromUtf8("Δ")},{"pi",QString::fromUtf8("π")},{"mu",QString::fromUtf8("μ")},{"tau",QString::fromUtf8("τ")},{"theta",QString::fromUtf8("θ")},{"approx",QString::fromUtf8(" ≈ ")},{"leq",QString::fromUtf8(" ≤ ")},{"geq",QString::fromUtf8(" ≥ ")},{"infty",QString::fromUtf8("∞")},{"quad","  "},{"qquad","    "}};
        if(symbols.contains(cmd)) return word(symbols.value(cmd),size);
        valid=false; return word(cmd,size);
    }
    Box sequence(qreal size,bool closing) {
        QVector<Box> parts;
        while(pos<source.size() && source[pos]!='}') {
            auto base=atom(size); Box sub,sup; bool hasSub=false,hasSup=false;
            while(pos<source.size() && (source[pos]=='_' || source[pos]=='^')) {
                bool low=source[pos++]=='_'; auto a=group(size*.72);
                if(low) { sub=a; hasSub=true; } else { sup=a; hasSup=true; }
            }
            if(hasSub || hasSup) {
                Box b; b.width=base.width+qMax(sub.width,sup.width); b.above=qMax(base.above,hasSup?size*.55+sup.above:0.); b.below=qMax(base.below,hasSub?size*.3+sub.below:0.);
                b.draw=[base,sub,sup,hasSub,hasSup,size](QPainter& p,qreal x,qreal y) { base.draw(p,x,y); if(hasSub) sub.draw(p,x+base.width,y+size*.3); if(hasSup) sup.draw(p,x+base.width,y-size*.55); }; base=b;
            }
            parts.append(base);
        }
        if(closing) { if(pos<source.size() && source[pos]=='}') ++pos; else valid=false; }
        return row(parts);
    }
public:
    explicit Math(QString s):source(s.left(2048)) { if(s.size()>2048) valid=false; }
    Box parse() { return sequence(18,false); }
    bool supported() const { return valid && pos==source.size(); }
};
inline QString equation(QString source,QTextDocument* target) {
    // Long equality chains become separate lines instead of shrinking the formula.
    Math whole(source); auto wholeBox=whole.parse();
    if(!whole.supported()) return "<code>"+source.toHtmlEscaped()+"</code>";
    QStringList lines=wholeBox.width>350 ? source.split('=') : QStringList{source}; QString result;
    for(int i=0;i<lines.size();++i) {
        QString s=lines[i].trimmed(); if(i) s="= "+s;
        Math parser(s); auto b=parser.parse();
        if(!parser.supported() || b.width>1800) return "<code>"+source.toHtmlEscaped()+"</code>";
        QImage img(qCeil((b.width+12)*2),qCeil((b.above+b.below+12)*2),QImage::Format_ARGB32_Premultiplied); img.fill(Qt::transparent);
        QPainter p(&img); p.scale(2,2); p.setRenderHint(QPainter::Antialiasing); p.setRenderHint(QPainter::TextAntialiasing); p.setPen(QColor("#182c40")); b.draw(p,6,b.above+6); p.end();
        QString id="ai-math:"+QUuid::createUuid().toString(QUuid::WithoutBraces); target->addResource(QTextDocument::ImageResource,QUrl(id),img);
        if(i) result+="<br>";
        result+=QString("<img src=\"%1\" width=\"%2\" height=\"%3\" alt=\"%4\">").arg(id).arg((b.width+12),0,'f',0).arg((b.above+b.below+12),0,'f',0).arg(s.toHtmlEscaped());
    }
    return result;
}
inline QString content(QString source,QTextDocument* target) {
    // Only extract math outside fenced/inline code. Bounded formulas and nesting.
    QString prepared; QVector<QPair<QString,QString>> formulas; bool fence=false,code=false;
    for(int i=0;i<source.size();) {
        if(source.mid(i,3)=="```" || source.mid(i,3)=="~~~") { fence=!fence; prepared+=source.mid(i,3); i+=3; continue; }
        if(!fence && source[i]=='`') { code=!code; prepared+=source[i++]; continue; }
        QString open,close;
        if(!fence && !code) {
            if(source.mid(i,2)=="\\[") { open="\\["; close="\\]"; }
            else if(source.mid(i,2)=="\\(") { open="\\("; close="\\)"; }
            else if(source.mid(i,2)=="$$") { open="$$"; close="$$"; }
            else if(source[i]=='$') { open="$"; close="$"; }
        }
        int end=open.isEmpty()?-1:source.indexOf(close,i+open.size());
        if(end>=0 && end-i<=2052 && formulas.size()<100) {
            QString key="AIMATH"+QUuid::createUuid().toString(QUuid::Id128)+"END";
            formulas.append({key,source.mid(i+open.size(),end-i-open.size())}); prepared+=key; i=end+close.size();
        } else prepared+=source[i++];
    }
    Document doc; doc.setMarkdown(prepared,QTextDocument::MarkdownFeatures(QTextDocument::MarkdownDialectGitHub)|QTextDocument::MarkdownNoHTML);
    QString html=doc.toHtml();
    // Suppress all externally supplied image tags; only our math resources are added below.
    html.remove(QRegularExpression("<img\\b[^>]*>",QRegularExpression::CaseInsensitiveOption));
    int start=html.indexOf("<body"); start=html.indexOf('>',start)+1; int end=html.lastIndexOf("</body>"); html=html.mid(start,end-start);
    for(const auto& f:formulas) html.replace(f.first,equation(f.second,target));
    return html;
}
inline QString message(const QString& who,const QString& text,QTextDocument* target) {
    QString color=who==QString::fromUtf8("Ti")?"#e8f2ff":"#f4f6f8";
    return "<table width=\"100%\" cellpadding=\"12\" cellspacing=\"0\" bgcolor=\""+color+"\"><tr><td><p style=\"color:#245b83; margin-bottom:8px\"><b>"+who.toHtmlEscaped()+"</b></p>"+content(text,target)+"</td></tr></table><p></p>";
}
}
