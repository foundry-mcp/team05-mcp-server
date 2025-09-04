# -*- coding: utf-8 -*-
"""
A MCP agent that can talk to the Distiller database.

@author: Peter Ercius, Alex Pattison, Morgan Wall
"""

from fastmcp import FastMCP
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from pydantic import AnyHttpUrl, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests.exceptions import HTTPError, RequestException

import numpy as np
import time
import argparse

mcp = FastMCP("DigitalMicrographController")
    
class Settings(BaseSettings):
    """ Settings for communicating with the Disitller API. The .env file
    will contain the necessary secrets."""
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)
    API_URL: AnyHttpUrl
    API_KEY_NAME: str
    API_KEY: str

settings = Settings() # API_URL = "https://fake.lbl.gov/api", API_KEY_NAME="fake", API_KEY='fake')  # type: ignore

class Location(BaseModel):
    """The location of a data set. If host is perlmutter then
    the streaming operation is finished. The path is the path to the data.
    
    Attributes
    ----------
    host : str
        The name of the host where the data is located. e.g. Perlmutter
    path : str
        The file path on the host to where the data is located.
    """
    host: str  # you'll look for host = perlmutter
    path: str

class Scan(BaseModel):
    """Information about a scan captured in the Distiller system.
    
    A Scan contains metadata and location data from a 4D Camera dataset,
    including identifiers for both the Distiller system. Each scan tracks
    multiple location points and maintains creation timestamp information.
    
    Attributes
    ----------
    id : int
        Unique identifier for the scan within the Distiller system.
    scan_id : int, optional
        Identifier from the 4D camera system. May be None if the scan
        was not captured using 4D camera equipment.
    locations : list[Location]
        List of Location objects representing spatial data points
        captured during the scan.
    created : datetime
        Timestamp indicating when the scan was created.
    image_path : str, optional
        File path to an associated image. Defaults to None if no image
        is stored with the scan.
    metadata : dict, optional
        The metadata for the scan.
    notes : str, optional
        Notes from Distiller
    """
    id: int  # distiller id
    scan_id: Optional[int]  # scan id from 4d camera
    locations: list[Location]
    created: datetime
    image_path: Optional[str] = None
    notes: Optional[str]
    metadata: Optional[dict[str, Any]]# = Field(alias="metadata_")

@mcp.tool()
def get_scan_by_id(distiller_scan_id: int):
    """ Get information about a data set in Distiller based 
    on the Distiller ID number
    
    Parameters
    ----------
    distiller_scan_id : int
        The Disitller scan id. This is a unique ID attached to each data set in the database.
    
    Returns
    -------
    : Scan
        Returns a Scan class with information like the 
    """
    headers = {
        settings.API_KEY_NAME: settings.API_KEY,
        "Content-Type": "application/json",
    }

    url = f"{settings.API_URL}/scans/{distiller_scan_id}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        json_data = response.json()
        return Scan(**json_data)
    except HTTPError as http_err:
        raise HTTPError(f"HTTP error occurred: {http_err}")
    except RequestException as req_err:
        raise RequestException(f"Request exception occurred: {req_err}")

@mcp.tool()
def get_scans(
    skip: int = 0,
    limit: int = 100,
    scan_id: int = -1,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    job_id: Optional[int] = None,
) -> list[Scan]:
    """
    Fetch a list of scans with various filter options.

    Parameters:
        skip (int): Number of records to skip.
        limit (int): Maximum number of records to return.
        scan_id (int): Specific scan ID to filter by.
        start (Optional[datetime]): Start of the date range for creation time.
        end (Optional[datetime]): End of the date range for creation time.
        job_id (Optional[int]): Job ID to filter by.

    Returns:
        List[Scan]: A list of Scan objects matching the criteria.

    Raises:
        HTTPError: If the request fails due to an HTTP error.
        RequestException: For any other request-related errors.
    """
    headers = {
        settings.API_KEY_NAME: settings.API_KEY,
        "Content-Type": "application/json",
    }

    params: dict[str, Any] = {
        "skip": skip,
        "limit": limit,
    }

    if scan_id != -1:
        params["scan_id"] = scan_id
    if start is not None:
        params["start"] = start.isoformat()
    if end is not None:
        params["end"] = end.isoformat()
    if job_id is not None:
        params["job_id"] = job_id

    url = f"{settings.API_URL}/scans"

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        json_data = response.json()
        return [Scan(**scan_data) for scan_data in json_data]
    except HTTPError as http_err:
        raise HTTPError(f"HTTP error occurred: {http_err}")
    except RequestException as req_err:
        raise RequestException(f"Request exception occurred: {req_err}")
    
@mcp.tool()
def distiller_greet_me(username):
    """Function to say hello to a user who wants to access Distiller"""
    return f'hello {username}. What do you want to get from Distiller?'

def get_scan_by_id_old(distiller_scan_id: int):
    """ Get information about a data set in Distiller based 
    on the Distiller ID number
    
    NON MCP version for testing
    
    Parameters
    ----------
    distiller_scan_id : int
        The Disitller scan id. This is a unique ID attached to each data set in the database.
    
    Returns
    -------
    : Scan
        Returns a Scan class with information like the 
    """
    headers = {
        settings.API_KEY_NAME: settings.API_KEY,
        "Content-Type": "application/json",
    }

    url = f"{settings.API_URL}/scans/{distiller_scan_id}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        json_data = response.json()
        #print(json_data)
        return Scan(**json_data)
    except HTTPError as http_err:
        raise HTTPError(f"HTTP error occurred: {http_err}")
    except RequestException as req_err:
        raise RequestException(f"Request exception occurred: {req_err}")

if __name__ == "__main__":
    # mcp.run(transport = "sse", host = "team05-support.dhcp.lbl.gov", port = 8080)
    #mcp.run(transport="sse", host="131.243.3.204", port="8080")
    
    # Test getting information from Distiller
    aa = get_scan_by_id_old(distiller_scan_id=35155)
    print(f'Screen current = {aa.metadata['Screen current']}')
    print(f'notes = {aa.notes}')
    
    