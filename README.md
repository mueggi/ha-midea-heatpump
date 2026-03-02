# Midea ATW Heat Pump - Home Assistant Integration

Custom [Home Assistant](https://www.home-assistant.io/) integration for Midea FlexFit ATW R32 air-to-water heat pumps (device type 0xC3). Communicates directly over LAN using the reverse-engineered M-Smart protocol — no cloud connection required.

## Supported Devices

Tested with:
- **Midea FlexFit ATW R32** (MZAU-28HWFN8-QD2W) with KJR-120J1/TFBG-E wired controller

Other Midea ATW heat pumps using device type 0xC3 may work but are untested.

## Entities

| Entity | Platform | Read | Write | Notes |
|--------|----------|------|-------|-------|
| DHW Water Heater | `water_heater` | Current + target temp | Target temp | Confirmed working |
| DHW Tank Temperature | `sensor` | Yes | - | Live sensor |
| Water Circuit Temperature | `sensor` | Yes | - | Live sensor |
| Outdoor Temperature | `sensor` | Yes | - | Live sensor |
| Zone 1 Target Temperature | `number` | - | Yes | Assumed state (untested) |
| Operating Mode | `select` | - | - | Stub (Heat / DHW / Heat+DHW) |
| ECO Mode | `switch` | - | Yes | Assumed state |
| Turbo DHW | `switch` | - | - | Stub |

**Assumed state** means HA tracks what was last sent but cannot read the value back from the device. **Stub** means the SET command hasn't been decoded yet — the entity only updates locally.

## Prerequisites

You need a **token** and **key** for your device. These are obtained from the Midea cloud API (NetHome Plus or MSmartHome) and are specific to your device. The companion CLI tool in [the heatpump project](https://github.com/mueggi/ha-midea-heatpump) can retrieve them:

```bash
# Example using the CLI tool (separate repo)
python midea_cli.py cloud-login --account you@example.com --password yourpass --save-config
```

The token and key are saved to `~/.midea_heatpump.json`. You'll enter them during the integration setup in Home Assistant.

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner and select **Custom repositories**
3. Add `https://github.com/mueggi/ha-midea-heatpump` with category **Integration**
4. Click **Install**
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/midea_heatpump/` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **Midea ATW Heat Pump**
3. Enter your connection details:
   - **IP Address** — LAN IP of the heat pump controller
   - **Port** — TCP port (default: 6444)
   - **Device ID** — numeric device ID from the cloud API
   - **Token** — hex string from cloud API
   - **Key** — hex string from cloud API
4. The integration validates the connection before saving. If it fails, check that the IP is reachable and the token/key are correct.

## How It Works

- Connects directly to the heat pump controller over TCP (port 6444)
- Uses the M-Smart 8370 protocol with AES encryption for the session
- Polls device status every 30 seconds via a persistent connection
- Auto-reconnects on connection failure
- All communication is local — no cloud dependency after obtaining the initial token/key

## Troubleshooting

**"Cannot connect to device"** during setup:
- Verify the heat pump controller is on your network (`ping <ip>`)
- Confirm port 6444 is reachable
- Double-check the token and key (they must be the hex strings, not base64)
- Try obtaining fresh token/key from the cloud API

**Entities show "unavailable":**
- Check Home Assistant logs for `midea_heatpump` errors
- The device may have dropped the TCP connection — it should auto-reconnect within 30s
- Power-cycling the heat pump controller can help if connections are stuck

**Temperature values seem wrong:**
- This device uses XC0 encoding (value = (raw - 50) / 2). If you see raw byte values instead of temperatures, something went wrong with the response parsing.

## License

MIT
