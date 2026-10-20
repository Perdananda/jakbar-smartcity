"""Transparent heuristic triage, not a regulatory determination."""
def recommendations(district,metrics,pop_density=None,poi_count=None):
    rows=[]
    if pop_density is not None:
        if pop_density>=20000:
            rows.append(('Tinggi','Audit kapasitas layanan publik dan akses ruang terbuka',f'Kepadatan penduduk {pop_density:,.0f} jiwa/km²; ambang 20.000 adalah asumsi studi, bukan standar resmi.'))
        elif pop_density>=10000:
            rows.append(('Sedang','Evaluasi distribusi fasilitas dan akses ruang terbuka',f'Kepadatan penduduk {pop_density:,.0f} jiwa/km²; ambang studi.'))
    if metrics:
        b=metrics.get('building_pct');g=metrics.get('green_pct')
        if b is not None and b>=45:
            rows.append(('Tinggi','Investigasi kawasan tertutup bangunan dan opsi penghijauan atap',f'Building footprint OSM {b:.1f}% dari luas batas wilayah; verifikasi citra dan kekuatan struktur diperlukan.'))
        if g is not None and g<10:
            rows.append(('Sedang','Verifikasi ketersediaan ruang hijau dan peluang taman mikro',f'Area hijau bertag OSM {g:.1f}%; bukan ukuran vegetasi aktual.'))
    if poi_count is not None and poi_count>=200:
        rows.append(('Observasi','Survei aktivitas dan hambatan lalu lintas di sekitar klaster POI',f'{poi_count} POI terpetakan; jumlah POI bukan bukti kemacetan.'))
    if not rows:rows.append(('Data terbatas','Lengkapi data sebelum menentukan prioritas','Belum cukup bukti untuk klasifikasi tekanan kawasan.'))
    return rows
