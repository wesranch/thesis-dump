# mosaic gee outputs
# Wesley Rancher

#install.packages("terra")
#install.packages("dplyr")
library(terra)
library(dplyr)
library(argparse)

#init
parser <- ArgumentParser()

# add the arguments to the parser
parser$add_argument('--dest_dir', type = 'character')
parser$add_argument('--out_dir', type = 'character')
parser$add_argument('--pattern', type = 'character')
parser$add_argument('--start_year', type = 'integer')
parser$add_argument('--end_year', type = 'integer')

# Parse
args <- parser$parse_args()
file_dir <- args$dest_dir
out_dir <- args$out_dir
pattern <- args$pattern
start_year <- args$start_year
end_year <- args$end_year
setwd(file_dir)

# read in the rasters 
list_of_files <- list.files(file_dir, pattern = pattern, full.names = TRUE)
print("files to be mosaiced:")
print(list_of_files)

# iterate over a sequence of years and pull out files specific to the year in the sequence
years <- seq(start_year, end_year)
years_string <- as.character(years)
for (year in unique(years_string)) {
  
  #pull out unique year
  #year <- years_string[[i]]
  files_one_year <- list_of_files[grepl(year, list_of_files)]

  
  list_of_rasters <- lapply(files_one_year, function(file) {
    r <- rast(file)
    r
  })
  
  # get band names for retention
  band_names <- names(list_of_rasters[[1]])
  flattened_band_names <- unlist(band_names)
  
  # turn list in sprc and mosaic
  coll_of_rasters <- sprc(list_of_rasters)
  print(paste0(year, " start: ", Sys.time()))
  mosaiced_raster <- merge(coll_of_rasters) 
  print(paste0(year, " finish: ", Sys.time()))
  names(mosaiced_raster) <- band_names
  
  #save it
  output_filename <- paste0(out_dir, "Landsat-mosaic-", year, ".tif")
  print(output_filename)
  writeRaster(mosaiced_raster, filename = output_filename, filetype = "GTiff", overwrite = TRUE)
  rm(list_of_rasters, coll_of_rasters, mosaiced_raster)
  gc()
}


