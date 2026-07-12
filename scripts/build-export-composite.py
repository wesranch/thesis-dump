
#Landsat image processing and predictor variable dataset creation
# Wesley Rancher, Hana Matsumoto

# %% start GEE session
import ee
import pandas as pd
import folium
from geemap import geemap
#ee.Reset()
ee.Authenticate()
ee.Initialize()

# %% Read in some ROI files and sampling data

#AK_landscape_model_region = ee.FeatureCollection('projects/ee-vegshiftsalaska/assets/LandisModelRegion') 
AK_landscape = ee.FeatureCollection('projects/ee-vegshiftsalaska/assets/Dalton_Landis') 
#AK_landscape = ee.FeatureCollection('projects/ee-vegshiftsalaska/assets/boreal_AK')
states = ee.FeatureCollection('TIGER/2016/States') 
#AK_landscape = states.filter(ee.Filter.eq('NAME', 'Alaska'))

#Map = geemap.Map(center=[64, -152], zoom=5, basemap='Esri.WorldGrayCanvas')

# topographic data
topo_data = ee.ImageCollection('JAXA/ALOS/AW3D30/V3_2').select('DSM')

elevation = topo_data.mosaic().reproject(crs='EPSG:4326', scale=30)
slope = ee.Terrain.slope(topo_data.mosaic().reproject(crs='EPSG:4326', scale=30))
aspect = ee.Terrain.aspect(topo_data.mosaic().reproject(crs='EPSG:4326', scale=30))

topo_layers = elevation.addBands(slope).addBands(aspect)

# %% Define years and functions for calculating SVIs
years = ee.List.sequence(2006, 2015)
year_info = years.size().getInfo()
year_info
# functions for vegetation indices calculations
#bands = ee.List(['blue', 'green', 'red', 'nir', 'swir1', 'swir2', 'ndvi', 'evi', 'mndwi', 'nbr', 'vari', 'savi', 'tcb', 'tcg', 'tcw'])
bands = ee.List(['ndvi', 'evi', 'mndwi', 'nbr', 'vari', 'savi', 'tcb', 'tcg', 'tcw'])

# normalized difference vegetation index
def ndvi_calc(img):
    ndvi = img.normalizedDifference(['nir', 'red']) \
              .rename('ndvi') \
              .multiply(10000.0) \
              .toInt16()
    return ndvi
# enhanced vegetation index
def evi_calc(img):
    # coefficients
    c1 = 2.5
    c2 = 6 
    c3 = 7.5
    c4 = 1.0

    # define bands
    red = img.select('red')
    nir = img.select('nir')
    blue = img.select('blue')

    # equation
    evi = nir.subtract(red) \
        .divide(nir.add(red.multiply(c2)).subtract(blue.multiply(c3)).add(c4)).multiply(c1) \
        .rename('evi') \
        .multiply(10000.0) \
        .toInt16()
    return evi
# modified normalized difference water index
def mndwi_calc(img):
    mndwi = img.normalizedDifference(['green', 'swir2']) \
              .rename('mndwi') \
              .multiply(10000.0) \
              .toInt16()
    return mndwi
# nbr
def nbr_calc(img):
    nbr = img.normalizedDifference(['nir', 'swir2']) \
            .rename('nbr') \
            .multiply(10000.0) \
            .toInt16()
    return nbr
# visible atmospherically resistant index
def vari_calc(img):
    vari = img.select('red') \
              .subtract(img.select('green')) \
              .divide(img.select('red').add(img.select('green')).subtract(img.select('blue'))) \
              .rename('vari') \
              .multiply(10000.0) \
              .toInt16()
    return vari
# soil adjusted vegetation index
def savi_calc(img):
    L = 0.5  # coefficient

    # bands
    nir = img.select('nir')
    red = img.select('red')

    # equation
    savi = nir.subtract(red).multiply(1+L) \
        .divide((nir).add(red).add(L)) \
        .rename('savi') \
        .multiply(10000.0) \
        .toInt16()
    return savi
# tasseled cap transformations
def tasseled_cap(img):
    # coefficients
    brightness_coeff = ee.Image([0.2043, 0.4158, 0.5524, 0.5741, 0.3124, 0.2303])
    greenness_coeff = ee.Image([-0.1603, -0.2819, -0.4934, 0.7940, 0.0002, -0.1446])
    wetness_coeff = ee.Image([0.0315, 0.2021, 0.3102, 0.1594, -0.6806, -0.6109])

    # bands to apply coefficients to
    # img = img.select(['B2', 'B3', 'B4', 'B5', 'B6', 'B7'])
    img = img.select(['blue', 'green', 'red', 'nir', 'swir1', 'swir2'])

    # math
    brightness = (img.multiply(brightness_coeff) \
        .reduce(ee.Reducer.sum()) \
        .rename('tcb') \
        .multiply(10000.0) \
        .toInt16())
    greenness = (img.multiply(greenness_coeff) \
        .reduce(ee.Reducer.sum()) \
        .rename('tcg') \
        .multiply(10000.0) \
        .toInt16())
    wetness = (img.multiply(wetness_coeff) \
        .reduce(ee.Reducer.sum()) \
        .rename('tcw') \
        .multiply(10000.0) \
        .toInt16())
    return ee.Image([brightness, greenness, wetness])

