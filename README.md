# 🛠️ OpenCore Helper

> A modular Python toolkit for hardware analysis, compatibility checking, diagnostics and OpenCore utilities.

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-yellow.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Development-orange.svg)]()

---

## 🚀 About

**OpenCore Helper** is an independent Python project designed to simplify hardware analysis, system diagnostics and OpenCore-related workflows.

The project uses a modular architecture, keeping each feature separated into its own component.

The main goal is to provide useful information before the user makes changes to their boot environment.

---

## ✨ Features

- 🖥️ Hardware detection
- 🔍 OpenCore Hardware Verifier (OHV)
- ⚙️ Compatibility analysis
- 📦 EFI management
- 🧩 `config.plist` validation
- 🍎 macOS version catalog
- 💿 Recovery management
- 🩺 System diagnostics
- 💾 Backup management
- 📊 JSON, TXT and HTML reports
- 📥 Download management
- 🔧 Tool detection
- 🔐 File hashing
- ⚙️ Process utilities
- 🌎 Multilingual support
- 🚀 Bootloader workspace preparation

---

## 🔍 OpenCore Hardware Verifier

The **OpenCore Hardware Verifier**, or **OHV**, is the hardware analysis system of OpenCore Helper.

It analyzes detected components and provides information such as:

- CPU
- GPU
- RAM
- Motherboard
- BIOS
- Storage
- Network
- Audio
- Architecture
- Operating system

The result can include:

- 🟢 Compatible
- 🟡 Warning
- 🔴 Unsupported
- 🔵 Information
- 💡 Recommendations

> OHV provides guidance and does not guarantee that a specific hardware configuration will run macOS successfully.

---

## 🖥️ Hardware Detection

OpenCore Helper can detect information about:

- CPU
- GPU
- Memory
- Motherboard
- Storage
- Network adapters
- Audio devices
- Operating system

The detection system uses platform-specific methods when available.

---

## ⚙️ Compatibility

The compatibility engine evaluates the detected system and generates a structured report.

Example:

```text
Compatibility Score: 82/100
Status: WARNING

CPU        ✓
GPU        ✓
RAM        ✓
Network    ⚠
Audio      ✓
Storage    ✓
