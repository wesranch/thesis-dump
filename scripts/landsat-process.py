# Landsat image processing and predictor variable dataset creation
# Wesley Rancher, Hana Matsumoto

# %% Start session
import ee
import pandas as pd
import geemap

ee.Authenticate()
ee.Initialize()

# %% Area of interest and topo data
AK_landscape = ee.FeatureCollection('projects/ee-vegshiftsalaska/assets/LandisModelRegion') 
#AK_landscape = ee.FeatureCollection('projects/ee-vegshiftsalaska/assets/Dalton_Landis') 
#AK_landscape = ee.FeatureCollection('projects/ee-vegshiftsalaska/assets/boreal_AK')
states = ee.FeatureCollection('TIGER/2016/States') 
#AK_landscape = states.filter(ee.Filter.eq('NAME', 'Alaska'))

Map = geemap.Map(center=[64, -152], zoom=5, basemap='Esri.WorldGrayCanvas')

# topographic data
topo_data = ee.ImageCollection('JAXA/ALOS/AW3D30/V3_2').select('DSM')
#project it
elevation = topo_data.mosaic().reproject(crs='EPSG:4326', scale=30)
slope = ee.Terrain.slope(topo_data.mosaic().reproject(crs='EPSG:4326', scale=30))
aspect = ee.Terrain.aspect(topo_data.mosaic().reproject(crs='EPSG:4326', scale=30))
topo_layers = elevation.addBands(slope).addBands(aspect)

# %% time range of interest
years = ee.List.sequence(2000, 2024)
year_info = years.size().getInfo()
year_info

#%% rescale from 0-65000 to approx. 0-1
def scale_and_offset(img):
    band_list = ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']
    qa_band = img.select('pixel_qa')
    mult_factor = ee.Image.constant(0.0000275)
    add_factor = ee.Image.constant(-0.2)
    
    scaled_bands = []
    for band in band_list:
        scaled_band = img.select(band).multiply(mult_factor).add(add_factor)
        scaled_bands.append(scaled_band)

    img_scaled = ee.Image(scaled_bands).addBands(qa_band)
    img_scaled = img_scaled.set({
        'SUN_AZIMUTH': img.get('SUN_AZIMUTH'),
        'SUN_ELEVATION': img.get('SUN_ELEVATION')
    })
    return img_scaled

# %% Landsat sensor corrections and cloud masks

# Hurni harmonization technique (not needed with C02)
# def harmonization(img):
#     slopes = ee.Image([0.8474, 0.8483, 0.9047, 0.8462, 0.8937, 0.9071])
#     intercepts = ee.Image([0.0003, 0.0088, 0.0061, 0.0412, 0.0254, 0.0172])
#     img_harm = img.select(['blue', 'green', 'red', 'nir', 'swir1', 'swir2']) \
#         .multiply(slopes) \
#         .add(intercepts.multiply(10000)) \
#         .int16()
#     return img.select().addBands(img_harm).addBands(img.select('pixel_qa'))

def cloud_mask_landsat8(img):
    quality_band = img.select('pixel_qa')
    dilated_cloud = (1 << 1)
    cloud_bit = (1 << 3)
    cloud_shadow = (1 << 4)
    water_bit = (1 << 7)
    cloud_mask = (quality_band.bitwiseAnd(cloud_bit).eq(0)) \
    .And(quality_band.bitwiseAnd(cloud_shadow).eq(0)) \
    .And(quality_band.bitwiseAnd(dilated_cloud).eq(0))

    # select pixels flagged as water
    water_mask = quality_band.bitwiseAnd(water_bit).neq(0)

    # Convert to bands
    cloudM = cloud_mask.select([0], ['cloudM'])
    waterM = water_mask.select([0], ['waterM'])
    image_cloud_masked = img.updateMask(cloud_mask).addBands([cloudM, waterM])
    return image_cloud_masked


