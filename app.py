import io
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import folium
from folium.plugins import HeatMap,MarkerCluster
from streamlit_folium import st_folium
from PIL import Image
from osm_data import DISTRICTS,load_geo,load_poi,download,polygon_metrics,paths

ROOT=Path(__file__).parent
ENABLE_DATA_MANAGEMENT = False  # Public dashboard: disable dataset modifications
st.set_page_config(page_title='Jakbar Smart City V3.4 | MCE302',page_icon='🏙️',layout='wide')
st.title('🏙️ Jakarta Barat Smart City Intelligence')
st.caption('**Version 3.4** · Population + OSM Boundary Density · 19 Oktober 2026')
st.caption('MCE302 · OpenStreetMap · Urban Pressure · POI · YOLO · Spatial Data')
st.sidebar.header('🌐 Kontrol Web GIS')
st.sidebar.caption('Build v3.4 · MCE302')
district=st.sidebar.selectbox('Kecamatan',DISTRICTS)
section=st.sidebar.radio('Menu',['Overview','Density Overview','Policy Recommendation','POI & Mobility','Urban Green Space','CCTV & YOLO','Sumber & Metodologi'])
if ENABLE_DATA_MANAGEMENT:
 st.sidebar.divider()
 st.sidebar.subheader('🔄 Sinkronisasi OpenStreetMap')
 st.sidebar.caption('Data OSM diunduh hanya saat tombol ditekan, bukan setiap refresh. Download wilayah besar dapat memakan waktu.')
 kinds=st.sidebar.multiselect('Layer untuk diunduh',['boundary','poi','buildings','landuse'],default=['boundary','poi'])
 if st.sidebar.button('Ambil / perbarui OSM',disabled=not kinds):
  try:
   with st.spinner('Mengambil data dari OSM / Overpass...'):
    msg=download(district,kinds)
   st.sidebar.success('Berhasil: '+', '.join(msg));st.cache_data.clear()
  except Exception as e:st.sidebar.error('Gagal mengambil OSM. Coba lagi nanti atau pakai cache. '+str(e))


@st.cache_data(show_spinner=False)
def geo(d,k):return load_geo(d,k)
@st.cache_data(show_spinner=False)
def metrics(d):return polygon_metrics(d)
@st.cache_data(show_spinner=False)
def pois(d):return load_poi(d)

def center_for(d):
 b=geo(d,'boundary')
 if b:
  try:
   from shapely.geometry import shape
   g=shape(b['features'][0]['geometry']).representative_point();return [g.y,g.x]
  except Exception:pass
 return [-6.176,106.763]

def base_map(d,zoom=13):return folium.Map(location=center_for(d),zoom_start=zoom,tiles='OpenStreetMap',control_scale=True)

def draw_boundary(m,d):
 b=geo(d,'boundary')
 if b:folium.GeoJson(b,name='Batas Kecamatan',style_function=lambda _:dict(color='#f97316',weight=3,fillOpacity=.03)).add_to(m)

def draw_polygon_layer(m,d,k,color,max_features=2000):
 data=geo(d,k)
 if not data:return 0
 feats=data['features'];count=len(feats)
 # Simplify geometry on render for map performance; all features retained for area calculations
 from shapely.geometry import shape,mapping
 selected=feats if count<=max_features else feats[::max(1,int(np.ceil(count/max_features)))]
 out=[]
 for f in selected:
  try:
   geom=shape(f['geometry']).simplify(.00003,preserve_topology=True)
   out.append({'type':'Feature','geometry':mapping(geom),'properties':{}})
  except Exception:pass
 folium.GeoJson({'type':'FeatureCollection','features':out},name=k,style_function=lambda _,c=color:dict(color=c,weight=.6,fillColor=c,fillOpacity=.3)).add_to(m)
 return count

