#spatial rf
#Wesley Rancher

library(dplyr)
library(spatialRF)
library(tidyr)
library(terra)
library(ggplot2)
library(tidymodels)
library(patchwork)
library(ranger)
library(SpatialML)

################################################################################
file_dir <- "/Users/wancher/Documents/thesis/data/output/"
out_dir <- "/Users/wancher/Documents/thesis/data/output/"
pattern <- "pixel-vals-3seas"

#files
files <- list.files(file_dir, pattern = pattern , full.names = TRUE, recursive = T)
climate_df <- read.csv(paste0(file_dir, "pixel-vals-hist-clim.csv"))
permafrost_df <- read.csv(paste0(file_dir, "pixel-vals-perm.csv"))
#files_to_predict <- list.files(file_dir, pattern = "all-pixels-", full.names = TRUE, recursive = TRUE)#predicting at plot xy only
raster_files <- list.files(out_dir, "dalton-clean-", full.names = T, recursive = T) #map predictions

#rasters
shp <- vect("/Users/wancher/Documents/thesis/data/landis/dalton_input/Dalton_Landscape.shp")
slope <- rast("/Users/wancher/Documents/thesis/data/output/dalton-slope.tif")
elev <- rast("/Users/wancher/Documents/thesis/data/output/dalton-elev.tif")
aspect <- rast("/Users/wancher/Documents/thesis/data/output/dalton-aspect.tif")
perm_raster <- rast("/Users/wancher/Documents/thesis/data/climate-data/permafrost/mu_permafrost_0_100_2.img")


###############################################################################
#function for cleaning
raster_to_df <- function(file){
  file_name <- basename(file)
  year <- sub('.*-(\\d{4})\\.tif', '\\1', file_name)
  
  r <- rast(file)
  r_full <- c(r, elev, slope, aspect)
  df <- as.data.frame(r_full, xy = TRUE)
  df$year <- year
  return(df)
}
raster_dataframes <- lapply(raster_files, raster_to_df)
rasters_clean <- list()
for (df in raster_dataframes) {
  rasters_clean[[df$year[1]]] <- df
}

#comment out if not mapping
dfs_predict <- rasters_clean

#prediction data wrangling
df_for_predicting <- function(file){
  #grab year from filename
  file_name <- basename(file)
  year <- sub('.*-(\\d{4})\\.csv', '\\1', file_name)
  
  #read file and rm index
  df <- read.csv(file)
  df <- df[-c(1)]
  
  #add xy
  coords <- sub('.*\\[([-0-9.]+),([-0-9.]+)\\].*', '\\1,\\2', df$.geo)
  splitxy <- strsplit(coords, ",")
  x <- as.numeric(sapply(splitxy, `[`, 1))
  y <- as.numeric(sapply(splitxy, `[`, 2))
  df$x <- x
  df$y <- y
  df <- df[-c(31)]
  df$year <- year
  return(df)
}
#add year as name for element in list
dfs_predict <- list()
for (file in files_to_predict) {
  df <- df_for_predicting(file)
  dfs_predict[[df$year[1]]] <- df
}

#lapply to df for training data
dfs <- lapply(files, read.csv)
for (i in seq_along(dfs)){
  print(ncol(dfs[[i]]))
}

#remove dfs with less than max columns and rbind
dfs <- dfs[sapply(dfs, function(df) ncol(df) == 37)]
main_df <- do.call(rbind, dfs)
names(main_df)
clean_df <- main_df[-c(1)]#rm sys index

#convert geo column to xy
coords <- sub('.*\\[([-0-9.]+),([-0-9.]+)\\].*', '\\1,\\2', clean_df$.geo)
splitxy <- strsplit(coords, ",")
x <- as.numeric(sapply(splitxy, `[`, 1))
y <- as.numeric(sapply(splitxy, `[`, 2))

#distance matrix
#xy <- c(x,y)
clean_df$x <- x
clean_df$y <- y
#no_duplicate_xy <- clean_df[!duplicated(clean_df[c("x","y")]),]
#locations <- clean_df[c("x", "y")]#need psp?
#plot(locations$x, locations$y)
#write.csv(locations, "/Users/wancher/Documents/thesis/data/biomass-input/locations.csv", row.names = FALSE)


