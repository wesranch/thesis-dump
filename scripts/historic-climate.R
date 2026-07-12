#plot locations
pl <- read.csv("/Users/wancher/Documents/thesis/data/biomass-input/locations.csv")
locations <- vect(pl, geom = c("x","y"),crs="EPSG:4326")
plot(locations)

#precip dir
dir <- "/Users/wancher/Documents/thesis/data/climate-data/pr_AK_771m_PRISM_1971_2000_historical/"
list_of_precip <- list.files(dir, pattern = "\\.tif$", full.names = T)
pr_rasters <- rast(c(list_of_precip))
pr_avg <- app(pr_rasters, fun = "mean")
plot(pr_avg)

#temperature dir
dir <- "/Users/wancher/Documents/thesis/data/climate-data/tas_AK_771m_PRISM_1971_2000_historical"
list_of_tas <- list.files(dir, pattern = "\\.tif$", full.names = T)
tas_rasters <- rast(c(list_of_tas))
tas_avg <- app(tas_rasters, fun = "mean")
plot(tas_avg)

#extract and clean
sampled_vals_hist_pr <- extract(pr_avg, locations)
sampled_vals_hist_tas <- extract(tas_avg, locations)

xy <- geom(locations)

sampled_vals_hist_pr <- sampled_vals_hist_pr[-c(1)]
sampled_vals_hist_tas <- sampled_vals_hist_tas[-c(1)]
names(sampled_vals_hist_pr)[names(sampled_vals_hist_pr) == "mean"] <- "hist_pr_1971_2000"
names(sampled_vals_hist_tas)[names(sampled_vals_hist_tas) == "mean"] <- "hist_tas_1971_2000"

sampled_vals_hist_pr$x <- xy[, "x"]
sampled_vals_hist_pr$y <- xy[, "y"]

sampled_vals_both_vars <- cbind(sampled_vals_hist_pr, sampled_vals_hist_tas)

write.csv(sampled_vals_both_vars, "/Users/wancher/Documents/thesis/data/output/pixel-vals-hist-clim.csv", row.names = F)
