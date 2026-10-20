"""Explicitly sourced official data imports; no fabricated population values."""
from pathlib import Path
import pandas as pd
from osm_data import DISTRICTS

BASE=Path(__file__).parent/'data'/'official'
BASE.mkdir(parents=True,exist_ok=True)
DATASET='https://satudata.jakarta.go.id/open-data/detail?kategori=dataset&page_url=data-penduduk-provinsi-dki-jakarta-menurut-jenis-kelamin-dan-rasio-jenis-kelamin'
AREA_DATASET='https://satudata.jakarta.go.id/dashboard/dashboard-publik/dashboard-potensi-kelurahan?blok=kependudukan-dan-ketenagakerjaan'

def normalize(v):
    return str(v).upper().strip().replace('PAL MERAH','PALMERAH').replace('KOTA ADM. JAKARTA BARAT','JAKARTA BARAT')

def import_population(file_bytes):
    df=pd.read_csv(__import__('io').BytesIO(file_bytes),encoding='utf-8-sig')
    df.columns=[c.strip().lower() for c in df.columns]
    needed={'periode_data','wilayah','kecamatan','jumlah_penduduk'}
    if not needed.issubset(df.columns):
        raise ValueError('CSV membutuhkan kolom: '+', '.join(sorted(needed)))
    df=df[df.wilayah.map(normalize).str.contains('JAKARTA BARAT')].copy()
    df['kecamatan']=df.kecamatan.map(normalize)
    df['jumlah_penduduk']=pd.to_numeric(df.jumlah_penduduk,errors='coerce')
    df['periode_data']=pd.to_numeric(df.periode_data,errors='coerce')
    df=df[df.kecamatan.isin([normalize(d) for d in DISTRICTS])].dropna(subset=['periode_data','jumlah_penduduk'])
    if df.empty:raise ValueError('Tidak ditemukan baris Jakarta Barat yang valid')
    # Each row in the source is age/kelurahan; aggregate once per district and year.
    out=df.groupby(['periode_data','kecamatan'],as_index=False)['jumlah_penduduk'].sum()
    out.to_csv(BASE/'population.csv',index=False)
    return len(out)

def load_population():
    p=BASE/'population.csv'
    return pd.read_csv(p) if p.exists() else pd.DataFrame(columns=['periode_data','kecamatan','jumlah_penduduk'])

def import_area(file_bytes):
    df=pd.read_csv(__import__('io').BytesIO(file_bytes),encoding='utf-8-sig')
    df.columns=[c.strip().lower() for c in df.columns]
    if not {'kecamatan','luas_km2'}.issubset(df.columns):raise ValueError('CSV membutuhkan kecamatan, luas_km2')
    df['kecamatan']=df.kecamatan.map(normalize)
    df['luas_km2']=pd.to_numeric(df.luas_km2,errors='coerce')
    df=df[df.kecamatan.isin([normalize(d) for d in DISTRICTS]) & (df.luas_km2>0)]
    if df.kecamatan.duplicated().any():raise ValueError('Luas wilayah harus satu baris per kecamatan')
    df[['kecamatan','luas_km2']].to_csv(BASE/'area.csv',index=False)
    return len(df)

def osm_boundary_area():
    """Calculate district area from cached OSM boundary polygons in metric CRS.

    This is geometric OSM area, NOT an official BPS administrative area.
    Missing or invalid boundaries are omitted rather than fabricated.
    """
    import geopandas as gpd
    from osm_data import paths
    rows=[]
    for district in DISTRICTS:
        file=paths(district)['boundary']
        if not file.exists():
            continue
        try:
            frame=gpd.read_file(file)
            if frame.empty or frame.crs is None:
                continue
            frame=frame.to_crs('EPSG:32748')
            geometry=frame.geometry.dropna()
            if geometry.empty:
                continue
            region=geometry.union_all()
            area=float(region.area)/1_000_000
            if area>0:
                rows.append({'kecamatan':normalize(district),'luas_km2':area})
        except Exception:
            continue
    return pd.DataFrame(rows,columns=['kecamatan','luas_km2'])