################################################################################
# response_variables <- c("AKbirch", "BCotton",
#                         "WhiteSpruce", "QAspen", "BlackSpruce")
response_variables <- c("resin birch", "black spruce",
                       "white spruce", "quaking aspen")
#cbind climate because join operation is wonky
clean_df_w_climate <- cbind(clean_df, climate_df)%>%select(-c(40,41))
training_df <- clean_df_w_climate %>%
  #mutate(across(-Species, ~ na_if(.x, -9999))) %>%#no 9999 vals
  filter(Species %in% response_variables) %>%
  rename(year=Year)%>%
  mutate(ag_carbon = Biogm2 * 0.47)%>%
  left_join(permafrost_df, by = c("PSP", "Species", "year"))%>%#pain in the neck
  select(-year, -PSP, -SPP_count, -.geo, -Biogm2, -x.y, -y.y)%>%
  rename(x = x.x, y = y.x)%>%
  drop_na()

################################################################################
# Iterate
grf_models <- list()
models <- list()
spatial_models <- list()
prediction_maps <- list()
summary_dfs <- list()
training_dataframes <- list()
#response <- response_variables[[3]]
for (response in response_variables) {
  
  #filter df to species  
  training_df_one_spp <- training_df %>% 
    filter(Species == response) %>%
    select(-Species)
  
  # tidy models to rm correlated vars
  tm_recipe <- recipe(ag_carbon ~ ., data = training_df_one_spp) %>%
    step_corr(all_numeric_predictors(), threshold = 0.80, 
              use = "pairwise.complete.obs", method = "pearson")
  prepped_recipe <- prep(tm_recipe, training = training_df_one_spp)
  data_corrRM <- bake(prepped_recipe, new_data = training_df_one_spp)
  
  split <- initial_split(data_corrRM, prop = .8)
  train <- training(split)
  test  <- testing(split)
  
  #create clean training df
  train_df <- train %>% 
    #append biomass column
    left_join(training_df_one_spp %>% select(ag_carbon,x,y), 
              by = c("x", "y", "ag_carbon"), relationship = "many-to-many")
  predictors <- setdiff(names(train_df), "ag_carbon")
  
  #create distance matrix
  distance.matrix <- as.matrix(dist(subset(train_df, select = -c(x, y))))
  thresholds <- quantile(distance.matrix, probs = c(0.25, 0.5, 0.75))
  #thresholds <- c(0, 2500, 5000, 7500, 12000)
  # non spatial random forest
  model.non.spatial <- spatialRF::rf(
    data = train_df,
    dependent.variable.name = "ag_carbon",
    predictor.variable.names = predictors,
    distance.matrix = distance.matrix,
    distance.thresholds = thresholds,
    xy = train_df[c("x","y")],
    verbose = FALSE) 
  
  #eval
  model.non.spatial <- spatialRF::rf_evaluate(
    model = model.non.spatial,
    xy = train_df[c("x","y")],
    repetitions = 30,         #number of spatial folds
    training.fraction = 0.80, #training data fraction on each fold
    metrics = "r.squared",
    verbose = FALSE)
  
  model.spatial <- spatialRF::rf_spatial(
    model = model.non.spatial,
    method = "mem.moran.sequential", #default method
    verbose = FALSE)
  
  print(response)
  spatialRF::print_performance(model.non.spatial)
  spatialRF::print_performance(model.spatial)
  
  models[[response]] <- model.non.spatial
  spatial_models[[response]] <- model.spatial
  training_dataframes[[response]] <- train_df
  
  ##############################################################################
  #geographic random forest package here:
  formula <- as.formula(paste("ag_carbon", "~", 
                              paste(setdiff(predictors, c("x", "y")), collapse = " + ")))
  grf_model <- grf(formula,
                 dframe = train_df, kernel = "adaptive", bw = 50, coords = train_df[c("x","y")], 
                 ntree = 500, forests = TRUE, geo.weighted = TRUE, print.results = TRUE)
  
  grf_models[[response]] <- grf_model
  ##############################################################################
  # predictions
  prediction_maps_years <- list()
  #years <- c(2000,2024)
  #for (year in years){
    
    #year_chr <- as.character(year)
    #keep columns after baking from above but join to plot locations df or raster
    #df_predict <- left_join(dfs_predict[[year_chr]], train_df)%>%
    #  select(intersect(names(dfs_predict[[year_chr]]), names(train_df)))
  
    
    #predicted <- stats::predict(
    #  object = grf_model$Global.Model,
    #  data = df_predict,
    #  type = "response"
    #)$predictions
    
    
    #df_predict$predicted <- predicted #add as column
    #df_predict$Species <- response
    
    #summary_df <- df_predict %>%
      #group_by(year, Species)%>%
    #  summarise(PredAvg = mean(predicted, na.rm = T),
    #            PredSD = sd(predicted, na.rm = T))
      
    #store in the list
    #summary_dfs[[length(summary_dfs) + 1]] <- summary_df
    
    #df to matrix
    #m <- as.matrix(df_predict[, c("x","y","predicted")])
    
    #empty_r <- rast(xmin = min(m[,1]), xmax = max(m[,1]), 
    #          ymin = min(m[,2]), ymax = max(m[,2]), 
    #          resolution = 30) 
    
    #pred_raster <- rasterize(m[, 1:2], empty_r, values = m[,3], background = NA)
    #names(pred_raster) <- "ag_carbon_Pred"
    #prediction_maps_years[[year_chr]] <- pred_raster
    #rm(predicted)
    #rm(pred_raster)
    #rm(m, empty_r)
    #gc()
  #}
  #prediction_maps[[response]] <- prediction_maps_years
  
  rm(model.spatial)
  rm(model.non.spatial)
  gc()
}
for (response in response_variables){
  predictions <- prediction_maps[[response]]
  r2000 <- predictions$`2000`
  r2024 <- predictions$`2024`
  #plot(r2024-r2000)
  response2 <- gsub(" ", "-", response)
  writeRaster(r2000, paste0("/Users/wancher/Documents/thesis/data/output/", response2, "-biomass-2000.tif"), overwrite = TRUE)
  writeRaster(r2024, paste0("/Users/wancher/Documents/thesis/data/output/", response2, "-biomass-2024.tif"), overwrite = TRUE)
  

}
for (i in seq_along(prediction_maps)){
  writeRaster(i, )
}
plotting_df <- do.call(rbind, summary_dfs)
plotting_df$year <- as.numeric(plotting_df$year)
p <- ggplot(plotting_df, aes(y= PredAvg, x = year, color = Species, group = Species))+
  geom_line(linewidth = 2)+
  #geom_smooth(linewidth = 1)+
  #geom_point(size = 3, alpha = 0.5)+
  scale_color_paletteer_d("lisa::EdwardHopper")+
  #geom_smooth()+
  #facet_wrap(~Species, ncol = 1)+
  theme_minimal()+
  theme(legend.position = "none")+
  scale_x_continuous(breaks = seq(2000, 2025, by = 5))+
  scale_y_continuous(breaks = seq(0, 700, by = 100), limits = c(0, 1000))

