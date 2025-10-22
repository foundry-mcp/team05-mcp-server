# team05-mcp-server
MCP server and supporting server(s) for communicating with the TEAM 0.5 Transmission Electron Microscope

# mcp_library.py
A set of MCP tools run on the support PC. It communicates with the micro_server.py on the microscope PC and the gata_server.py on the Gatan PC.

This currently is started using the beacon_311 conda envireonment on the support PC.

# microscope_server.py
The zeroMQ based server that communicates with the microscope scripting interface, the CEOS RPC gateway (for aberration correction), and the TIA (ESVision) STEM acquisition software.

This is run on the TEAM 0.5 microscope PC using the winpython 3.4 command prompt.

# gatan_server.py
The zeroMQ based server that communicates with the Gatan Digital Micrograph software on the Gatan PC. This server writes templated .s scripts and executes them in DM. It relies on the dm_scripts.py to write the templates.

This is run on the Gatan PC. Currently there is a w7server shortcut being used, but that is old. We need to update to this version.

# mcp_distiller.py
A MCP agent that can get information from the Distiller database. You can get a range of scan_ids or data from a specific data set id.

This is run on the support PC using a anaconda environment called team05-mcp.

# 4Dcamera_commands_mcp.py
This can communicate with the 4D Camera backend. Its useful for getting and setting the tmemperature and other various commands. It is designed for troublehsooting and maintenance, not experiments.

This is run on Morgan's computer.

# mcp_ncempy.py
A MCP agent that can read the EMD files saved to the support PC. This also has a GUI that will show the data in a matplotlib plot.

This is run on the support PC using an anaconda environment called team05-mpc(?).