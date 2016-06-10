"""io.py 

  This module contains utility functions related to file input/output for the
  vic_rgm_conductor.

"""

import numpy as np
import csv

def get_rgm_pixel_mapping(pixel_map_file):
  """ Parses the RGM pixel to VIC grid cell mapping file and initialises a 2D
    grid of dimensions num_rows_dem x num_cols_dem (matching the RGM pixel
    grid), each element containing a list with the VIC cell ID associated
    with that RGM pixel and its median elevation
  """
  cell_areas = {}
  headers = {}
  with open(pixel_map_file, 'r') as f:
    # Read the number of columns and rows (order is unimportant)
    for _ in range(2):
      key, value = f.readline().split(None, 1)
      headers[key] = value
    nx = int(headers['NCOLS'])
    ny = int(headers['NROWS'])
    # create an empty two dimensional array
    cell_id_map = np.empty((ny, nx))
    cell_id_map.fill(np.nan)
    z_map = np.empty((ny, nx))
    z_map.fill(np.nan)
    _ = f.readline() # Consume the column headers
    for line in f:
      _, i, j, _, median_elev, cell_id = line.split()
      i, j = int(i), int(j)
      if cell_id != 'NA': #otherwise we leave it as np.NaN
        cell_id_map[i,j] = cell_id
        z_map[i, j] = median_elev
      # Increment the pixel-granularity area within the grid cell
      if cell_id in cell_areas:
        cell_areas[cell_id] += 1
      else:
        cell_areas[cell_id] = 1
  return cell_id_map, z_map, cell_areas, nx, ny

def read_gsa_headers(dem_file):
  """ Opens and reads the header metadata from a GSA Digital Elevation Map
    file, verifies agreement with the VIC-RGM mapping file metadata, and
    returns the x and y extents metadata
  """
  with open(dem_file, 'r') as f:
    # First line
    first_line = f.readline()
    assert first_line.startswith('DSAA'), 'read_gsa_headers({}): DSAA header \
      on first line of DEM file was not found or is malformed.  DEM file does \
      not conform to ASCII grid format.'.format(dem_file)
    # Second line
    num_cols, num_rows = f.readline().split()
    xmin, xmax = f.readline().split()
    ymin, ymax = f.readline().split()
    out_1 = [float(n) for n in (xmin, xmax, ymin, ymax)]
    out_2 = [int(x) for x in (num_rows, num_cols)]
  return out_1 + out_2

def write_grid_to_gsa_file(grid, outfilename, num_cols_dem, num_rows_dem,\
    dem_xmin, dem_xmax, dem_ymin, dem_ymax):
  """ Writes a 2D grid to ASCII file in the input format expected by the RGM \
  for DEM and mass balance grids """
  zmin = np.min(grid)
  zmax = np.max(grid)
  header_rows = [['DSAA'], [num_cols_dem, num_rows_dem], [dem_xmin, dem_xmax],\
    [dem_ymin, dem_ymax], [zmin, zmax]]
  with open(outfilename, 'w') as csvfile:
    writer = csv.writer(csvfile, delimiter=' ')
    for header_row in header_rows:
      writer.writerow(header_row)
    for row in grid:
      writer.writerow(row)

def update_glacier_mask(surf_dem, bed_dem, num_rows_dem, num_cols_dem):
  """ Takes output Surface DEM from RGM and uses element-wise differencing 
    with the Bed DEM to form an updated glacier mask 
  """
  diffs = surf_dem - bed_dem
  if np.any(diffs < 0):
    raise Exception(
      'update_glacier_mask: Error: Subtraction of Bed DEM from the output \
      Surface DEM of RGM produced one or more negative values.'
    )

  glacier_mask = np.zeros((num_rows_dem, num_cols_dem))
  glacier_mask[diffs > 0] = 1
  return glacier_mask

def read_state(state, cells):
  """Reads the most recent state variables from the VIC state file produced by
    the most recent VIC run and updates the CellState and HruState object
    members of each cell.
  """
  num_lons = len(state['lon'])
  def get_2D_cell_indices(count):
    """Returns the 2D lat/lon indices of the cell for accessing it from the
      state file
    """
    return count // num_lons, count % num_lons

  cell_idx = 0
  for cell_id, cell in cells.items():
    cell_lat_idx, cell_lon_idx = get_2D_cell_indices(cell_idx)
    cell_hru_idx = 0
    # read all cell state variables
    for variable in cell.cell_state.variables:
      cell.cell_state.variables[variable] = \
        state[variable][cell_lat_idx][cell_lon_idx]
    for band in cell.bands:
      # HRUs are sorted by ascending veg_type_num in VIC state file
      for hru_veg_type in band.hru_keys_sorted:
        # read all HRU state variables with dimensions (lat, lon, hru)
        for variable in band.hrus[hru_veg_type].hru_state.variables:
          band.hrus[hru_veg_type].hru_state.variables[variable] = \
            state[variable][cell_lat_idx][cell_lon_idx][cell_hru_idx]
        cell_hru_idx += 1
    cell_idx += 1

def write_state(state, cells):
  """Modifies the existing VIC state file with the modified states from the
    CellState and HruState object members of each cell.
  """
  num_lons = len(state['lon'])
  def get_2D_cell_indices(count):
    """Returns the 2D lat/lon indices of the cell for accessing it from the
      state file
    """
    return count // num_lons, count % num_lons

  cell_idx = 0
  for cell_id, cell in cells.items():
    cell_lat_idx, cell_lon_idx = get_2D_cell_indices(cell_idx)
    cell_hru_idx = 0
    # write all cell state variables
    for variable in cell.cell_state.variables:
      state[variable][cell_lat_idx, cell_lon_idx] = \
        cell.cell_state.variables[variable]
    for band in cell.bands:
      # HRUs are sorted by ascending veg_type_num in VIC state file
      for hru_veg_type in band.hru_keys_sorted:
        # write all HRU state variables with dimensions (lat, lon, hru)
        for variable in band.hrus[hru_veg_type].hru_state.variables:
          state[variable][cell_lat_idx, cell_lon_idx, cell_hru_idx] = \
            band.hrus[hru_veg_type].hru_state.variables[variable]
        cell_hru_idx += 1
    cell_idx += 1