################################################################################
#training df plot // do this on cleaned vars
spatialRF::plot_training_df(
  data = train_df,
  dependent.variable.name = "ag_carbon",
  predictor.variable.names = predictors,
  ncol = 5,
  method = "lm",
  point.color = viridis::viridis(100, option = "plasma"),
  line.color = "black"
)

library(pdp)
#partial dependency
#https://cran.r-project.org/web/packages/pdp/vignettes/pdp-intro.pdf
pdp_dfs <- list()
top_var <- "DSM"
for (response in response_variables){
  grf_model <- grf_models[[response]]
  train_df <- training_dataframes[[response]]
  depplot <- pdp::partial(
    grf_model$Global.Model, 
    train = train_df, 
    pred.var = top_var, 
    grid.resolution = 200,
    plot = FALSE)
  pdp_df <- as.data.frame(depplot)
  pdp_df$Species <- response
  pdp_dfs[[response]] <- pdp_df
  
  #plot
  png("writing/figures/partialWS.png", width = 5, height = 5, units = "in", res = 300)
  plt <- ggplot(pdp_df, aes_string(x = top_var, y = "yhat")) +
    geom_line(size = 2, color = "#A4804CFF") +
    labs(
      x = top_var, 
      y = "AG Carbon") +
    theme_minimal()
  print(plt)
  dev.off()
}


