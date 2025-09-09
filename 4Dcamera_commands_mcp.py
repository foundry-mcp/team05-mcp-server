
import os
import socket
import paramiko
from fastmcp import FastMCP
import numpy as np
import yaml
from numpy.typing import NDArray
import base64
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

mcp = FastMCP("4Dcamera")

# Define the server's IP address and port
host = os.getenv("CAM_HOST") # the address of the server to send the commands
port = os.getenv("CAM_PORT") # the port to send the commands to
ip = os.getenv("CAM_IP")

'''
This is a set of tools for communicating with the 4Dcamera

'''


def ssh_connect_with_password(hostname, username, password, command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(hostname, username=username, password=password)
        stdin, stdout, stderr = client.exec_command(command)
        result = stdout.read().decode()
        print(stdout.read().decode())
        print(stderr.read().decode())
        return result
    finally:
        client.close()



@mcp.tool()
def greet_user(username):
    ''' this function greets a user by name '''
    return f'hello {username}'


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
    s.connect((host, int(port)))
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
    if temperature:
        temp = temperature
    else:
        temp = temperature.get() # new temperature in GUI
    content = f"setsensortemperature {temp}"
    send_command(content)

@mcp.tool()
def on_get_temperature():
    """This reads the temperature from the sensor. Only the Q1 temperature is important. This parses
    the output from the sensor and returns only the needed value in celsius."""
    for_vfdaq = os.getenv('for_vfdaq') # `set for_vfdaq=` or `export for_vfdaq=`
    command1 = f"echo \"dsh sensor temp\" | sshpass -e ssh -T -o HostKeyAlgorithms=ssh-rsa root@{ip}"
    rr = ssh_connect_with_password('vfdaq.lbl.gov', 'daquser', for_vfdaq, command1)
    return(rr)
    #Q1_temp = rr.stdout.split("\n")[0]

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