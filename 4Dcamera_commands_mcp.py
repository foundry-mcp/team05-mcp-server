
import os
import socket
import paramiko
from fastmcp import FastMCP
import numpy as np
import yaml
from numpy.typing import NDArray
import base64
from dotenv import load_dotenv

mcp = FastMCP("4Dcamera")

# Load environment variables from .env file
load_dotenv()
# Define the server's IP address and port
server_host = os.getenv("SRV_HOST") # the address of the server to send the commands
server_user = os.getenv("SRV_USR") # the username to log into the server
server_pwd = os.getenv("SRV_PWD")
server_port = os.getenv("SRV_PORT") # the port to send the commands to
# 4D Camera head IP address and credentials
camera_ip = os.getenv("CAM_IP") # the camera head IP
camera_usr = os.getenv("CAM_USR")
camera_pwd = os.getenv("CAM_PWD2")

def ssh_connect_with_password(hostname, username, password, command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(hostname, username=username, password=password)
        stdin, stdout, stderr = client.exec_command(command)
        result = stdout.read().decode()
        error = stderr.read().decode()
        print(result)
        print(error)
        return result
    except Exception as e:
        error_msg = f"SSH connection failed: {str(e)}"
        print(error_msg)
        return error_msg
    finally:
        client.close()

def send_command(content):
    """ This function takes in a string as a command to the 4D Camera. 
    Parameters
    ----------
    content : str
        The command to send to the 4D Camera server as a string.
    """
    # status_text.delete('1.0', tk.END)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"# ============ {s=}")
    s.connect((server_host, int(server_port)))
    s.sendall(content.encode())
    s.shutdown(socket.SHUT_WR)
    while True:
        data = s.recv(4096)
        if not data:
            break
        print(str(data.decode()))

    s.close()


@mcp.tool()
def on_new_dark(mode=2, threshold=0, offset=20):
    """This function acquires a new dark image for the camera. It has 
    inputs that allow you to modify the final image such as a threshold, 
    and offset. 
    
    Parameters
    ----------
    mode : int
        The mode can be either 0, 1, or 2
        0 - the dark subtraction is turned off
        1 - the dak subtraction is turned on
        2 - a new dark image is acquired and then dark subtraction is turned on
    threshold : int
        All values below this integer will automatically be set to 0.
    offset : int
        An offset to apply to every image. Typically this is 20 to allow the
        full Gaussian noise profile to be shown in a uint16 dataset.
    """
    content = f"enabledarkfieldsub {mode} {threshold} {offset}"
    send_command(content)

@mcp.tool()
def on_resync():
    """The function bound to the Resync GUI button. This will run the syncing routine
    on the camera head which aligns all of the columns. It will also reset the scan number."""
    content = "resync"
    send_command(content)

@mcp.tool()
def on_power_down():
    """The function bound to the Power down GUI button. This will run the power down
    script on the camera head effectively shutting down the camera."""
    content = "powerdowncamera"
    send_command(content)

@mcp.tool()
def on_power_up(confirm=None, set_temperature=None):
    """The function bound to the Power Up GUI button. This will run the power up script
    on the camera head. This will start up the camera so it is ready for operation. If the
    keywords are not supplied then confirmation pop up windws are shown.

    Parameters
    ----------
    confirm : bool
        Set this to True to skip the confirmation box to power up the camera
    set_temperature : bool
        Set this to True to skip the confirmation box to set the sensor temperature to 19C after
        powering up. Otherwise, the temperature is set to -10C and cooling fails.
    """
    if confirm:
        content = "powerupcamera"
        send_command(content)

    if set_temperature:
        content = f"setsensortemperature 19"
        send_command(content)

@mcp.tool()
def on_set_temperature(temperature=None):
    """The function bound to the Set temperature GUI button. It reads the 
    temperature input from a text box and sets the camera temperautre. If
    the temperature keyword is set then it uses that temperature. The 
    temperature is in celsius."""
    content = f"setsensortemperature {temperature}"
    send_command(content)

@mcp.tool()
def on_get_temperature():
    """This reads the temperature from the sensor. Only the Q1 temperature is important. This parses
    the output from the sensor and returns only the needed value in celsius."""
    command1 = f"echo \"dsh sensor temp\" | sshpass -p {camera_pwd} ssh -T -o HostKeyAlgorithms=ssh-rsa {camera_usr}@{camera_ip}"
    print(command1)
    rr = ssh_connect_with_password(server_host, server_user, server_pwd, command1)
    return(rr)

@mcp.tool()
def start_stem_scan(width, height, npause=0, nread=1, flyback=300, write=1):
    '''Take a stem scan'''
    command = f"startstemscan {npause} {nread} {width} {height} {flyback} {write}"
    send_command(command)

@mcp.tool()
def insert_camera():
    ''' Insert camera into beam path.'''
    send_command('insertcamera')


@mcp.tool()
def retract_camera():
    '''Retract camera from beam path.'''
    send_command('retractcamera')



if __name__ == "__main__":
    mcp.run(transport = "http", port = 8000)