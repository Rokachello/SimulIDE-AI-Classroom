// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "aicontext.h"
#include "circuit.h"
#include "mainwindow.h"
#include "circuitwidget.h"
#include "simulator.h"
#include <QApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QTimer>
#include <cmath>
#include <cstdio>
#include <cstdlib>
inline void aiCheck(bool ok, const char* text) {
    if (!ok) { fprintf(stderr, "AI CONTEXT FAIL: %s\n", text); std::exit(1); }
}
inline void runAiContextTest() {
    auto* c = Circuit::self();
    auto* v = c->createComponent("Voltage Source", "V", QPoint(-100, -100));
    auto* r = c->createComponent("Resistor", "R", QPoint(0, 0));
    auto* g = c->createComponent("Ground", "GND", QPoint(100, 100));
    aiCheck(v && r && g, "test components created");
    r->setPropStr("Resistance", "1000");
    v->setPropStr("Value_Volt", "5"); v->setPropStr("Running", "true");
    c->newconnector(v->getPins()[0]); c->closeconnector(r->getPins()[0]);
    c->newconnector(r->getPins()[1]); c->closeconnector(g->getPins()[0]);
    auto stopped = captureAiContext();
    aiCheck(stopped["components"].toArray().size() == 3, "components included");
    aiCheck(stopped["connections"].toArray().size() == 2, "two wires included");
    aiCheck(!stopped["simulation"].toObject()["measurements_valid"].toBool(), "stopped readings invalid");
    for (auto component : stopped["components"].toArray())
        for (auto pin : component.toObject()["pins"].toArray())
            aiCheck(pin.toObject()["voltage_V"].isNull(), "stopped voltage is null");
    CircuitWidget::self()->powerCircOn();
    QTimer::singleShot(300, [] {
        auto* sim = Simulator::self();
        aiCheck(sim->simState() == SIM_RUNNING, "simulation running");
        const auto running = captureAiContext();
        aiCheck(sim->simState() == SIM_RUNNING, "capture restores running state");
        aiCheck(running["simulation"].toObject()["measurements_valid"].toBool(), "running readings valid");
        bool foundFive = false;
        for (auto component : running["components"].toArray())
            for (auto pin : component.toObject()["pins"].toArray()) {
                QJsonValue value = pin.toObject().value("voltage_V");
                if (value.isDouble() && std::fabs(value.toDouble() - 5.0) < 0.01) foundFive = true;
            }
        if (!foundFive) fprintf(stderr, "%s\n", QJsonDocument(running).toJson().constData());
        aiCheck(foundFive, "known 5V source captured");
        aiCheck(running["simulation"].toObject()["timeline"].toObject()["samples"].toArray().size() >= 1, "timeline records running simulation");
        QTimer::singleShot(300, [] {
        auto* sim = Simulator::self();
        auto trace = captureAiContext()["simulation"].toObject()["timeline"].toObject();
        auto samples = trace["samples"].toArray();
        aiCheck(samples.size() >= 2, "multiple timed solver samples captured");
        aiCheck(samples.last().toObject()["time_s"].toDouble() > samples.first().toObject()["time_s"].toDouble(), "simulation time increases");
        bool measuredFive = false;
        for (auto val : samples.last().toObject()["values"].toArray())
            if (std::fabs(val.toDouble() - 5) < 0.01) measuredFive = true;
        aiCheck(measuredFive, "timeline includes real 5V reading");
        sim->pauseSim(); sim->waitForAiSnapshot();
        captureAiContext(); aiCheck(sim->simState() == SIM_PAUSED, "paused state preserved");
        auto paused = captureAiContext()["simulation"].toObject()["timeline"].toObject()["samples"].toArray().size();
        aiCheck(captureAiContext()["simulation"].toObject()["timeline"].toObject()["samples"].toArray().size() == paused, "paused samples do not duplicate");
        for (auto* component : *Circuit::self()->compList())
            if (component->itemType() == "Resistor") component->setPropStr("Resistance", "2000");
        aiCheck(captureAiContext()["simulation"].toObject()["timeline"].toObject()["samples"].toArray().size() == 1, "changed property clears previous history");
        setAiTimelineEnabled(false);
        aiCheck(captureAiContext()["simulation"].toObject()["timeline"].toObject()["samples"].toArray().isEmpty(), "disabled history removed");
        setAiTimelineEnabled(true); captureAiContext();
        sim->stopSim();
        aiCheck(captureAiContext()["simulation"].toObject()["timeline"].toObject()["samples"].toArray().isEmpty(), "stop clears history");
        fprintf(stderr, "PASS: native stopped/running/paused circuit context and 5V measurement\n");
        std::exit(0);
        });
    });
}
