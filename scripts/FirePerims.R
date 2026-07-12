#mtbs map for intro

library(terra)
library(ggplot2)
library(dplyr)
library(rnaturalearth)
library(rnaturalearthdata)
library(sf)
options(scipen=999)

#read in mtbs filtered to AK
albers <- "EPSG:3338"
fires <- vect("/Users/wancher/Downloads/mtbs_perims_DD.shp")
aoi <- st_read("/Users/wancher/Documents/thesis/data/map-files/FullLandscapeV3_082722.shp")
fires_ak <- fires[grep("^AK", fires$Event_ID), ]
fires_ak$Year <- substr(as.character(fires_ak$Ig_Date), 1, 4)
fires_ak_sf <- st_as_sf(fires_ak)
fires_ak_sf <- st_transform(fires_ak_sf, crs = albers)
fires_ak_sf_clipped <- st_intersection(fires_ak_sf, aoi)

#ak shpfile
alaska <- ne_states(country = "United States of America", returnclass = "sf") %>%
  filter(name == "Alaska")
alaska <- st_transform(alaska, crs = albers)

fplot <- ggplot() +
  geom_sf(data = alaska, fill = "gray90", color = "black") +
  geom_sf(data = fires_ak_sf_clipped, aes(fill = Year), color = NA) +
  scale_fill_viridis_d(option = "plasma", name = "Year") +
  theme_bw(base_family = "Times New Roman") +
  #theme(legend.position = "bottom",
  #      legend.box = "horizontal")+
  labs(title = "Fire Perimeters")

#save
png("writing/figures/Introduction_Fires.png", width = 7, height = 6.5, units = "in", res = 300)
print(fplot)
dev.off()


##plotting annual area burned
summary_df <- as.data.frame(fires_ak_sf_clipped) %>%
  group_by(Year)%>%
  summarise(AAB=sum(BurnBndAc, na.rm = TRUE)/2.471)%>%
  filter(Year >= 2000)

#x axis breaks
min_year <- min(summary_df$Year)
max_year <- max(summary_df$Year)
x_breaks <- seq(min_year, max_year, by = 5)

aabplot <- ggplot(data = summary_df, aes(x = as.numeric(Year), y = AAB)) +
  geom_line(color = "black", size = 1) +
  scale_x_continuous(breaks = x_breaks) + 
  labs(
    title = "Annual Area Burned",
    x = "Year",
    y = expression("Area Burned (Ha)")
  ) +
  theme_bw(base_family = "Times New Roman") +
  theme(
    axis.text = element_text(color = "black", size = 14),
    axis.text.x = element_text(color = "black", size = 14, angle = 45, hjust = 1), 
    plot.title = element_text(color = "black", size = 20, hjust = 0.5), 
    axis.title.y = element_text(color = "black", size = 18),
    axis.title.x = element_text(color = "black", size = 18),
    strip.text = element_text(color = "black", size = 13), 
    panel.grid.major = element_line(color = "gray70", linewidth = 0.25),
    panel.grid.minor = element_blank()
  )


png("writing/figures/Introduction_AAB.png", width = 7, height = 6.5, units = "in", res = 300)
print(aabplot)
dev.off()
