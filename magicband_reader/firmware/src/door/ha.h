#pragma once
// Wi-Fi (WiFiManager, non-blocking), MQTT and Home Assistant discovery.
// Access control never waits on any of this: it keeps working offline.

#include <ArduinoJson.h>

void haBegin(bool forcePortal);
void haLoop();
bool haConnected();
const char *haDeviceId();
// Publishes to MQTT_BASE "/" sub.
void haPublish(const char *sub, const char *payload, bool retain = false);
void haPublishJson(const char *sub, const JsonDocument &doc, bool retain = false);
// Re-sends the discovery config (the user select's options change with the users).
void haPublishDiscovery();

// Implemented by main.cpp.
void appOnMqtt(const char *sub, const char *payload);  // sub = topic minus MQTT_BASE "/"
void appOnMqttConnected();                             // publish all retained state
void appUserOptions(JsonArray opts);                   // names for the user select
