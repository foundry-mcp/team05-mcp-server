# -*- coding: utf-8 -*-
"""
A MCP agent that can talk to the Distiller database.

@author: Peter Ercius, Alex Pattison, Morgan Wall
"""

from fastmcp import FastMCP
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import requests
from pydantic import AnyHttpUrl, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests.exceptions import HTTPError, RequestException

import numpy as np
import time
import argparse

mcp = FastMCP("DistillerController")
    
class Settings(BaseSettings):
    """ Settings for communicating with the Disitller API. The .env file
    will contain the necessary secrets."""
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra='ignore')
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

class JobType(str, Enum):
    """The kind of processing job that can be submitted to Distiller."""
    TRANSFER = "transfer"
    COUNT = "count"
    STREAMING = "streaming"

class JobState(str, Enum):
    """Slurm-derived state of a Distiller job."""
    INITIALIZING = "INITIALIZING"
    BOOT_FAIL = "BOOT_FAIL"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    CONFIGURING = "CONFIGURING"
    DEADLINE = "DEADLINE"
    FAILED = "FAILED"
    NODE_FAIL = "NODE_FAIL"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    REQUEUE_FED = "REQUEUE_FED"
    REQUEUED = "REQUEUED"
    REVOKED = "REVOKED"
    SPECIAL_EXIT = "SPECIAL_EXIT"
    STOPPED = "STOPPED"
    SUSPENDED = "SUSPENDED"
    TIMEOUT = "TIMEOUT"

class Job(BaseModel):
    """A processing job submitted to a compute machine (e.g. Perlmutter)
    to act on one or more scans.

    Attributes
    ----------
    id : int
        Unique identifier for the job within the Distiller system.
    job_type : JobType
        The kind of job, e.g. "count" for 4D Camera frame counting.
    scan_ids : list[int], optional
        The Distiller scan ids this job operates on.
    machine : str
        The compute machine the job runs on, e.g. "perlmutter".
    slurm_id : int, optional
        The Slurm job id once the job has been submitted to the scheduler.
    state : JobState
        Current state of the job.
    params : dict
        Job-type-specific parameters, e.g. {"threshold": 4.5, "darkfield": "none"}
        for a count job.
    output : str, optional
        Captured stdout/stderr from the job, once available.
    elapsed : float, optional
        Elapsed run time in seconds.
    submit : datetime, optional
        Time the job was submitted.
    notes : str, optional
        Notes about the job.
    """
    id: int
    job_type: JobType
    scan_ids: Optional[list[int]] = None
    machine: str
    slurm_id: Optional[int] = None
    state: JobState = JobState.INITIALIZING
    params: dict[str, Any]
    output: Optional[str] = None
    elapsed: Optional[float] = None
    submit: Optional[datetime] = None
    notes: Optional[str] = None

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

@mcp.tool()
def put_note(distiller_scan_id: int, note: str):
    """ Set the note field in Distiller. This can be used to 
    save extra data about a 4D STEM scan.
    
    NON MCP version for testing
    
    Parameters
    ----------
    distiller_scan_id : int
        The Disitller scan id. This is a unique ID attached to each data set in the database.
    note : str
        The information to store in the notes section of Distiller
        
    Returns
    -------
    None
    """
    import json
    headers = {
        settings.API_KEY_NAME: settings.API_KEY,
        "Content-Type": "application/json",
    }

    url = f"{settings.API_URL}/scans/{distiller_scan_id}"

    try:
        response = requests.patch(url, headers=headers, data=json.dumps({'notes':note}))
        response.raise_for_status()
        json_data = response.json()
        print(json_data)
        return Scan(**json_data)
    except HTTPError as http_err:
        raise HTTPError(f"HTTP error occurred: {http_err}")
    except RequestException as req_err:
        raise RequestException(f"Request exception occurred: {req_err}")

@mcp.tool()
def add_metadata(distiller_scan_id: int, metadata: dict[str, Any]):
    """ Update the metadata field in Distiller. This can be used to
    store updated or supplemental metadata for a 4D STEM scan.

    Parameters
    ----------
    distiller_scan_id : int
        The Disitller scan id. This is a unique ID attached to each data set in the database.
    metadata : dict
        The metadata to merge into the existing metadata field in Distiller.

    Returns
    -------
    : Scan
        A Scan class object with information about the scan that was changed
    """
    import json
    headers = {
        settings.API_KEY_NAME: settings.API_KEY,
        "Content-Type": "application/json",
    }

    url = f"{settings.API_URL}/scans/{distiller_scan_id}"
    params = {"merge": True}

    try:
        response = requests.patch(
            url,
            headers=headers,
            params=params,
            data=json.dumps({"metadata": metadata}),
        )
        response.raise_for_status()
        json_data = response.json()
        print(json_data)
        return Scan(**json_data)
    except HTTPError as http_err:
        raise HTTPError(f"HTTP error occurred: {http_err}")
    except RequestException as req_err:
        raise RequestException(f"Request exception occurred: {req_err}")

