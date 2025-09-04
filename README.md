# team05-mcp-server
MCP server and supporting server(s) for communicating with the TEAM 0.5 Transmission Electron Microscope

# mcp_library.py
The set of MCP tools made available. This should be run on the support PC and have access to the microscope PC and the Gatan PC.

# microscope_server.py
The zeroMQ based server that communicates with the mciroscope scritping interface, the CEOS RPC gateway (for aberration correction), and the TIA (ESVision) STEM acquisition software.

# gatan_server.py (to be added)
The zeroMQ based server that communicates with the Gatan Digital Micrograph software on the Gatan PC. This server is based on the "mulitscan_server" and not in the repo yet.