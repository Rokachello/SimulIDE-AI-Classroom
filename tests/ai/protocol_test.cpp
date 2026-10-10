// SPDX-License-Identifier: GPL-3.0-or-later
#include "aiprotocol.h"
#include <QCoreApplication>
#include <iostream>
#include <cstdlib>
static void check(bool ok, const char* message) {
    if (!ok) { std::cerr << "FAIL: " << message << std::endl; std::exit(1); }
}
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    QJsonArray history{AiProtocol::message("user", "old question"), AiProtocol::message("assistant", "old answer")};
    auto req = AiProtocol::request("chosen-model", "editable prompt", history, "fresh snapshot", "new question");
    check(req["instructions"] == "editable prompt", "system prompt preserved");
    check(req["model"] == "chosen-model", "chosen model preserved");
    check(!req["store"].toBool(true), "response storage disabled");
    auto input = req["input"].toArray();
    check(input.size() == 4, "history and current context included");
    check(input[2].toObject()["content"].toString().contains("fresh snapshot"), "latest context attached");
    check(input[3].toObject()["content"] == "new question", "question kept separate");
    check(history.size() == 2, "request does not mutate history");
    const auto output = QJsonDocument::fromJson(R"({"output":[{"type":"reasoning","summary":[]},{"type":"message","content":[{"type":"output_text","text":"first"},{"type":"output_text","text":"second"}]}]})").object();
    check(AiProtocol::responseText(output) == "first\nsecond", "parse message after reasoning, multiple texts");
    const auto refusal = QJsonDocument::fromJson(R"({"output":[{"type":"message","content":[{"type":"refusal","refusal":"refused"}]}]})").object();
    check(AiProtocol::responseText(refusal) == "refused", "refusals displayed");
    check(AiProtocol::responseText(QJsonObject()).isEmpty(), "missing output handled");
    std::cout << "PASS: protocol request and response cases" << std::endl;
}
