BUILD_DIR = $$PWD/build_AI
include(SimulIDE.pri)
PRE_TARGETDEPS -= runLrelease
QMAKE_EXTRA_TARGETS -= runLrelease
contains(CONFIG, ai_test): DEFINES += AI_SELF_TEST

# Bundle zlib for Windows; no separate zlib package is needed.
win32 {
    LIBS -= -lz
    INCLUDEPATH += $$PWD/third_party/zlib
    SOURCES += $$files($$PWD/third_party/zlib/*.c)
    HEADERS += $$files($$PWD/third_party/zlib/*.h)
}