if ENABLE_DATA_MANAGEMENT:
 st.sidebar.divider()
 st.sidebar.subheader('📂 Upload GeoJSON')
 st.sidebar.caption('Pilih kecamatan dan jenis layer, lalu unggah GeoJSON. File akan disimpan sebagai cache untuk kecamatan tersebut.')
 geo_layer=st.sidebar.selectbox('Jenis layer GeoJSON',['boundary','buildings','landuse','poi'])
 geo_upload=st.sidebar.file_uploader('Pilih file .geojson atau .json',type=['geojson','json'],key='geojson_upload')
 if geo_upload is not None and st.sidebar.button('Simpan GeoJSON ke layer',type='primary'):
  try:
   import json
   from shapely.geometry import shape
   from osm_data import save_uploaded_geojson
   data=json.loads(geo_upload.getvalue().decode('utf-8-sig'))
   count=save_uploaded_geojson(district,geo_layer,data)
   st.cache_data.clear()
   st.sidebar.success(f'{count:,} fitur disimpan untuk {district} / {geo_layer}.')
   st.rerun()
  except Exception as e:
   st.sidebar.error(f'GeoJSON tidak dapat disimpan: {e}')

 uploaded=st.sidebar.file_uploader('Tambahkan POI dari CSV (opsional)',type=['csv'],help='Kolom: name,category,lat,lon')

poi=pois(district)
if ENABLE_DATA_MANAGEMENT:
 if uploaded is not None:
  try:
   extra=pd.read_csv(uploaded)
   if not {'name','category','lat','lon'}.issubset(extra.columns):st.sidebar.error('CSV wajib punya name, category, lat, lon')
   else:poi=pd.concat([poi,extra],ignore_index=True)
  except Exception as e:st.sidebar.error(str(e))
for k in ['lat','lon']:
 if k in poi:poi[k]=pd.to_numeric(poi[k],errors='coerce')
poi=poi.dropna(subset=['lat','lon']) if len(poi) else poi

if section=='Overview':
 st.subheader(f'Ringkasan Spasial — {district}')
 try:met=metrics(district)
 except Exception as e:met=None;st.error(f'Penghitungan geometri gagal: {e}')
 a,b,c,d=st.columns(4)
 a.metric('POI terpetakan',len(poi))
 b.metric('Bangunan OSM',f"{met['building_count']:,}" if met and met['building_count'] is not None else '—')
 c.metric('Building footprint',f"{met['building_pct']:.1f}%" if met and met['building_pct'] is not None else '—')
 d.metric('Ruang hijau OSM',f"{met['green_pct']:.1f}%" if met and met['green_pct'] is not None else '—')
 st.caption('Persentase dihitung dari geometri OSM yang tersedia, BUKAN pengukuran seluruh vegetasi melalui citra satelit. Data tidak lengkap dapat menghasilkan underestimate.')
 left,right=st.columns([1.5,1])
 with left:
  m=base_map(district);draw_boundary(m,district)
  if len(poi):
   cluster=MarkerCluster(name='POI').add_to(m)
   for r in poi.head(1500).itertuples():folium.Marker([r.lat,r.lon],tooltip=f'{r.name} · {r.category}').add_to(cluster)
  folium.LayerControl().add_to(m);st_folium(m,height=490,returned_objects=[],key='overview')
 with right:
  if len(poi):st.plotly_chart(px.bar(poi.category.value_counts().head(12).rename_axis('Kategori').reset_index(name='Jumlah'),x='Jumlah',y='Kategori',orientation='h',title='POI berdasarkan kategori'),use_container_width=True)
  else:st.info('Belum ada POI cache untuk kecamatan ini. Data POI belum tersedia pada cache server.')
 from official_data import density,normalize
 official=density()
 selected_density=official[official.kecamatan==normalize(district)] if len(official) else pd.DataFrame()
 if len(selected_density):
  st.metric('Kepadatan penduduk (penduduk impor / luas OSM)',f"{selected_density.iloc[0].density_per_km2:,.0f} jiwa/km²")
  st.caption(f"Periode: {int(selected_density.iloc[0].periode_data)}. Jumlah penduduk: data impor; luas: boundary OSM (geometris, bukan luas resmi BPS).")
 else:
  st.info('Density Overview memerlukan jumlah penduduk dari dataset resmi dan boundary OSM lokal. Data penduduk perlu disiapkan administrator; luas dihitung otomatis dari boundary.')
 st.caption('Buka menu **Density Overview** di sidebar untuk melihat perbandingan delapan kecamatan.')

