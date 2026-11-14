"""Check that Earth Engine is authenticated and the Cloud project works.

    earthengine authenticate              # once per machine, opens a browser
    export EE_PROJECT=your-project-id
    python scripts/00_ee_check.py
"""
import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analogatlas import config as C  # noqa: E402

if not C.EE_PROJECT:
    sys.exit("Set EE_PROJECT to your Google Cloud project id first: export EE_PROJECT=...")

ee.Initialize(project=C.EE_PROJECT)

# Copernicus DEM GLO-30: elevation and slope at the Atacama (Salar de Atacama area)
pt = ee.Geometry.Point(-68.2, -23.5)
dem = ee.ImageCollection("COPERNICUS/DEM/GLO30").select("DEM").mosaic() \
    .setDefaultProjection("EPSG:4326", None, 30)
stats = ee.Image.cat(dem.rename("elev_m"), ee.Terrain.slope(dem).rename("slope_deg")) \
    .reduceRegion(ee.Reducer.median(), pt.buffer(5000), scale=90).getInfo()
print(f"Earth Engine OK (project {C.EE_PROJECT})")
print(f"Atacama test, 5 km radius: elevation {stats['elev_m']:.0f} m, median slope {stats['slope_deg']:.1f} deg")
