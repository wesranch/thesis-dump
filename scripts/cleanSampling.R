
library(dplyr)

file_dir <- "/Users/wancher/Downloads/"
out_dir <- "/Users/wancher/Documents/thesis/data/output/"
pattern <- "pixel-vals-"

#files
files <- list.files(file_dir, pattern = pattern , full.names = TRUE, recursive = TRUE)
dfs <- lapply(files, read.csv)

for (i in seq_along(dfs)){
  print(ncol(dfs[[i]]))
}

dfs <- dfs[sapply(dfs, function(df) ncol(df) == 37)]
main_df <- do.call(rbind, dfs)
colnames(main_df)
clean_df <- main_df[-c(1, 37)]

write.csv(clean_df, file = paste0(out_dir, "pixel-vals-indices-topo-C60L.csv"), row.names = F)