elif section=='POI & Mobility':
 st.subheader(f'POI & Potensi Tekanan Aktivitas — {district}')
 st.caption('Heatmap = konsentrasi fasilitas yang dipetakan OSM; BUKAN kondisi kemacetan live atau IDW.')
 if not len(poi):st.warning('Belum ada POI. Data POI belum tersedia pada cache server.')
 else:
  cats=sorted(poi.category.astype(str).unique());selected=st.multiselect('Kategori POI',cats,default=cats)
  filtered=poi[poi.category.isin(selected)]
  m=base_map(district);draw_boundary(m,district)
  if len(filtered):
   HeatMap(filtered[['lat','lon']].values.tolist(),radius=20,blur=17,name='Heatmap POI').add_to(m)
   cluster=MarkerCluster(name='Marker POI').add_to(m)
   for r in filtered.head(1500).itertuples():folium.Marker([r.lat,r.lon],tooltip=f'{r.name} · {r.category}').add_to(cluster)
  folium.LayerControl().add_to(m);st_folium(m,height=520,returned_objects=[],key='poi')
  st.metric('POI terpilih',len(filtered));st.dataframe(filtered,use_container_width=True,hide_index=True)
  st.download_button('Unduh POI CSV',filtered.to_csv(index=False).encode('utf-8-sig'),file_name=f'poi_{district.lower().replace(" ","_")}.csv',mime='text/csv')

elif section=='Urban Green Space':
 st.subheader(f'Building & Landuse — {district}')
 st.caption('Taman Sari sudah memiliki data GeoJSON yang kamu unggah. Ketersediaan kecamatan lain mengikuti cache server.')
 opts=st.multiselect('Tampilkan layer',['Buildings','Landuse'],default=['Buildings','Landuse'])
 m=base_map(district);draw_boundary(m,district)
 for opt,k,color in [('Buildings','buildings','#ef4444'),('Landuse','landuse','#22c55e')]:
  if opt in opts:
   n=draw_polygon_layer(m,district,k,color)
   if n>2000:st.caption(f'Layer {k}: {n:,} fitur polygon di cache; sebagian fitur ditampilkan agar browser tetap responsif. Semua fitur dipakai untuk penghitungan.')
 folium.LayerControl().add_to(m);st_folium(m,height=530,returned_objects=[],key='urban')
 try:
  met=metrics(district)
  if met:
   st.json({k:round(v,2) if isinstance(v,float) else v for k,v in met.items()})
   st.caption('Building coverage adalah rasio luas footprint bangunan. Green coverage hanya tag hijau OSM yang tersedia. Kedua ukuran bukan hasil segmentasi AI dari notebook.')
  else:st.info('Data boundary, buildings, atau landuse belum tersedia pada cache server.')
 except Exception as e:st.error(str(e))

