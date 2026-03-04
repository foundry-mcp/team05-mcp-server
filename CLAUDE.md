# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository contains MCP (Model Context Protocol) servers and supporting communication servers for operating the TEAM 0.5 Transmission Electron Microscope. The system uses a distributed architecture with multiple servers running on different PCs that communicate via ZeroMQ.

## Testing

Run individual test files to verify server functionality:

```bash
# Test microscope server commands
python test_microscope_client.py --host localhost --port 7001

# Test Gatan server commands
python test_gatan_server.py
```

## Architecture

### Multi-PC Distributed System

The system consists of three main components running on separate machines:

1. **Support PC** - Runs `mcp_library.py` with the FastMCP server
2. **Microscope PC** - Runs `microscope_server.py` (ZeroMQ server on port 7001)
3. **Gatan PC** - Runs `gatan_server.py` (ZeroMQ server on port 13579)

### Network Configuration

- Microscope PC: `192.168.0.24:7001`
- Gatan PC: `192.168.0.30:13579`
- Support PC hosts MCP server at `team05-support.dhcp.lbl.gov:8080`

### Communication Flow

```
MCP Client (Claude/AI)
    ↓ (SSE/FastMCP)
mcp_library.py (Support PC)
    ↓ (ZeroMQ)
    ├─→ microscope_server.py (Microscope PC)
    │       ├─→ TEMScripting COM interface
    │       ├─→ TIA/ESVision STEM acquisition
    │       └─→ CEOS RPC gateway (port 7072) for aberration correction
    └─→ gatan_server.py (Gatan PC)
            └─→ Digital Micrograph via generated .s scripts
```

### Key Components

**mcp_library.py**: Main MCP server exposing tools to AI clients. Contains `Microscope_Client` and `Gatan_Client` classes that communicate with the respective servers via ZeroMQ. Runs in `beacon_311` conda environment on Support PC.

**microscope_server.py**: ZeroMQ server with three main classes:
- `CorrectorCommands` - Communicates with CEOS RPC gateway for aberration correction
- `MicroscopeControl` - Interfaces with TEMScripting and TIA via COM objects
- `MicroscopeServer` - Main server loop handling requests

Runs using WinPython 3.4 on Microscope PC.

**gatan_server.py**: ZeroMQ server that dynamically generates Digital Micrograph scripts using templates from `dm_scripts.py`, writes them to `C:/Users/VALUEDGATANCUSTOMER/Documents/automation/`, and executes them via subprocess calls to DigitalMicrograph.exe. Runs using globally installed Python on Gatan PC.

**dm_scripts.py**: Template generator for Digital Micrograph .s scripts. Functions return formatted script strings with parameters for 4D Camera acquisition, STEM scans, and beam movements.

**4Dcamera_commands_mcp.py**: Standalone MCP server for direct communication with 4D Camera backend (maintenance/troubleshooting). Requires `4dcam-mcp-env-requirements.txt` dependencies.

**mcp_distiller.py**: MCP agent for interacting with the Distiller database - retrieves scan data, adds notes and metadata. Runs in `team05-mcp` conda environment.

**mcp_ncempy.py**: MCP agent for reading EMD files and displaying data via matplotlib. Runs in `team05-mcp` conda environment.

### Python Environment Dependencies

The Support PC uses hardcoded paths to external dependencies:
- BEACON client: `D:/user_data/Pattison/BEACON` (see mcp_library.py:47)
- Files copied to Gatan PC: Local `Documents/automation` folder

### Communication Protocol

All ZeroMQ servers use REQ-REP pattern with pickled Python dictionaries:
- Request format: `{'type': 'command_name', ...params}`
- Response format: `{'reply_data': result, ...metadata}`

Gatan server uses tuple format: `(command_string, params_dict)`

### Data Storage

4D-STEM and HAADF data written to EMD (HDF5) format with metadata from `get_metadata()`. The `write_emd_data()` function in mcp_library.py handles file creation with proper dimension datasets and microscope metadata.

## Important Parameters

See `TEAM0.5_Parameters.md` for:
- STEM optimal lens settings by voltage (50-300kV)
- HAADF collection semi-angles for different camera lengths
- 4D Camera calibrations
- Dwell time optimization (flyback time = 3.6ms, trigger = 16.6ms at 60Hz)

This file is exposed as an MCP resource at `file://TEAM0.5_Parameters.md`.