@mcp.tool()
def run_count_job(
    distiller_scan_id: int,
    threshold: float = 4.5,
    darkfield: str = "none",
    machine: str = "perlmutter",
) -> Job:
    """ Submit a "count" job to Distiller for a 4D Camera scan. This runs
    electron-counting on the raw frames for the given scan on the named
    compute machine.

    Parameters
    ----------
    distiller_scan_id : int
        The Distiller scan id to run the count job on.
    threshold : float
        Counting threshold, in the same units Distiller already uses for
        this parameter. Defaults to 4.5, the value used by prior count jobs.
    darkfield : str
        Darkfield correction mode, e.g. "none". Defaults to "none", the value
        used by prior count jobs.
    machine : str
        The compute machine to submit the job to. Defaults to "perlmutter",
        the only machine currently registered in Distiller.

    Returns
    -------
    : Job
        The newly created Job, including its Distiller id and initial state.
    """
    import json
    headers = {
        settings.API_KEY_NAME: settings.API_KEY,
        "Content-Type": "application/json",
    }

    url = f"{settings.API_URL}/jobs"
    body = {
        "job_type": JobType.COUNT.value,
        "scan_id": distiller_scan_id,
        "machine": machine,
        "params": {
            "threshold": threshold,
            "darkfield": darkfield,
        },
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(body))
        response.raise_for_status()
        json_data = response.json()
        return Job(**json_data)
    except HTTPError as http_err:
        raise HTTPError(f"HTTP error occurred: {http_err}")
    except RequestException as req_err:
        raise RequestException(f"Request exception occurred: {req_err}")

@mcp.tool()
def get_job_by_id(distiller_job_id: int) -> Job:
    """ Get information about a single job in Distiller, including its
    current state, Slurm id, and any captured output.

    Parameters
    ----------
    distiller_job_id : int
        The Distiller job id.

    Returns
    -------
    : Job
        The Job with the given id.
    """
    headers = {
        settings.API_KEY_NAME: settings.API_KEY,
        "Content-Type": "application/json",
    }

    url = f"{settings.API_URL}/jobs/{distiller_job_id}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        json_data = response.json()
        return Job(**json_data)
    except HTTPError as http_err:
        raise HTTPError(f"HTTP error occurred: {http_err}")
    except RequestException as req_err:
        raise RequestException(f"Request exception occurred: {req_err}")

@mcp.tool()
def get_jobs(
    skip: int = 0,
    limit: int = 100,
    job_type: Optional[JobType] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    scan_id: Optional[int] = None,
) -> list[Job]:
    """ Fetch a list of jobs with various filter options.

    Parameters
    ----------
    skip : int
        Number of records to skip.
    limit : int
        Maximum number of records to return.
    job_type : JobType, optional
        Filter by job type, e.g. JobType.COUNT.
    start : datetime, optional
        Start of the date range for job submission time.
    end : datetime, optional
        End of the date range for job submission time.
    scan_id : int, optional
        Filter by the Distiller scan id the job operates on.

    Returns
    -------
    : list[Job]
        A list of Job objects matching the criteria.
    """
    headers = {
        settings.API_KEY_NAME: settings.API_KEY,
        "Content-Type": "application/json",
    }

    params: dict[str, Any] = {
        "skip": skip,
        "limit": limit,
    }

    if job_type is not None:
        params["job_type"] = job_type.value
    if start is not None:
        params["start"] = start.isoformat()
    if end is not None:
        params["end"] = end.isoformat()
    if scan_id is not None:
        params["scan_id"] = scan_id

    url = f"{settings.API_URL}/jobs"

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        json_data = response.json()
        return [Job(**job_data) for job_data in json_data]
    except HTTPError as http_err:
        raise HTTPError(f"HTTP error occurred: {http_err}")
    except RequestException as req_err:
        raise RequestException(f"Request exception occurred: {req_err}")

@mcp.tool()
def cancel_job(distiller_job_id: int) -> Job:
    """ Cancel a running or pending job in Distiller.

    Parameters
    ----------
    distiller_job_id : int
        The Distiller job id to cancel.

    Returns
    -------
    : Job
        The updated Job, reflecting the cancelled state.
    """
    headers = {
        settings.API_KEY_NAME: settings.API_KEY,
        "Content-Type": "application/json",
    }

    url = f"{settings.API_URL}/jobs/{distiller_job_id}/cancel"

    try:
        response = requests.put(url, headers=headers)
        response.raise_for_status()
        json_data = response.json()
        return Job(**json_data)
    except HTTPError as http_err:
        raise HTTPError(f"HTTP error occurred: {http_err}")
    except RequestException as req_err:
        raise RequestException(f"Request exception occurred: {req_err}")

def get_scan_by_id_test(distiller_scan_id: int):
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

def put_note_test(distiller_scan_id: int, note: str):
    """ Set the note field in Distiller. This can be used to 
    save extra data about a 4D STEM scan.
    
    NON MCP version for testing
    
    Parameters
    ----------
    distiller_scan_id : int
        The Disitller scan id. This is a unique ID attached to each data set in the database.
    note : str
        The information to store in the notes section of Distiller
        
    Returns
    -------
    : Scan
        A Scan class object with information about the scan that was changed 
    """
    import json
    headers = {
        settings.API_KEY_NAME: settings.API_KEY,
        "Content-Type": "application/json",
    }

    url = f"{settings.API_URL}/scans/{distiller_scan_id}"

    try:
        response = requests.patch(url, headers=headers, data=json.dumps({'notes':note}))
        response.raise_for_status()
        json_data = response.json()
        print(json_data)
        return Scan(**json_data)
    except HTTPError as http_err:
        raise HTTPError(f"HTTP error occurred: {http_err}")
    except RequestException as req_err:
        raise RequestException(f"Request exception occurred: {req_err}")

if __name__ == "__main__":
    mcp.run(transport = "sse", host = "team05-support.dhcp.lbl.gov", port = 8081)
    #mcp.run(transport = "sse", host = "127.0.0.1", port = 8081)
    
    # Test getting information from Distiller
    #aa = get_scan_by_id_test(distiller_scan_id=35249)
    #if aa.metadata:
    #    print(f'Screen current = {aa.metadata['Screen current']}')
    #if aa.notes:
    #    print(f'notes = {aa.notes}')
    
    #print('change the note.')
    # put_note(distiller_scan_id=35249, note='Posted through the API')