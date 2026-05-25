# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview
This repository contains Bokeh-based dashboards for real-time visualization of experimental data related to the Slab project. It includes both live streaming from hardware via EPICS and monitoring of local data files.

## Architecture

The core of the repository consists of two main application components:

- **Live Data Streaming (`stream_bokeh.py`)**: 
  - Uses the `epics` library to interface with EPICS PVs (Process Variables) from the Slab Ioxos DAQ system.
  - Continuously fetches data in a background thread and updates Bokeh plots.
  - Visualizes "on" vs "off" chopper states, ratios, and statistical uncertainties.
  - **Dependency**: Requires access to the `eco` python module (typically found in `/slab/config/src/python/eco/`).

- **File Watcher Dashboard (`watcher_bokeh.py`)**: 
  - Uses the `watchdog` library to monitor specific directories for new or modified `.txt` files.
  *   Updates a Bokeh dashboard automatically when data files are updated.
  - Allows selection of different "pgroups" (data groups) via a dropdown menu and enables comparison between multiple selected runs.

## Example Data

Example data files are in the following directories:

- **'.txt' files containing the data, which is loaded by the method 'read_file' in the script 'watcher_bokeh.py'**:
  - The data is loaded with the method 'read_file'
  - The data is analysed with the method 'on_modified_cb'

- **'.pkl' files containing the data used for the table in the script 'watcher_bokeh.py'**:
  - The data is loaded with the method 'get_run_table_data'

## Development Commands

The applications are designed to be run using the `bokeh serve` command.

### Running the Live Streamer
To start the live EPICS data dashboard:
```bash
bokeh serve --show slab_online_plot/stream_bokeh.py
```

### Running the File Watcher
To start the file monitoring dashboard:
```bash
bokeh serve --show slab_online_plot/watcher_bokeh.py
```

## Dependencies
The project requires the following Python packages:
- `numpy`
- `bokeh`
- `scipy`
- `epics`
- `watchdog`

**Note**: Ensure your `PYTHONPATH` includes the path to the `eco` acquisition module if running `stream_bokeh.py`.
