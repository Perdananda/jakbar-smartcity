from pathlib import Path
import json
import pandas as pd

BASE=Path(__file__).parent
CACHE=BASE/'data'/'osm'
CACHE.mkdir(parents=True,exist_ok=True)
DISTRICTS=['Taman Sari','Tambora','Grogol Petamburan','Palmerah','Kebon Jeruk','Kembangan','Cengkareng','Kalideres']
PLACE={'Taman Sari':'Taman Sari, West Jakarta, Jakarta, Indonesia','Tambora':'Tambora, West Jakarta, Jakarta, Indonesia','Grogol Petamburan':'Grogol Petamburan, West Jakarta, Jakarta, Indonesia','Palmerah':'Palmerah, West Jakarta, Jakarta, Indonesia','Kebon Jeruk':'Kebon Jeruk, West Jakarta, Jakarta, Indonesia','Kembangan':'Kembangan, West Jakarta, Jakarta, Indonesia','Cengkareng':'Cengkareng, West Jakarta, Jakarta, Indonesia','Kalideres':'Kalideres, West Jakarta, Jakarta, Indonesia'}
TAGS={'amenity':['school','university','college','hospital','clinic','marketplace','bus_station','restaurant','parking'],'shop':['mall','supermarket'],'highway':['bus_stop']}

def safe_name(d):return d.lower().replace(' ','_')
def paths(d):return {k:CACHE/f'{safe_name(d)}_{k}.geojson' for k in ('boundary','buildings','landuse','poi')}

# Kelompok POI tetap mencakup kategori V3 asli; cache tiap kelompok terpisah.
POI_GROUPS = {
    "education": {"amenity": ["school", "university", "college"]},
    "health": {"amenity": ["hospital", "clinic"]},
    "commerce": {"amenity": ["marketplace"], "shop": ["mall", "supermarket"]},
    "transport": {"amenity": ["bus_station", "parking"], "highway": ["bus_stop"]},
    "food": {"amenity": ["restaurant"]},
}
POI_COLUMNS = ["name", "category", "lat", "lon", "source"]


def _poi_rows(g, tags):
    rows = []
    for _, r in g.iterrows():
        geom = r.geometry
        if geom is None or geom.is_empty:
            continue
        point = geom if geom.geom_type == "Point" else geom.representative_point()
        categories = [(key, str(r.get(key))) for key in tags if pd.notna(r.get(key))]
        if not categories:
            continue
        cat = categories[0][1]
        name = r.get("name")
        rows.append({"name": str(name) if pd.notna(name) else cat,
                     "category": cat, "lat": point.y, "lon": point.x,
                     "source": "OpenStreetMap"})
    return pd.DataFrame(rows, columns=POI_COLUMNS)


