// SPDX-License-Identifier: GPL-3.0-or-later
#include "aicontext.h"
#include "circuit.h"
#include "simulator.h"
#include "node.h"
#include "comproperty.h"
#include <QJsonArray>
#include <QDateTime>
#include <QFileInfo>
#include <QJsonDocument>
#include <QCryptographicHash>
#include <QSet>
#include <cmath>


static QJsonObject describe(Component* comp, bool measured) {
    QJsonObject properties;
    for (const auto& group : *comp->properties())
        for (ComProperty* prop : group.propList)
            properties[prop->name()] = QJsonObject{{"value", prop->getValStr()}, {"unit", prop->unit()}};
    QJsonArray pins;
    for (Pin* pin : comp->getPins()) {
        if (!pin) continue;
        QJsonObject p{{"id", pin->pinId()}, {"label", pin->getLabelText()},
                       {"wired", pin->connector() != nullptr || pin->conPin() != nullptr},
                       {"bus", pin->isBus()}, {"unused", pin->unused()}};
        // Solver nodes exist only after simulation initialisation. Do not equate
        // their absence in a stopped simulation with an unconnected schematic.
        p["solver_node"] = measured && pin->getEnode() ? QJsonValue(pin->getEnode()->itemId()) : QJsonValue();
        p["voltage_V"] = measured && pin->getEnode() ? QJsonValue(pin->getVoltage()) : QJsonValue();
        p["current_A"] = measured && pin->hasCurrent() ? QJsonValue(pin->getCurrent()) : QJsonValue();
        pins.append(p);
    }
    return QJsonObject{{"id", comp->getUid()}, {"type", comp->itemType()},
                       {"label", comp->idLabel()}, {"selected", comp->isSelected()},
                       {"properties", properties}, {"pins", pins}};
}

namespace {
bool timelineEnabled = true;
QByteArray timelineFingerprint;
QJsonArray timelineChannels, timelineSamples;
int omittedSignals = 0;
void clearTimeline() {
    timelineFingerprint.clear(); timelineChannels = QJsonArray();
    timelineSamples = QJsonArray(); omittedSignals = 0;
}
QJsonObject timelineFor(const QJsonObject& snapshot) {
    auto simulation = snapshot["simulation"].toObject();
    if (!timelineEnabled || !simulation["measurements_valid"].toBool()) clearTimeline();
    if (timelineEnabled && simulation["measurements_valid"].toBool()) {
        QJsonArray identity, channels, values;
        QSet<QString> voltageNodes;
        int total = 0;
        for (const auto& collection : {QString("components"), QString("junctions")}) {
            for (auto entry : snapshot[collection].toArray()) {
                auto component = entry.toObject();
                QJsonArray pins;
                for (auto pinEntry : component["pins"].toArray()) {
                    auto pin = pinEntry.toObject();
                    QJsonObject identityPin = pin;
                    identityPin.remove("voltage_V"); identityPin.remove("current_A");
                    pins.append(identityPin);
                    for (const auto& quantity : {QString("voltage_V"), QString("current_A")}) {
                        auto value = pin[quantity];
                        if (!value.isDouble() || !std::isfinite(value.toDouble())) continue;
                        if (quantity == "voltage_V") {
                            QString node = pin["solver_node"].toString();
                            if (voltageNodes.contains(node)) continue;
                            voltageNodes.insert(node);
                        }
                        ++total;
                        if (channels.size() >= 24) continue;
                        channels.append(QJsonObject{{"component_id", component["id"]},
                            {"component_label", component["label"]}, {"pin_id", pin["id"]},
                            {"pin_label", pin["label"]}, {"solver_node", pin["solver_node"]},
                            {"quantity", quantity}});
                        values.append(value);
                    }
                }
                component.remove("selected"); component["pins"] = pins; identity.append(component);
            }
        }
        QJsonObject signature{{"components", identity}, {"connections", snapshot["connections"]},
                              {"channels", channels}, {"file_name", snapshot["file_name"]}, {"step_ps", simulation["step_ps"]}};
        auto fingerprint = QCryptographicHash::hash(QJsonDocument(signature).toJson(QJsonDocument::Compact), QCryptographicHash::Sha256);
        double time = simulation["time_s"].toDouble();
        if (fingerprint != timelineFingerprint || (!timelineSamples.isEmpty() &&
                time < timelineSamples.last().toObject()["time_s"].toDouble())) clearTimeline();
        timelineFingerprint = fingerprint; timelineChannels = channels; omittedSignals = total - channels.size();
        if (timelineSamples.isEmpty() || time > timelineSamples.last().toObject()["time_s"].toDouble()) {
            timelineSamples.append(QJsonObject{{"time_ps", simulation["time_ps"]},
                                               {"time_s", time}, {"values", values}});
            while (timelineSamples.size() > 100) timelineSamples.removeAt(0);
        }
    }
    double maxGap = 0;
    for (int i = 1; i < timelineSamples.size(); ++i)
        maxGap = qMax(maxGap, timelineSamples[i].toObject()["time_s"].toDouble() - timelineSamples[i-1].toObject()["time_s"].toDouble());
    return QJsonObject{{"enabled", timelineEnabled}, {"kind", "sparse_gui_samples"},
        {"poll_interval_wall_ms", 200}, {"max_samples", 100}, {"max_channels", 24},
        {"omitted_signals", omittedSignals}, {"max_observed_gap_sim_s", maxGap},
        {"channels", timelineChannels}, {"samples", timelineSamples},
        {"limitations", "Not a solver trace. Fast transitions may be missed or aliased. Values are indexed by channels; current sign follows the component pin convention. History resets on stop/restart or observed circuit/property changes."}};
}
}
void setAiTimelineEnabled(bool enabled) { timelineEnabled = enabled; clearTimeline(); }