def density():
    pop=load_population()
    if pop.empty:
        return pd.DataFrame()
    area=osm_boundary_area()
    if area.empty:
        return pd.DataFrame()
    pop=pop.copy()
    pop['kecamatan']=pop.kecamatan.map(normalize)
    pop['periode_data']=pd.to_numeric(pop.periode_data,errors='coerce')
    pop['jumlah_penduduk']=pd.to_numeric(pop.jumlah_penduduk,errors='coerce')
    pop=pop.dropna(subset=['periode_data','jumlah_penduduk'])
    if pop.empty:
        return pd.DataFrame()
    latest=pop[pop.periode_data==pop.periode_data.max()].copy()
    merged=latest.merge(area,on='kecamatan',how='inner',validate='one_to_one')
    merged['density_per_km2']=merged.jumlah_penduduk/merged.luas_km2
    merged['area_source']='OpenStreetMap boundary (geometric, not BPS)'
    return merged


# V3.3: safe API/CSV ingestion with last-known-good snapshots.
import io, json, os, shutil, tempfile
from datetime import datetime, timezone
from urllib.parse import urlparse

META=BASE/'metadata.json'
HISTORY=BASE/'history'
HISTORY.mkdir(parents=True,exist_ok=True)

ALIASES={
 'periode_data':('periode_data','tahun','year','periode'),
 'wilayah':('wilayah','kota_kabupaten','kota','kabupaten_kota'),
 'kecamatan':('kecamatan','nama_kecamatan','nama_kec'),
 'jumlah_penduduk':('jumlah_penduduk','total_penduduk','penduduk','jumlah'),
 'luas_km2':('luas_km2','luas_wilayah_km2','luas_kecamatan_km2'),
}

def _standardize(df, fields):
 df=df.copy();df.columns=[str(c).strip().lower().replace(' ','_') for c in df.columns]
 rename={}
 for target in fields:
  matches=[name for name in ALIASES[target] if name in df.columns]
  if not matches:raise ValueError(f'Kolom wajib tidak ditemukan: {target}. Kolom tersedia: {list(df.columns)}')
  rename[matches[0]]=target
 return df.rename(columns=rename)

def _normalize_district(v):
 import re
 x=re.sub(r'\s+',' ',str(v).upper().strip())
 x=x.replace('PAL MERAH','PALMERAH').replace('GROGOL PETAMBURAN','GROGOL PETAMBURAN')
 return x

def _validate_population(df):
 df=_standardize(df,['periode_data','kecamatan','jumlah_penduduk'])
 if 'wilayah' in df.columns:
  df=df[df.wilayah.astype(str).str.upper().str.contains('JAKARTA BARAT',na=False)]
 df['kecamatan']=df.kecamatan.map(_normalize_district)
 df=df[df.kecamatan.isin([_normalize_district(d) for d in DISTRICTS])].copy()
 df['jumlah_penduduk']=pd.to_numeric(df.jumlah_penduduk,errors='coerce')
 df['periode_data']=pd.to_numeric(df.periode_data,errors='coerce')
 if df[['periode_data','jumlah_penduduk']].isna().any().any():raise ValueError('Ada nilai periode/penduduk tidak valid')
 if (df.jumlah_penduduk<0).any():raise ValueError('Jumlah penduduk negatif')
 if df.empty:raise ValueError('Tidak ada data delapan kecamatan Jakarta Barat')
 # Source may have multiple age/sex/kelurahan rows. Group these only if they are
 # non-overlapping counts. Otherwise source mapping must be reviewed manually.
 result=df.groupby(['periode_data','kecamatan'],as_index=False)['jumlah_penduduk'].sum()
 latest=result[result.periode_data==result.periode_data.max()]
 missing=set(_normalize_district(d) for d in DISTRICTS)-set(latest.kecamatan)
 if missing:raise ValueError('Data tahun terbaru tidak mencakup kecamatan: '+', '.join(sorted(missing)))
 return result.sort_values(['periode_data','kecamatan'])

