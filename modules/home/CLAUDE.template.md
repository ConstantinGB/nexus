# {project_name} — Home

This project manages a Home Assistant (HA) installation and smart-home automation. The AI
helps write automations and scripts in YAML, design Lovelace dashboards, configure device
integrations, and debug configuration errors.

## Key software

- **Home Assistant** — core platform; config at `~/.homeassistant/` or `/config/` in Docker
- **HACS** — community store for integrations and Lovelace cards; installed via HA UI
- **Mosquitto** — MQTT broker for Zigbee2MQTT and other MQTT devices; default port 1883
- **Zigbee2MQTT** — Zigbee coordinator → MQTT bridge; config at `data/configuration.yaml`
- **ZHA** — Zigbee Home Automation built into HA; simpler alternative to Zigbee2MQTT
- **ESPHome** — custom firmware for ESP8266/ESP32: `esphome run device.yaml`
- **Node-RED** — visual automation editor; available as HA addon
- **AppDaemon** — Python-based automation for complex logic; runs as HA addon

## Home Assistant core config files

| File | Purpose |
|------|---------|
| `configuration.yaml` | Main config; references other files via `!include` |
| `automations.yaml` | Automation list |
| `scripts.yaml` | Reusable action sequences |
| `scenes.yaml` | Named snapshots of entity states |
| `secrets.yaml` | Credentials referenced as `!secret key_name` |
| `customize.yaml` | Friendly names, icons, hidden flags |
| `ui-lovelace.yaml` | Dashboard YAML (only if Storage Mode is off) |

## Automation structure

```yaml
alias: "Turn off lights at midnight"
description: ""
trigger:
  - platform: time
    at: "00:00:00"
condition:
  - condition: state
    entity_id: person.owner
    state: home
action:
  - service: light.turn_off
    target:
      area_id: living_room
mode: single
```

## Typical tasks

- Write time-based, presence-based, and sensor-triggered automations
- Create reusable scripts for repeated action sequences
- Design Lovelace dashboard YAML (cards: `entities`, `gauge`, `map`, `picture-glance`, `custom:mushroom-*`)
- Write ESPHome YAML for new DIY devices (temperature sensors, LED strips, buttons)
- Debug `configuration.yaml` errors from HA logs (`Settings → System → Logs`)
- Configure a new Zigbee or WiFi device integration
- Write Jinja2 template sensors for derived values

## Jinja2 template reference

```yaml
# Current state of an entity
{{ states('sensor.living_room_temperature') }}
# Attribute value
{{ state_attr('climate.living_room', 'current_temperature') }}
# Numeric maths
{{ (states('sensor.power_w') | float * 0.001) | round(2) }} kW
# Conditional
{% if is_state('binary_sensor.front_door', 'on') %}open{% else %}closed{% endif %}
# Time
{{ now().strftime('%H:%M') }}
```

---

## Your setup

<!-- Home Assistant URL: e.g. http://homeassistant.local:8123 or http://192.168.1.10:8123 -->

<!-- HA version: e.g. 2024.11 -->

<!-- Zigbee setup: ZHA / Zigbee2MQTT / none
     Coordinator hardware: e.g. Sonoff Zigbee 3.0 USB Dongle Plus, ConBee II -->

<!-- MQTT broker: Mosquitto addon / separate host / none -->

<!-- Device inventory (types and protocols):
     e.g.
     - Philips Hue bulbs (Zigbee via ZHA)
     - Shelly 1PM plugs (WiFi, native HA integration)
     - Aqara temperature sensors (Zigbee)
     - Sonos speakers (WiFi) -->

<!-- ESPHome devices (if any):
     e.g. garage temperature/humidity sensor (DHT22), RGB LED strip controller -->

<!-- Automation goals:
     e.g. presence-based lighting, morning wake-up routine, energy monitoring -->

## Notes for the AI

<!-- Integration quirks, entity naming conventions, areas already defined in HA,
     automations that must not be modified, or energy tariff details for cost calculations. -->