#%% Illumination condition
# https://mygeoblog.com/2018/10/17/terrain-correction-in-gee/
def illuminationCondition(img):
    # image metadata about solar position (azimuth and zenith)
    azimuth_rad = ee.Image.constant(ee.Number(img.get('SUN_AZIMUTH')).multiply(3.14159265359).divide(180))
    zenith_rad = ee.Image.constant(ee.Number(90).subtract(img.get('SUN_ELEVATION')).multiply(3.14159265359).divide(180))
    
    #the DEM is in a computed projection so we need to reproject
    geom_test = img.geometry()#filter bounds by
    topo_data = ee.ImageCollection('JAXA/ALOS/AW3D30/V3_2') \
        .filterBounds(geom_test) \
        .select('DSM') \
        .mosaic() \
        .reproject(crs='EPSG:4326', scale=30)

    slope_rad = ee.Terrain.slope(topo_data).multiply(3.14159265359).divide(180)  # radians
    aspect_rad = ee.Terrain.aspect(topo_data).multiply(3.14159265359).divide(180)  # radians

    # Calculate Illumination Condition (IC)
    ##slope part
    cos_zenith = zenith_rad.cos()
    cos_slope = slope_rad.cos()
    slope_illumination = cos_zenith.multiply(cos_slope)
    ##aspect part
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
    mask2 = img.select('slope').gte(0) \
        .And(img.select('IC').gte(0)) \
        .And(img.select('nir').gt(-0.38)) #shift in scale from 0-1 to -.2-1.6
    img_plus_IC_mask2 = img.updateMask(mask2)
    #invalid_mask = img.select('nir').lte(-0.38)
    #img_with_na = img_plus_IC_mask2.where(invalid_mask, -9999)
    # bands to correct
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
        c = ee.Algorithms.If(a.gt(0), b.divide(a), ee.Number(0))
        c_image = ee.Image.constant(c)#needs to be an image constant
        
        #correction
        band_image = img_plus_IC_mask2.select(band)
        IC_image = img_plus_IC_mask2.select('IC')
        cosS_image = img_plus_IC_mask2.select('cosS')
        cosZ_image = img_plus_IC_mask2.select('cosZ')
        
        # apply the final formula
        scsc_output = img_plus_IC_mask2.expression(
            "((image * (cosB * cosZ + cvalue)) / (IC + cvalue))", {
                'image': band_image,
                'IC': IC_image,
                'cosB': cosS_image,
                'cosZ': cosZ_image,
                'cvalue': c_image})
        
        return scsc_output
    
    corrected_bands = [apply_scsc_corr(band) for band in band_list]
    img_scsc_corr = ee.Image(corrected_bands)
    return img_scsc_corr

#%% Vegetation indices
# normalized difference vegetation index
def ndvi_calc(img):
    ndvi = img.normalizedDifference(['nir', 'red']) \
              .rename('ndvi')
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
        .rename('evi')
    return evi
# modified normalized difference water index
def mndwi_calc(img):
    mndwi = img.normalizedDifference(['green', 'swir2']) \
              .rename('mndwi')
    return mndwi
# nbr
def nbr_calc(img):
    nbr = img.normalizedDifference(['nir', 'swir2']) \
            .rename('nbr')
    return nbr
# visible atmospherically resistant index
def vari_calc(img):
    vari = img.select('red') \
              .subtract(img.select('green')) \
              .divide(img.select('red').add(img.select('green')).subtract(img.select('blue'))) \
              .rename('vari')
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
        .rename('savi')
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
        .rename('tcb'))
    greenness = (img.multiply(greenness_coeff) \
        .reduce(ee.Reducer.sum()) \
        .rename('tcg'))
    wetness = (img.multiply(wetness_coeff) \
        .reduce(ee.Reducer.sum()) \
        .rename('tcw'))
    return ee.Image([brightness, greenness, wetness])

# %% Add indices and band names functions
def add_indices(img):
    ndvi = img.addBands(ndvi_calc(img)).toFloat()
    evi = img.addBands(evi_calc(img)).toFloat()
    mndwi = img.addBands(mndwi_calc(img)).toFloat()
    nbr = img.addBands(nbr_calc(img)).toFloat()
    vari = img.addBands(vari_calc(img)).toFloat()
    savi = img.addBands(savi_calc(img)).toFloat()
    tc = img.addBands(tasseled_cap(img)).toFloat()

    return img.addBands(ndvi).addBands(evi)\
              .addBands(mndwi).addBands(nbr)\
              .addBands(vari).addBands(savi).addBands(tc)

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

#%% Get Collection
# renaming bands
def get_landsat_collection_sr(sensor):
    if sensor in ['LC08', 'LC09']:
        bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL']
    else:  # for Landsat 5 and 7
        bands = ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7', 'QA_PIXEL']
    band_names_landsat = ['blue', 'green', 'red', 'nir', 'swir1', 'swir2', 'pixel_qa']
    cloud_threshold = 65
    collection_filtered_without_date = ee.ImageCollection('LANDSAT/' + sensor + '/C02/T1_L2') \
        .filterBounds(AK_landscape)\
        .filterMetadata('CLOUD_COVER', 'less_than', cloud_threshold) \
        .select(bands, band_names_landsat)  #rename bands
    return collection_filtered_without_date
