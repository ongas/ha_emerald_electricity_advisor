# Emerald Electricity Advisor - Home Assistant Integration

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)

An unofficial Home Assistant integration for [Emerald Electricity Advisor](https://www.emeraldenergy.com.au/), providing seamless control and monitoring of your Emerald energy management devices.

## Features

- 🔐 Secure authentication with your Emerald account
- 📊 Real-time device status and information
- 🔄 Automatic device discovery
- 🎯 Easy integration with Home Assistant automations and dashboards
- ⚡ Async support for optimal performance

## Installation

### Via HACS (Recommended)

1. Open Home Assistant
2. Go to **Settings** → **Devices & Services**
3. Click **⤵️ Create Automation** in the bottom right
4. Search for **Emerald Electricity Advisor**
5. Click **Install**
6. Restart Home Assistant

### Manual Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/ongas/ha_emerald_electricity_advisor.git
   ```

2. Copy the `custom_components/emerald_electricity_advisor` folder to your Home Assistant's `custom_components/` directory

3. Restart Home Assistant

## Configuration

After installation:

1. Go to **Settings** → **Devices & Services**
2. Click **+ Create Automation**
3. Search for **Emerald Electricity Advisor**
4. Enter your Emerald account credentials (email and password)
5. Authorize device discovery

The integration will automatically create sensor entities for each of your Emerald devices.

## Available Sensors

- **Status**: Current operational status of your device
- **Portal URL**: Direct link to your device in the Emerald portal

Additional sensor types are added based on API data availability.

## Usage Examples

### Display Device Status

```yaml
type: entities
entities:
  - entity: sensor.my_device_status
  - entity: sensor.my_device_url
```

### Automation: Device Status Change Notification

```yaml
automation:
  - alias: "Notify on Device Status Change"
    trigger:
      platform: state
      entity_id: sensor.my_device_status
    action:
      service: notify.mobile_app_phone
      data:
        title: "Emerald Device Status"
        message: "Status changed to {{ states('sensor.my_device_status') }}"
```

## Troubleshooting

### Invalid Authentication Error

- Verify your Emerald email and password are correct
- Try resetting your Emerald account password
- Check if your account has active Emerald devices

### No Devices Found

- Ensure your Emerald account has devices associated with it
- Verify you're using the correct login credentials
- Check Emerald's website to confirm device registration

### Integration Won't Load

- Check Home Assistant logs for detailed error messages
- Ensure you're running Home Assistant 2023.08 or later
- Try restarting Home Assistant

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration. It is not affiliated with or endorsed by Emerald Energy or Emerald Electricity. Use at your own risk.

## Support

For issues, feature requests, or questions:
- [GitHub Issues](https://github.com/ongas/ha_emerald_electricity_advisor/issues)

## Changelog

### Version 1.0.0
- Initial release
- Device discovery
- Status and URL sensors
- Full authentication support
