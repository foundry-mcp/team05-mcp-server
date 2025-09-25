# team05-mcp-server
MCP server and supporting server(s) for communicating with the TEAM 0.5 Transmission Electron Microscope

# mcp_library.py
The set of MCP tools made available. This should be run on the support PC and have access to the microscope PC and the Gatan PC.

This currently is started using the beacon_311 conda envireonment on the support PC.

# microscope_server.py
The zeroMQ based server that communicates with the microscope scripting interface, the CEOS RPC gateway (for aberration correction), and the TIA (ESVision) STEM acquisition software.

This is run on the team 0.5 microscope PC usoing the winpython 3.4 command prompt.

# gatan_server.py
The zeroMQ based server that communicates with the Gatan Digital Micrograph software on the Gatan PC. This server writes templated .s scripts and executes them in DM. It relies on the dm_script.py and mb_script.py to write the templates.

This is run on the gatan PC. Currently there is a w7server shortcut being used, but that is old. We need to update to this version.

# mcp_distiller.py
A MCP agent that can get data from the Distiller database. You can get a range of scan_ids or data from a specific data set id.

This is run on the support PC using a anaconda environment called team05-mcp.

# 4Dcamera_commands_mcp.py
This can communicate with the 4D Camera backend. Its useful for getting and setting the tmemperature and other various commands. It is designed for troublehsooting and maintenance, not experiments.

This is run on Morgan's computer.