tcc_params = {'bands':['red', 'green', 'blue'],
               "min":-0.1, "max":.1, "gamma":.3}
#%% Fire data
def process_mtbs(AK_landscape, year):

    mtbs_boundaries = ee.FeatureCollection("USFS/GTAC/MTBS/burned_area_boundaries/v1")\
                            .filterBounds(AK_landscape)
    
    def calculate_year_difference(feature):
        ignition_date = ee.Date(feature.get('Ig_Date'))
        year_difference = ee.Number(year).subtract(ignition_date.get('year'))
        return feature.set('tsf', year_difference)
    def find_overlaps(feature):
        overlaps = mtbs_boundaries.filterBounds(feature.geometry())
        return feature.set('total_fires', overlaps.size())

    tsf = mtbs_boundaries.map(calculate_year_difference).select('tsf', 'Ig_Date', 'Event_ID')
    overlapping_fires = mtbs_boundaries.map(find_overlaps)

    filtered_tsf = tsf.filter(ee.Filter.gte('tsf', 0))
    tsf_event_ids = filtered_tsf.aggregate_array('Event_ID')
    filtered_overlaps = overlapping_fires.filter(ee.Filter.inList('Event_ID', tsf_event_ids))

    # time since fire and number of fires
    tsf_image = filtered_tsf.reduceToImage(properties=['tsf'], reducer=ee.Reducer.max()).rename('tsf')
    tsf_image = tsf_image.unmask(-9999) 
    overlap_image = filtered_overlaps.reduceToImage(properties=['total_fires'], reducer=ee.Reducer.sum()).rename('total_fires')
    overlap_image = overlap_image.unmask(0)

    # MTBS
    mtbs_severity = ee.ImageCollection("USFS/GTAC/MTBS/annual_burn_severity_mosaics/v1")\
                        .filterBounds(AK_landscape)\
                        .filterDate('1984-01-01', ee.Date.fromYMD(year, 12, 31))

    severity_image = mtbs_severity.mean().rename('severity')  
    severity_image = severity_image.unmask(-9999)

    # severity layers
    severity_unburned = severity_image.gte(1).lt(2).rename('severity_unburned')
    severity_low = severity_image.gte(2).lt(3).rename('severity_low')
    severity_moderate = severity_image.gte(3).lt(4).rename('severity_moderate')
    severity_high = severity_image.gte(4).lt(5).rename('severity_high')

    # combine into single image
    severity_bands = ee.Image.cat([
        severity_unburned,
        severity_low,
        severity_moderate,
        severity_high
    ])

    return {
        'tsf_image': tsf_image,
        'overlap_image': overlap_image,
        'severity_bands': severity_bands
    }
# %% Iterate
#cafiPlots = ee.FeatureCollection(f'projects/ee-vegshiftsalaska/assets/sample-data/locations')