################################################################################
#importance plots
for (response in response_variables){
  model.non.spatial <- models[[response]]
  model.spatial <- spatial_models[[response]]
  grf_model <- grf_models[[response]]
  
  p1 <- spatialRF::plot_importance(
    model.non.spatial, 
    verbose = FALSE) + 
    ggplot2::ggtitle("Non-spatial model")
  
  p2 <- spatialRF::plot_importance(
    model.spatial,
    verbose = FALSE) + 
    ggplot2::ggtitle("Spatial model")
  
  png(paste0("writing/figures/vip",response, ".png"), width = 5, height = 5, units = "in", res = 300)
  grf_plot <- vip(
    grf_model$Global.Model,
    verbose = FALSE
  ) +
    ggtitle("Global Feature Importance") +
    theme_minimal(base_size = 14) + 
    theme(
      plot.title = element_text(hjust = 0.5),
      axis.text = element_text(color = "black"),
      axis.title = element_blank()
    ) +
    #labs(y = "Global Importance")+
    scale_fill_viridis_d()+
    geom_col(fill = viridis_pal(option = "E")(5)[2])
  print(grf_plot)
  dev.off()
  double <- p1 | p2
  plot_this <- double + plot_annotation(title = response)
  print(plot_this)
}

################################################################################
# investigating spatial predictors
library(tigris)
library(sf)
us_states <- tigris::states(cb = TRUE, resolution = "500k")
alaska <- us_states %>% filter(STUSPS == "AK")
alaska_3338 <- st_transform(alaska, crs = 3338)
plot(alaska_3338["STUSPS"]) 

#spatial predictors explained here:
# https://blasbenito.github.io/spatialRF/#fitting-a-spatial-model-with-rf_spatial
spatial.predictors <- spatialRF::get_spatial_predictors(model.spatial)
pr <- data.frame(spatial.predictors, training_df_one_spp[, c("x", "y")])
pr_sf <- st_as_sf(pr, coords = c("x", "y"), crs = 4326)
pr_3338 <- st_transform(pr_sf, crs = 3338)
pr2 <- as.data.frame(st_coordinates(pr_3338))
pr2 <- cbind(pr2, pr_sf[, !(names(pr_sf) %in% c("geometry"))]) %>%
  select(-geometry)

p1 <- ggplot2::ggplot() +
  ggplot2::geom_sf(data = alaska_3338, fill = "white") +
  ggplot2::geom_point(
    data = pr2,
    ggplot2::aes(
      x = X,
      y = Y,
      color = spatial_predictor_357.9323_2
    ),
    size = 2.5
  ) +
  ggplot2::scale_color_viridis_c(option = "F") +
  ggplot2::theme_bw() +
  ggplot2::labs(color = "Eigenvalue") +
  #ggplot2::scale_x_continuous(limits = c(-170, -30)) +
  #ggplot2::scale_y_continuous(limits = c(-58, 80))  +
  ggplot2::ggtitle("Variable: spatial_predictor_0_2") + 
  ggplot2::theme(legend.position = "bottom")+ 
  ggplot2::xlab("Longitude") + 
  ggplot2::ylab("Latitude")

p2 <- ggplot2::ggplot() +
  ggplot2::geom_sf(data = alaska_3338, fill = "white") +
  ggplot2::geom_point(
    data = pr2,
    ggplot2::aes(
      x = X,
      y = Y,
      color = spatial_predictor_357.9323_5,
    ),
    size = 2.5
  ) +
  ggplot2::scale_color_viridis_c(option = "F") +
  ggplot2::theme_bw() +
  ggplot2::labs(color = "Eigenvalue") +
  #ggplot2::scale_x_continuous(limits = c(-155, 154)) +
  #ggplot2::scale_y_continuous(limits = c(50, 70))  +
  ggplot2::ggtitle("Variable: spatial_predictor_0_5") + 
  ggplot2::theme(legend.position = "bottom") + 
  ggplot2::xlab("Longitude") + 
  ggplot2::ylab("")

p1 | p2