QJsonObject captureAiContext() {
    auto* circuit = Circuit::self();
    auto* sim = Simulator::self();
    if (!circuit || !sim || circuit->isBusy() || circuit->is_constarted())
        return QJsonObject{{"error", "Dokončaj povezavo oziroma urejanje vezja in poskusi ponovno."}};
    const simState_t original = sim->simState();
    const bool resume = original == SIM_RUNNING;
    if (resume) sim->pauseSim();
    sim->waitForAiSnapshot(); // Join the solver before reading its mutable nodes.
    const bool measured = original == SIM_RUNNING || original == SIM_PAUSED;
    const char* states[] = {"stopped", "error", "starting", "paused", "waiting", "running", "debug"};
    QJsonArray components, junctions, wires;
    for (auto* comp : *circuit->compList()) components.append(describe(comp, measured));
    for (auto* node : *circuit->nodeList()) junctions.append(describe(node, measured));
    for (auto* wire : *circuit->conList())
        wires.append(QJsonObject{{"id", wire->getUid()}, {"from", wire->startPinId()},
                                 {"to", wire->endPinId()}, {"bus", wire->isBus()}});
    QJsonObject result{{"schema", "simulide-ai-context/1"},
        {"captured_utc", QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)},
        {"file_name", QFileInfo(circuit->getFilePath()).fileName()},
        {"components", components}, {"junctions", junctions}, {"connections", wires},
        {"simulation", QJsonObject{{"state", states[int(original)]},
            {"time_ps", QString::number(sim->circTime())},
            {"time_s", double(sim->circTime()) / 1e12}, {"step_ps", QString::number(sim->stepSize())},
            {"measurements_valid", measured}, {"measurement_kind", "single_instant_snapshot"}}},
        {"limitations", QJsonArray{"Sparse timeline only; no full-bandwidth waveform, frequency measurement or oscilloscope traces.",
            "No firmware/source file contents. Component properties may reference filenames.",
            "Nested subcircuit internals may not be fully exposed; bus lanes require interpretation.",
            "Null voltages are unknown, not zero. Wired does not prove a complete electrical path."}}};
    auto simulation = result["simulation"].toObject();
    simulation["timeline"] = timelineFor(result);
    result["simulation"] = simulation;
    if (resume) sim->resumeSim();
    return result;
}
