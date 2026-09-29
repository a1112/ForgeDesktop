#include "payload.h"
#include <cassert>
int main() {
    assert(validObservation(R"({"type":"window","id":"a","kind":"normal","geometry":{"x":0,"y":0,"width":640,"height":480}})"));
    assert(!validObservation(R"({"type":"input","id":"a"})"));
    assert(!validObservation(R"({"type":"window","id":"a","kind":"normal","geometry":{"x":0,"y":0,"width":0,"height":480}})"));
    assert(!validObservation(QByteArray(65537, 'x')));
    assert(!validObservation(R"({"type":"closed","id":"a","command":"exec"})"));
}