for i in range(year_info):
    year = years.get(i).getInfo()

    #mtbs for respective year
    fire_layers = process_mtbs(AK_landscape, year)

    #seasonal windows
    startSeason1 = ee.Date.fromYMD(year, 3, 1)
    endSeason1 = ee.Date.fromYMD(year, 5, 31)
    startSeason2 = ee.Date.fromYMD(year, 6, 1)
    endSeason2 = ee.Date.fromYMD(year, 8, 31)
    startSeason3 = ee.Date.fromYMD(year, 9, 1)
    endSeason3 = ee.Date.fromYMD(year, 11, 30)
        
    ################################################
    def get_landsat_Images(sensor, AK_landscape, startSeason, endSeason):  
        collection = get_landsat_collection_sr(sensor)
        cleaned_images = (collection
            .filterBounds(AK_landscape)
            .filterDate(startSeason, endSeason)
            .map(scale_and_offset)
            .map(cloud_mask_landsat8)
            #.map(illuminationCondition)
            #.map(illumination_correction)
            .map(add_indices))
        return cleaned_images

    # function to bring everything together            
    def make_ls(AK_landscape):
        tcc_bands = ee.List(['red', 'green', 'blue'])
        bands_indices = ee.List(['ndvi', 'evi', 'mndwi', 'nbr', 'vari', 'savi', 'tcb', 'tcg', 'tcw'])
        sensors = ['LC08', 'LC09', 'LE07', 'LT05']
        spring_images = ee.ImageCollection([])
        summer_images = ee.ImageCollection([])
        fall_images = ee.ImageCollection([])

        for sensor in sensors:
            spring_images = spring_images.merge(get_landsat_Images(sensor, AK_landscape, startSeason1, endSeason1))
            summer_images = summer_images.merge(get_landsat_Images(sensor, AK_landscape, startSeason2, endSeason2))
            fall_images = fall_images.merge(get_landsat_Images(sensor, AK_landscape, startSeason3, endSeason3))
        
        # Median composites by season
        springtime = add_suffix(spring_images.median().select(bands_indices), 'spring')
        summertime = add_suffix(summer_images.median().select(bands_indices), 'summer')
        falltime = add_suffix(fall_images.median().select(bands_indices), 'fall')
        #green_up = add_suffix(summer_images.median().subtract(spring_images.median()).select(bands_indices), 'up')
        #brown_down = add_suffix(fall_images.median().subtract(summer_images.median()).select(bands_indices), 'down')

        # add each composite as bands
        return springtime.addBands(summertime).addBands(falltime)


    #make composite
    #tcc_bands_sum = ee.List(['red_summer', 'green_summer', 'blue_summer'])
    landsat_composite = make_ls(AK_landscape)\
        .clip(AK_landscape)\
        .reproject(crs='EPSG:3338', scale=30)
    #info = landsat_composite.getInfo()
    #Map.addLayer(landsat_composite, tcc_params, f'tcc {year} boreal 13')
    fire = landsat_composite\
        .addBands(fire_layers['tsf_image'])\
        .addBands(fire_layers['overlap_image'])\
        .addBands(fire_layers['severity_bands'])
    landsat_and_topo_layers = fire.addBands(topo_layers)\
        .reproject(crs='EPSG:3338', scale=30)\
        .clip(AK_landscape)

    #save composite
    geom = AK_landscape.geometry()
    task = ee.batch.Export.image.toDrive(
        image=landsat_and_topo_layers.toFloat(),
        description=f'landis-tile-{year}',
        folder='Final_Composites',
        region=geom,
        scale=30,
        crs='EPSG:3338',
        maxPixels=1e13)
    task.start()


    # Sampling process
    def get_pixel_values(f, img):
        return f.setMulti(img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=f.geometry(),
            scale=30,
            crs='EPSG:3338'))
    
    #cafiPlots = ee.FeatureCollection(f'projects/ee-vegshiftsalaska/assets/sample-data/biomass_{year}')
    #def sample_pixels(f):
    #    return get_pixel_values(f)

    #pv_sampling = cafiPlots.map(lambda f: get_pixel_values(f, landsat_and_topo_layers))
    #task_sampling = ee.batch.Export.table.toDrive(
    #   collection=pv_sampling,
    #   description=f'pixel-vals-fire-{year}',
    #   folder='Sampled_Alaska',
    #   fileFormat='CSV')
    #task_sampling.start()

    #clean up
    landsat_composite = None
    landsat_and_topo_layers = None
    springtime = None
    falltime = None
    falltime = None

# %% Export true color
def export_median_true_color_composite(years):
    start_month = 5
    end_month = 8
    sensors = ['LC08', 'LC09', 'LT05']
  
    merged = ee.ImageCollection([])
    
    for i in range(years.length().getInfo()):
        year = years.get(i).getInfo()
        start_date = ee.Date.fromYMD(year, start_month, 1)
        end_date = ee.Date.fromYMD(year, end_month, 31)
        
        for sensor in sensors:
            collection = get_landsat_collection_sr(sensor) \
                .filterDate(start_date, end_date) \
                .map(cloud_mask_landsat8) \
                .map(scale_and_offset)

            merged = merged.merge(collection)
    
    median_image = merged.median()

    # Select RGB bands and rename
    tcc = median_image.select(['red', 'green', 'blue'])
    Map.addLayer(tcc, tcc_params, f"true AHH {years.get(0).getInfo()}-{years.get(-1).getInfo()}")


shpfile = ee.FeatureCollection('projects/ee-vegshiftsalaska/assets/oceans-extent-basemap2')
AK_landscape_inv = shpfile.geometry().difference(AK_landscape.geometry())
selected_years = ee.List.sequence(1984, 2024)
years = selected_years
export_median_true_color_composite(selected_years)

Map.addLayer(AK_landscape, {}, 'boreal')


# %%