elif section=='Density Overview':
 from official_data import density,normalize,save_population_csv,sync_api,load_metadata,DATASET,osm_boundary_area
 st.subheader('Density Overview — Kepadatan Penduduk Jakarta Barat')
 st.caption('Jumlah penduduk: API resmi atau CSV tervalidasi. Luas: dihitung dari boundary OSM lokal. Cache penduduk tersimpan di data/official/.')
 st.markdown(f'[Referensi portal dataset penduduk]({DATASET})')
 st.info('Luas wilayah dihitung otomatis dari *_boundary.geojson (proyeksi EPSG:32748). Angka ini bukan luas administratif resmi BPS.')
 if ENABLE_DATA_MANAGEMENT:
  st.warning('Endpoint API dataset resmi belum ditentukan. Masukkan URL endpoint JSON/CSV yang benar-benar tersedia; tautan halaman portal bukan otomatis endpoint API.')
  mode=st.radio('Metode pembaruan',['API (sinkronisasi manual)','CSV (fallback)'],horizontal=True)
  if mode.startswith('API'):
   with st.form('official_api_sync'):
    api_url=st.text_input('URL endpoint API resmi (HTTPS)',placeholder='https://.../api/...')
    submitted=st.form_submit_button('Sinkronkan & validasi')
   if submitted:
    try:
     with st.spinner('Mengambil dan memvalidasi data...'):
      n=sync_api(api_url,'population')
     st.success(f'Sinkronisasi berhasil: {n} baris valid tersimpan.')
     st.rerun()
    except Exception as e:st.error(f'Sinkronisasi ditolak, cache lama dipertahankan: {e}')
  else:
   popfile=st.file_uploader('CSV jumlah penduduk per kecamatan',type=['csv'],key='population')
   if popfile and st.button('Validasi & simpan penduduk'):
    try:st.success(f'{save_population_csv(popfile.getvalue())} baris valid disimpan');st.rerun()
    except Exception as e:st.error(f'CSV ditolak, cache lama dipertahankan: {e}')
 with st.expander('Status sumber data dan riwayat sinkronisasi',expanded=True):
  meta=load_metadata()
  if not meta:st.info('Belum ada metadata sinkronisasi V3.4. Data impor versi sebelumnya tetap dapat dibaca.')
  for kind,label in [('population','Jumlah penduduk')]:
   item=meta.get(kind,{})
   st.write(f"**{label}:** {item.get('source','Belum tercatat')} · Terakhir sukses (UTC): {item.get('last_success_utc','—')} · {item.get('rows','—')} baris")
   if item.get('source_url'):st.caption('Endpoint: '+item['source_url'])
  area_df=osm_boundary_area()
  st.write(f'**Luas wilayah:** {len(area_df)}/8 boundary OSM tersedia · dihitung lokal (EPSG:32748)')
 df=density()
 if len(df):
  st.metric('Periode penduduk',str(int(df.periode_data.max())))
  st.caption('Kepadatan = jumlah penduduk dari data impor / luas geometri OSM (km²). Luas bukan angka administratif BPS. Periksa kesetaraan wilayah dan periode sebelum membuat keputusan.')
  chosen=df[df.kecamatan==normalize(district)]
  if len(chosen):
   x=chosen.iloc[0];k1,k2,k3=st.columns(3)
   k1.metric(f'Penduduk {district}',f'{x.jumlah_penduduk:,.0f} jiwa')
   k2.metric('Luas kecamatan',f'{x.luas_km2:,.2f} km²')
   k3.metric('Kepadatan',f'{x.density_per_km2:,.0f} jiwa/km²')
  st.plotly_chart(px.bar(df.sort_values('density_per_km2',ascending=False),x='kecamatan',y='density_per_km2',title='Density Overview: delapan kecamatan'),use_container_width=True)
  st.dataframe(df,use_container_width=True,hide_index=True)
  st.download_button('Unduh hasil density',df.to_csv(index=False).encode(),file_name='jakbar_density.csv')
 else:st.warning('Belum tersedia data penduduk yang valid atau boundary OSM lokal. Impor data jumlah penduduk resmi dan periksa file boundary.')
 st.caption('Kepadatan administratif bukan interpolasi IDW. Dataset baru yang tidak lolos validasi tidak menggantikan cache lama.')

elif section=='Policy Recommendation':
 from official_data import density,normalize
 from policy import recommendations
 st.subheader(f'Policy Recommendation — {district}')
 st.caption('Rekomendasi berbasis indikator bangunan, ruang hijau, POI, dan kepadatan resmi bila tersedia. Bukan keputusan pemerintah.')
 df=density();matches=df[df.kecamatan==normalize(district)] if len(df) else pd.DataFrame()
 popdensity=float(matches.iloc[0].density_per_km2) if len(matches) else None
 try:met=metrics(district)
 except Exception as e:met=None;st.warning(f'Metrik geometri tidak tersedia: {e}')
 rows=recommendations(district,met,popdensity,len(poi))
 st.dataframe(pd.DataFrame(rows,columns=['Prioritas indikatif','Usulan investigasi','Alasan / batasan']),use_container_width=True,hide_index=True)
 st.caption('Rekomendasi ini adalah aturan heuristik eksplisit untuk tugas akademik, bukan keputusan atau standar resmi Pemprov DKI. Perlu survei lapangan, validasi kualitas OSM, dan evaluasi dampak.')
 if popdensity is None:st.warning('Indikator kepadatan penduduk belum tersedia. Policy Recommendation saat ini hanya menggunakan metrik OSM dan POI; administrator perlu menyiapkan data resmi untuk melengkapinya.')
 st.info('Catatan PDP: prioritaskan data agregat tingkat kecamatan. Jangan gunakan nama, alamat individu, nomor telepon, atau nomor polisi untuk menyusun prioritas kebijakan.')