# %% Add indices and band names functions
def add_indices(image):
    scaled_image = image.toFloat().divide(10000.0)
    return image.addBands(ndvi_calc(scaled_image))\
                .addBands(evi_calc(scaled_image))\
                .addBands(mndwi_calc(scaled_image))\
                .addBands(nbr_calc(scaled_image))\
                .addBands(vari_calc(scaled_image))\
                .addBands(savi_calc(scaled_image))\
                .addBands(tasseled_cap(scaled_image))

# add suffix to all band names
def add_suffix(in_image, suffix_str):
    # convert band names to lowercase and add suffix
    def append_suffix(band_name):
        return ee.String(band_name).toLowerCase().cat('_').cat(suffix_str)
    # apply the suffix to all band names
    bandnames = in_image.bandNames().map(append_suffix)
    # the number of bands
    nb = bandnames.size()
    # select bands with the new names
    return in_image.select(ee.List.sequence(0, ee.Number(nb).subtract(1)), bandnames)

# %% Landsat sensor corrections and cloud masks

# Hurni harmonization technique (option in lieu of Massey approach)
def harmonization(img):
    slopes = ee.Image([0.8474, 0.8483, 0.9047, 0.8462, 0.8937, 0.9071])
    intercepts = ee.Image([0.0003, 0.0088, 0.0061, 0.0412, 0.0254, 0.0172])
    img_harm = img.select(['blue', 'green', 'red', 'nir', 'swir1', 'swir2']) \
        .multiply(slopes) \
        .add(intercepts.multiply(10000)) \
        .int16()
    return img.select().addBands(img_harm).addBands(img.select('pixel_qa'))


# function for cloud mask images in collection // includes water mask
def cloud_mask_landsat8(img):
    img = ee.Image(img)
    quality_band = img.select('pixel_qa') #fmask for hls and QA_PIXEL for landsat
    water = quality_band.bitwiseAnd(1).neq(0) 
    shadow = quality_band.bitwiseAnd(8).neq(0)  
    cloud = quality_band.bitwiseAnd(32).neq(0) 
    cloud_confidence = quality_band.bitwiseAnd(64).add(quality_band.bitwiseAnd(128)).interpolate([0, 64, 128, 192], [0, 1, 2, 3], 'clamp').int()
    cloud_confidence_medium_high = cloud_confidence.gte(2)
    cloudM = water.Or(shadow).Or(cloud).Or(cloud_confidence_medium_high).select([0], ['cloudM'])
    
    # add cirrus confidence to cloud mask (cloudM) for Landsat 8
    cirrus_confidence = quality_band.bitwiseAnd(256).add(quality_band.bitwiseAnd(512)).interpolate([0, 256, 512, 768], [0, 1, 2, 3], 'clamp').int()
    cirrus_confidence_medium_high = cirrus_confidence.gte(2)
    cloudM = cloudM.Or(cirrus_confidence_medium_high)
    cloudM = cloudM.Not()
 
    # mask image with cloud mask and add as band
    image_cloud_masked = img.updateMask(cloudM).addBands(cloudM)
    return image_cloud_masked

#%% Illumination condition
# https://mygeoblog.com/2018/10/17/terrain-correction-in-gee/
def illuminationCondition(img):
    #img = test_image_correcting
    #img_proj = img.projection()
    # Extract image metadata about solar position (azimuth and zenith)
    azimuth_rad = ee.Image.constant(ee.Number(img.get('SUN_AZIMUTH')).multiply(3.14159265359).divide(180))
    zenith_rad = ee.Image.constant(ee.Number(90).subtract(img.get('SUN_ELEVATION')).multiply(3.14159265359).divide(180))
    
    # Create terrian layers (slope and aspect)
    #the DEM is in a computed projection so we need to reproject
    topo_data = ee.ImageCollection('JAXA/ALOS/AW3D30/V3_2') \
        .filterBounds(AK_landscape) \
        .select('DSM') \
        .mosaic() \
        .reproject(crs='EPSG:4326', scale=30)

    #slope = ee.Terrain.slope(topo_data_mosaic)
    #Map.addLayer(slope, {'min': 0, 'max': 45, 'palette': ['blue', 'green', 'yellow', 'red']}, 'Slope')
    slope_rad = ee.Terrain.slope(topo_data).multiply(3.14159265359).divide(180)  # radians
    aspect_rad = ee.Terrain.aspect(topo_data).multiply(3.14159265359).divide(180)  # radians

    # Calculate Illumination Condition (IC)
    ## slope part of calc
    cos_zenith = zenith_rad.cos()
    cos_slope = slope_rad.cos()
    slope_illumination = cos_zenith.multiply(cos_slope)

    #Map.addLayer(slope_illumination, {'min': 0, 'max': .5, 'palette': ['blue', 'green', 'yellow', 'red']}, 'Slope Illumination')
    ## aspect part of calc
    sin_zenith = zenith_rad.sin()
    sin_slope = slope_rad.sin()
    cosAzmithDiff = (azimuth_rad.subtract(aspect_rad)).cos()
    aspect_illumination = sin_zenith.multiply(sin_slope).multiply(cosAzmithDiff)
    
    # full illumination condition 
    IC = slope_illumination.add(aspect_illumination)
    
    #add IC to image
    img_IC = img.addBands(IC.rename('IC'))\
        .addBands(cos_zenith.rename('cosZ'))\
        .addBands(cos_slope.rename('cosS'))\
        .addBands(slope.rename('slope'))
    return img_IC

