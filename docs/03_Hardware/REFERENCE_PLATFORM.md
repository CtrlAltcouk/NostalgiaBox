# Reference Hardware Platform

## Status

Confirmed initial hardware platform for NostalgiaBox version 1 development.

## Base computer

- **Manufacturer:** Dell
- **Model:** OptiPlex 7050 Micro Form Factor
- **Processor:** Intel Core i5-7500T
- **Installed memory:** 8 GB DDR4 SODIMM as purchased
- **Planned memory:** 16 GB DDR4 SODIMM after compatibility testing of the additional 8 GB module
- **Storage:** 256 GB SSD
- **Power supply:** Dell external power adapter supplied with the computer
- **Video output:** DisplayPort on the purchased configuration; exact adapter or cable to be selected after television compatibility is checked
- **Operating system supplied:** Windows 10 Pro
- **Planned operating system:** TBD by architecture decision

## Why this platform was selected

- Available at a reasonable used-market cost
- Compact one-litre-class chassis suitable for a set-top-box enclosure
- Sufficient CPU and integrated graphics capability for the intended 1080p interface and media playback
- Business-grade construction and serviceability
- Replaceable memory and storage
- External power supply reduces enclosure heat and mains-voltage complexity
- Existing metal chassis, fan and airflow path can remain intact inside a decorative enclosure

## Enclosure strategy

The current preferred approach is to retain the complete Dell chassis and design a non-structural outer enclosure or fascia around it.

This avoids unnecessarily redesigning:

- CPU cooling
- airflow
- electrical grounding
- electromagnetic shielding
- motherboard mounting
- storage mounting
- power-button wiring

The enclosure must not obstruct the Dell air intake or exhaust. Final clearances will be based on measurements from the delivered unit.

## Items still to confirm

- Exact existing RAM module manufacturer, capacity, speed and rank
- Compatibility of the additional 8 GB DDR4 SODIMM
- SSD make, model, interface and health
- Power-adapter wattage and condition
- Installed Wi-Fi and Bluetooth hardware, if any
- Available rear video connectors
- BIOS version and configuration
- Hardware-decoding support under the selected operating system
- Idle and playback temperatures
- Acoustic performance
- Television HDMI compatibility through the chosen DisplayPort adapter

## Hardware arrival checklist

1. Photograph all sides, labels, ports, power adapter and internal layout.
2. Check chassis damage, missing screws and blocked ventilation.
3. Record the service tag privately; do not publish it in the repository.
4. Boot the supplied operating system before wiping the drive.
5. Confirm CPU, RAM, storage and network hardware match the listing.
6. Run Dell onboard diagnostics.
7. Record SSD SMART health.
8. Test all USB, network, audio and video outputs.
9. Check fan noise and temperatures at idle and during video playback.
10. Install the additional RAM only after confirming compatibility.
11. Run an extended memory test after installation.
12. Update this document with confirmed specifications and measurements.

## Upgrade policy

Upgrades should solve a documented requirement rather than being added speculatively. The initial 256 GB SSD is intended for the operating system, application and a small test library. The long-term media-storage design remains undecided.
