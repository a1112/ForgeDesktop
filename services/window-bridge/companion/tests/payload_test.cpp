#include "payload.h"
#include <cassert>
int main() {
    const QByteArray good = R"({"type":"window","id":"a","parent":null,"caption":"title","app_id":"app","kind":"normal","geometry":{"x":0,"y":0,"width":640,"height":480}})";
    assert(validObservation(good));
    auto wrongType = good;
    wrongType.replace("\"caption\":\"title\"", "\"caption\":{}");
    assert(!validObservation(wrongType));
    auto missingParent = good;
    missingParent.replace("\"parent\":null,", "");
    assert(!validObservation(missingParent));
    assert(!validObservation(R"({"type":"input","id":"a"})"));
    assert(!validObservation(R"({"type":"window","id":"a","kind":"normal","geometry":{"x":0,"y":0,"width":0,"height":480}})"));
    assert(!validObservation(QByteArray(65537, 'x')));
    assert(!validObservation(R"({"type":"closed","id":"a","command":"exec"})"));
    assert(validObservation(R"({"type":"active","id":null})"));
    assert(validObservation(R"({"type":"active","id":"{opaque-uuid}"})"));
    assert(!validObservation(R"({"type":"active"})"));
    assert(!validObservation(R"({"type":"active","id":false})"));
    assert(!validObservation(R"({"type":"active","id":7})"));
    assert(!validObservation(R"({"type":"active","id":[]})"));
    assert(!validObservation(R"({"type":"active","id":{}})"));
    assert(!validObservation(R"({"type":"active","id":""})"));
    assert(!validObservation(R"({"type":"active","id":"space id"})"));
    assert(!validObservation(R"({"type":"active","id":null,"command":"exec"})"));
    assert(!validObservation(R"({"type":"closed","id":null})"));
    assert(!validObservation(R"({"type":"closed"})"));
    auto nullWindow = good;
    nullWindow.replace("\"id\":\"a\"", "\"id\":null");
    assert(!validObservation(nullWindow));
    auto missingWindow = good;
    missingWindow.replace("\"id\":\"a\",", "");
    assert(!validObservation(missingWindow));
}