#%% Illumination correction
# Function to apply the Sun-Canopy-Sensor + C (SCSc) correction method to each image. 
# Function by Patrick Burns and Matt Macander 
def illumination_correction(img):
    img_with_IC = illuminationCondition(img) 
    
    #used for testing
    # stats = img_plus_IC.reduceRegion(
    #     reducer=ee.Reducer.minMax(),  # Computes min and max values
    #     geometry=img_plus_IC.geometry(),  # Use the image's geometry (whole image)
    #     scale=30,  # Specify the scale (adjust as needed)
    #     maxPixels=1e13  # Set a high maxPixels value to allow full processing
    # )
    # info = stats.getInfo()
    #mask1 = img_plus_IC.select('nir').gt(-0.1)

    #landsat collection is scaled
    mask2 = img_with_IC.select('slope').gte(5) \
        .And(img_with_IC.select('IC').gte(0)) \
        .And(img_with_IC.select('nir').gt(-6535.5))
    img_plus_IC_mask2 = img_with_IC.updateMask(mask2)
    
    # bands to topo correct
    band_list = ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']

    def apply_scsc_corr(band):
        # reducer for linear fit
        fit = img_plus_IC_mask2.select(['IC', band]).reduceRegion(
            reducer=ee.Reducer.linearFit(),
            scale=30,
            maxPixels=1e9
        )
        
        # check if the reduction result is empty
        if fit is None or not fit.get('scale') or not fit.get('offset'):
            return img_plus_IC_mask2.select(band)

        # linear fit coefficients
        a = ee.Number(fit.get('scale'))#slope
        b = ee.Number(fit.get('offset'))#lm intercept
        #out_c = out_b.divide(out_a)
        c = ee.Algorithms.If(a.gt(0), b.divide(a), ee.Number(0))

        #correction
        #get bands
        band_image = img_plus_IC_mask2.select(band)
        IC_image = img_plus_IC_mask2.select('IC')
        cosS_image = img_plus_IC_mask2.select('cosS')
        cosZ_image = img_plus_IC_mask2.select('cosZ')
        
        # apply the final formula to divide by IC
        scsc_output = img_plus_IC_mask2.expression(
            "((image * (cosB * cosZ + cvalue)) / (IC + cvalue))", {
                'image': band_image,
                'IC': IC_image,
                'cosB': cosS_image,
                'cosZ': cosZ_image,
                'cvalue': c})
        
        return scsc_output
    
    # corrected_bands = band_list.map(apply_scsc_corr)
    corrected_bands = [apply_scsc_corr(band) for band in band_list]
    img_scsc_corr = ee.Image(corrected_bands).addBands(img.select('IC'))
    return img_scsc_corr.select(band_list)
#%% Get Collection
# renaming bands
def get_landsat_collection_sr(sensor):
    if sensor in ['LC08', 'LC09']:
        bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL']
    else:  # for Landsat 5 and 7
        bands = ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7', 'QA_PIXEL']

    band_names_landsat = ['blue', 'green', 'red', 'nir', 'swir1', 'swir2', 'pixel_qa']
    cloud_threshold = 80 
    collection_filtered_without_date = ee.ImageCollection('LANDSAT/' + sensor + '/C02/T1_L2') \
        .filterBounds(AK_landscape)\
        .filterMetadata('CLOUD_COVER', 'less_than', cloud_threshold) \
        .select(bands, band_names_landsat)  #rename bands
    collection_filtered_without_date = collection_filtered_without_date.map(harmonization)
    return collection_filtered_without_date