elif section=='CCTV & YOLO':
 st.subheader('CCTV Snapshot → YOLO Vehicle Detection')
 st.caption('Inferensi CPU VPS: snapshot manual, satu frame per proses; bukan live stream.')
 st.warning('🔒 Catatan UU PDP (UU No. 27 Tahun 2022): gambar CCTV dapat mengandung data pribadi seperti wajah dan nomor polisi yang dapat dikaitkan dengan individu. Gunakan gambar yang memiliki dasar pemrosesan yang sah dan izin penggunaan; hindari unggah/publikasi identitas, lakukan penyamaran bila perlu, batasi akses dan retensi. Dashboard ini tidak melakukan anonimisasi otomatis. Hasil YOLO hanya menghitung kendaraan, bukan identifikasi pemilik.')
 file=st.file_uploader('Upload JPG/PNG',type=['jpg','jpeg','png']);conf=st.slider('Confidence',.1,.9,.3,.05)
 if file:
  img=Image.open(io.BytesIO(file.read())).convert('RGB');img.thumbnail((1600,1600))
  a,b=st.columns([1.4,1])
  with a:st.image(img,caption='Snapshot asli',use_container_width=True)
  with b:
   if st.button('Jalankan YOLO',type='primary'):
    try:
     from ultralytics import YOLO
     with st.spinner('Inferensi model...'):
      res=YOLO('yolo11n.pt').predict(np.asarray(img),conf=conf,imgsz=640,device='cpu',verbose=False)[0]
      counts={k:0 for k in ['car','motorcycle','bus','truck']}
      for cls in res.boxes.cls.cpu().numpy().astype(int):
       k=res.names[int(cls)]
       if k in counts:counts[k]+=1
      score=counts['car']+.5*counts['motorcycle']+2*(counts['bus']+counts['truck'])
      st.metric('Kendaraan terlihat',sum(counts.values()));st.metric('Density score (heuristik)',round(score,1))
      st.dataframe(pd.DataFrame([{'Jenis':k,'Jumlah':v} for k,v in counts.items()]),hide_index=True)
      st.warning('Perlu validasi manual: deteksi dapat keliru karena sudut kamera, cuaca, pencahayaan, occlusion, dan domain shift. Skor adalah heuristik, bukan indeks kemacetan resmi. Jumlah per frame bukan arus kendaraan/jam.')
    except Exception as e:st.error(f'YOLO gagal: {e}')

else:
 st.subheader('Sumber Data, Proses & Batasan')
 st.markdown('''**Sumber:** OpenStreetMap contributors (© OSM), melalui ekstrak PBF lokal, GeoJSON yang telah disimpan, atau OSMnx/Overpass. Jumlah penduduk berasal dari CSV/API yang dikonfigurasi administrator setelah validasi; luas wilayah dihitung dari boundary OSM dan bukan angka luas administratif resmi BPS.\n\n**Notebook acuan:** `Jakarta Barat Urban Pressure Analysis.ipynb`, `Dense Settlement Map.ipynb`, dan `smart_traffic_integrated final.ipynb`. Hasil model AI kompleks dari notebook tersebut belum dieksekusi otomatis di dashboard ini.\n\n**Metode:** Building coverage = luas footprint bangunan / luas batas kecamatan. Green coverage = gabungan luas polygon bertag hijau / luas batas kecamatan. OSM tidak menjamin seluruh bangunan/vegetasi tercatat.\n\n**POI:** Dipetakan berdasarkan kategori OSM dan diproyeksikan menjadi titik representatif bila geometri polygon. Heatmap menggunakan pemulusan kernel, bukan IDW atau bukti kemacetan.\n\n**Interpolasi:** IDW belum diterapkan karena belum tersedia titik pengukuran variabel yang layak diinterpolasi. API kependudukan dapat disinkronkan secara manual setelah URL endpoint resmi dikonfigurasi. Luas OSM tidak boleh disebut luas resmi BPS.\n\n**Privasi dan PDP:** UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi perlu diperhatikan untuk foto/video CCTV, wajah, plat nomor yang dapat dikaitkan dengan seseorang, dan atribut individu. Gunakan dasar pemrosesan yang sah, minimisasi data, penyamaran bila diperlukan, pembatasan akses dan retensi. Dashboard tidak menjamin anonimisasi otomatis.''')
 st.write('Cache yang tersedia:')
 st.dataframe(pd.DataFrame([{'Layer':k,'Tersedia':p.exists(),'Ukuran MB':round(p.stat().st_size/1e6,2) if p.exists() else 0} for k,p in paths(district).items()]),hide_index=True)
 st.markdown('[© OpenStreetMap contributors](https://www.openstreetmap.org/copyright) · [BPS Jakarta Barat](https://jakbarkota.bps.go.id/) · [Satu Data Jakarta](https://satudata.jakarta.go.id/)')
st.divider();st.caption('V3.4 · MCE302 · Prototype Web GIS akademik · Data aktual OSM dengan cakupan yang bergantung pada kontribusi pemetaan')