def _validate_area(df):
 df=_standardize(df,['kecamatan','luas_km2'])
 df['kecamatan']=df.kecamatan.map(_normalize_district)
 df=df[df.kecamatan.isin([_normalize_district(d) for d in DISTRICTS])].copy()
 df['luas_km2']=pd.to_numeric(df.luas_km2,errors='coerce')
 if df.luas_km2.isna().any() or (df.luas_km2<=0).any():raise ValueError('Luas wilayah tidak valid')
 if df.kecamatan.duplicated().any():raise ValueError('Ada kecamatan duplikat')
 missing=set(_normalize_district(d) for d in DISTRICTS)-set(df.kecamatan)
 if missing:raise ValueError('Luas wilayah tidak mencakup: '+', '.join(sorted(missing)))
 return df[['kecamatan','luas_km2']].sort_values('kecamatan')

def _commit(df,kind,source,source_url=None):
 target=BASE/('population.csv' if kind=='population' else 'area.csv')
 timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 if target.exists():shutil.copy2(target,HISTORY/f'{kind}_{timestamp}.csv')
 fd,temp=tempfile.mkstemp(dir=BASE,suffix='.tmp')
 try:
  with os.fdopen(fd,'w',encoding='utf-8',newline='') as handle:df.to_csv(handle,index=False)
  os.replace(temp,target)
 finally:
  if os.path.exists(temp):os.unlink(temp)
 metadata=load_metadata()
 metadata[kind]={'source':source,'source_url':source_url,'last_success_utc':datetime.now(timezone.utc).isoformat(),'rows':len(df),'period':int(df.periode_data.max()) if kind=='population' else None}
 META.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
 return len(df)

def load_metadata():
 try:return json.loads(META.read_text(encoding='utf-8'))
 except (OSError,ValueError):return {}

def save_population_csv(content):
 return _commit(_validate_population(pd.read_csv(io.BytesIO(content),encoding='utf-8-sig')),'population','CSV upload')

def save_area_csv(content):
 return _commit(_validate_area(pd.read_csv(io.BytesIO(content),encoding='utf-8-sig')),'area','CSV upload')

def sync_api(url,kind='population',timeout=30):
 if kind!='population':raise ValueError('V3.4 hanya menerima API jumlah penduduk; luas wilayah dihitung dari boundary GeoJSON.')
 # Admin-provided official API URL; no endpoint is assumed or invented.
 import requests
 parsed=urlparse(url)
 if parsed.scheme!='https' or not parsed.hostname:raise ValueError('API harus berupa URL HTTPS yang valid')
 # Prevent obvious private-network/loopback SSRF targets.
 import ipaddress,socket
 for addr in socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM):
  ip=ipaddress.ip_address(addr[4][0])
  if not ip.is_global:raise ValueError('Endpoint harus memakai alamat IP publik')
 response=requests.get(url,timeout=(10,timeout),headers={'User-Agent':'JakbarSmartCityAcademicDashboard/3.4','Accept':'application/json,text/csv'})
 response.raise_for_status()
 if len(response.content)>15_000_000:raise ValueError('Respons API lebih dari 15 MB')
 content_type=response.headers.get('Content-Type','').lower()
 if 'json' in content_type or response.content.lstrip(b'\xef\xbb\xbf \t\r\n').startswith((b'{',b'[')):
  obj=json.loads(response.content.decode('utf-8-sig'))
  if isinstance(obj,dict):
   for key in ('data','results','records','items'):
    if isinstance(obj.get(key),list):obj=obj[key];break
  if not isinstance(obj,list):raise ValueError('JSON API tidak berupa array record; perlu adapter khusus')
  df=pd.DataFrame(obj)
 else:
  if 'html' in content_type or response.content.lstrip().lower().startswith((b'<!doctype html',b'<html')):
   raise ValueError('URL mengembalikan halaman HTML, bukan data CSV/JSON. Gunakan URL unduh langsung atau endpoint API dataset.')
  df=pd.read_csv(io.BytesIO(response.content),encoding='utf-8-sig')
 result=_validate_population(df)
 return _commit(result,kind,'API',url)