# %% Iterate
image_collection = ee.ImageCollection([])
pv_df = []
all_dfs = []
for i in range(year_info):
    year = years.get(9).getInfo()

    #seasonal windows
    startSeason1 = ee.Date.fromYMD(year, 3, 1)
    endSeason1 = ee.Date.fromYMD(year, 5, 31)
    startSeason2 = ee.Date.fromYMD(year, 6, 1)
    endSeason2 = ee.Date.fromYMD(year, 8, 31)
    startSeason3 = ee.Date.fromYMD(year, 9, 1)
    endSeason3 = ee.Date.fromYMD(year, 11, 30)
        
    ################################################
    #get this to work for startSeason endSeason
    def get_landsat_Images(sensor, AK_landscape, startSeason, endSeason):  
        collection = get_landsat_collection_sr(sensor)
        cleaned_images = (collection
            .filterBounds(AK_landscape)
            .filterDate(startSeason, endSeason)
            .map(cloud_mask_landsat8)
            .map(illumination_correction)
            .map(add_indices))
        return cleaned_images

    # function to bring everything together            
    def make_ls(AK_landscape):
        sensors = ['LC08', 'LC09', 'LE07', 'LT05']
        spring_images = ee.ImageCollection([])
        summer_images = ee.ImageCollection([])
        fall_images = ee.ImageCollection([])

        for sensor in sensors:
            spring_images = spring_images.merge(get_landsat_Images(sensor, AK_landscape, startSeason1, endSeason1))
            summer_images = summer_images.merge(get_landsat_Images(sensor, AK_landscape, startSeason2, endSeason2))
            fall_images = fall_images.merge(get_landsat_Images(sensor, AK_landscape, startSeason3, endSeason3))
        # Median composites by season
        #springtime = add_suffix(spring_images.median().select(bands), 'spring').unmask(-9999)
        summertime = add_suffix(summer_images.median().select(bands), 'summer').unmask(-9999)
        #falltime = add_suffix(fall_images.median().select(bands), 'fall').unmask(-9999)
        green_up = add_suffix(summer_images.median().subtract(spring_images.median()).select(bands), 'up').unmask(-9999)
        brown_down = add_suffix(fall_images.median().subtract(summer_images.median()).select(bands), 'down').unmask(-9999)

        # add each composite as bands
        return green_up.addBands(summertime).addBands(brown_down)


    # apply the function appending the image at each iteration to our list of images
    landsat_composite = make_ls(AK_landscape).clip(AK_landscape).reproject(crs='EPSG:3338', scale=30).int16()
    landsat_and_topo_layers = landsat_composite.addBands(topo_layers)               

    
    geom = AK_landscape.geometry()
    #save the composite
    task = ee.batch.Export.image.toDrive(
        image=landsat_composite,
        description=f'FullComp_Dalton_{year}_V2.tif',
        folder='Alaska_Proj',
        region=geom,
        scale=30,
        crs='EPSG:3338',
        maxPixels=1e13)
    task.start()

    # Add the composite to the ImageCollection
    #image_collection = image_collection.merge(ee.Image([landsat_composite]))

    # Sampling process
    def get_pixel_values(f, img):
        return f.setMulti(img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=f.geometry(),
            scale=30,
            crs='EPSG:3338'))
    
    cafiPlots = ee.FeatureCollection(f'projects/ee-vegshiftsalaska/assets/biomass-all-years/biomass_{year}')
    def sample_pixels(f):
        return get_pixel_values(f)

    pv_sampling = cafiPlots.map(lambda f: get_pixel_values(f, landsat_and_topo_layers))

    pv_sampling_info = pv_sampling.getInfo()

    # apply the sample function and export locally 
    for feature in pv_sampling_info['features']:
        properties = feature['properties']
        pv_df.append(properties)
    extracted_pv_vals = pd.DataFrame(pv_df)
    all_dfs.append(extracted_pv_vals)


#bind
final_df = pd.concat(all_dfs, ignore_index=True)
#final_df.to_csv('/Users/wancher/Documents/thesis/data/output/pixel-vals-indices-topo.csv', index=False) 
# %%  
# export to image collection
# geom = AK_landscape.geometry()
# export_task = ee.batch.Export.image.toAsset(
#     image=image_collection.mosaic(),  # You can mosaic all images or export them individually
#     description='interior-full-composites',
#     assetId='projects/ee-vegshiftsalaska/assets/interior_full_composites', 
#     region=geom,
#     scale=30,
#     crs='EPSG:3338',
#     maxPixels=1e13
# )
#export_task.start()

# %% Optionally, export pixel sampling data (CSV)
# landis_region_task = ee.batch.Export.table.toDrive(
#     collection=pv_sampling,
#     description=f'PixelVals_Landis_{year}_V2',
#     folder='Alaska_Proj',
#     fileFormat='CSV'
# )
# landis_region_task.start()