def download(d, kinds, *, poi_pause=20, poi_retries=1, force_poi_groups=False):
    """Download requested layers. POI groups are cached individually and resumed safely."""
    import os
    import time
    import osmnx as ox
    import geopandas as gpd

    # Default OSMnx endpoint; optional override for known-working endpoint.
    endpoint = os.getenv("OVERPASS_URL", "").strip()
    if endpoint:
        ox.settings.overpass_url = endpoint
    ox.settings.requests_timeout = int(os.getenv("OVERPASS_TIMEOUT", "180"))
    ox.settings.use_cache = True
    place, p, messages = PLACE[d], paths(d), []

    if "boundary" in kinds:
        g = ox.geocode_to_gdf(place)
        g.to_file(p["boundary"], driver="GeoJSON")
        messages.append("boundary")
    if "buildings" in kinds:
        g = ox.features_from_place(place, tags={"building": True})
        g = g[g.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
        g.to_file(p["buildings"], driver="GeoJSON")
        messages.append(f"buildings: {len(g)}")
    if "landuse" in kinds:
        g = ox.features_from_place(place, tags={"landuse": True,
            "leisure": ["park", "garden", "nature_reserve"],
            "natural": ["wood", "grass", "scrub"]})
        g = g[g.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
        g.to_file(p["landuse"], driver="GeoJSON")
        messages.append(f"landuse: {len(g)}")

    if "poi" in kinds:
        if not p["boundary"].exists():
            raise FileNotFoundError(f"Boundary belum ada: {p['boundary']}. Sinkronkan boundary dahulu.")
        boundary = gpd.read_file(p["boundary"]).to_crs(4326)
        polygon = boundary.geometry.union_all()
        if polygon.is_empty:
            raise ValueError("Boundary kosong")
        part_paths = []
        failures = []
        for i, (group, tags) in enumerate(POI_GROUPS.items()):
            part = CACHE / f"{safe_name(d)}_poi_{group}.csv"
            part_paths.append(part)
            if part.exists() and part.stat().st_size > 0 and not force_poi_groups:
                print(f"  SKIP POI {group} (cache)", flush=True)
                continue
            if i:
                time.sleep(max(0, poi_pause))
            print(f"  DOWNLOAD POI {group}", flush=True)
            for attempt in range(max(1, poi_retries + 1)):
                try:
                    g = ox.features_from_polygon(polygon, tags=tags)
                    frame = _poi_rows(g, tags)
                    tmp = part.with_suffix(".csv.tmp")
                    frame.to_csv(tmp, index=False)
                    tmp.replace(part)
                    print(f"  OK POI {group}: {len(frame)} baris", flush=True)
                    break
                except Exception as exc:
                    msg = str(exc)
                    print(f"  ERROR POI {group}: {type(exc).__name__}: {msg[:250]}", flush=True)
                    # Jangan ulangi otomatis jika ada sinyal pembatasan akses.
                    if any(code in msg for code in ("429", "406", "Too Many Requests")):
                        raise RuntimeError("Overpass menolak request (406/429). Hentikan sinkronisasi dan coba nanti.") from exc
                    if attempt >= poi_retries:
                        failures.append(group)
                    else:
                        time.sleep(max(30, poi_pause))
        if failures:
            raise RuntimeError("POI belum lengkap, grup gagal: " + ", ".join(failures) +
                               ". Cache grup berhasil tersimpan; jalankan ulang nanti.")
        if not all(part.exists() and part.stat().st_size > 0 for part in part_paths):
            raise RuntimeError("Cache grup POI belum lengkap")
        merged = pd.concat([pd.read_csv(part) for part in part_paths], ignore_index=True)
        merged = merged.drop_duplicates(subset=["name", "category", "lat", "lon"])
        final = CACHE / f"{safe_name(d)}_poi.csv"
        tmp = final.with_suffix(".csv.tmp")
        merged.to_csv(tmp, index=False)
        tmp.replace(final)
        messages.append(f"poi: {len(merged)} (lengkap {len(POI_GROUPS)} grup)")
    return messages

def load_geo(d,k):
 p=paths(d)[k]
 if not p.exists():return None
 return json.loads(p.read_text(encoding='utf-8'))

def load_poi(d):
 p=CACHE/f'{safe_name(d)}_poi.csv'
 return pd.read_csv(p) if p.exists() else pd.DataFrame(columns=['name','category','lat','lon','source'])

def polygon_metrics(d):
 import geopandas as gpd
 p=paths(d)
 if not p['boundary'].exists():return None
 boundary=gpd.read_file(p['boundary']).to_crs(32748)
 region=boundary.geometry.union_all();area=region.area
 result={'area_km2':area/1e6,'building_pct':None,'green_pct':None,'building_count':None}
 if p['buildings'].exists():
  b=gpd.read_file(p['buildings']).to_crs(32748)
  b=b[b.geometry.geom_type.isin(['Polygon','MultiPolygon'])]
  clipped=b.geometry.intersection(region)
  result['building_count']=len(b);result['building_pct']=min(100,clipped.area.sum()/area*100)
 if p['landuse'].exists():
  g=gpd.read_file(p['landuse']).to_crs(32748)
  mask=pd.Series(False,index=g.index)
  for key,values in {'landuse':['forest','grass','meadow','recreation_ground','village_green','allotments','orchard'],'leisure':['park','garden','nature_reserve'],'natural':['wood','grass','scrub']}.items():
   if key in g.columns:mask=mask|g[key].isin(values)
  g=g[mask]; clipped=g.geometry.intersection(region)
  if len(clipped):
   # union prevents double-counting overlapping green polygons
   result['green_pct']=min(100,clipped.union_all().area/area*100)
  else:result['green_pct']=0.
 return result


def save_uploaded_geojson(district, layer, data):
 """Validate an uploaded WGS84 GeoJSON and store it in the selected district cache."""
 from shapely.geometry import shape
 if layer not in ('boundary','buildings','landuse','poi'):
  raise ValueError('Layer tidak dikenali')
 if data.get('type')=='FeatureCollection':
  features=data.get('features',[])
 elif data.get('type')=='Feature':
  features=[data]
 else:
  raise ValueError('Harus berupa GeoJSON FeatureCollection atau Feature')
 if not features:
  raise ValueError('GeoJSON tidak berisi fitur')
 valid=[]
 for feature in features:
  geom=feature.get('geometry')
  if not geom:continue
  geometry=shape(geom)
  if geometry.is_empty:continue
  if layer in ('boundary','buildings','landuse') and geometry.geom_type not in ('Polygon','MultiPolygon'):
   continue
  valid.append(feature)
 if not valid:
  raise ValueError('Tidak ada geometri yang cocok dengan layer (boundary/buildings/landuse membutuhkan Polygon)')
 collection={'type':'FeatureCollection','features':valid}
 target=paths(district)[layer]
 target.write_text(json.dumps(collection,ensure_ascii=False),encoding='utf-8')
 if layer=='poi':
  rows=[]
  for f in valid:
   geom=shape(f['geometry']);point=geom if geom.geom_type=='Point' else geom.representative_point()
   props=f.get('properties') or {}
   category=next((str(props[k]) for k in ('amenity','shop','highway','tourism','leisure','category') if props.get(k)), 'other')
   rows.append({'name':str(props.get('name') or category),'category':category,'lat':point.y,'lon':point.x,'source':'GeoJSON upload'})
  pd.DataFrame(rows,columns=['name','category','lat','lon','source']).to_csv(CACHE/f'{safe_name(district)}_poi.csv',index=False)
 return len(valid)
