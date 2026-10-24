import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

# ==============================================================================
# 1. ARAYÜZ VE SAYFA YAPILANDIRMASI
# ==============================================================================
st.set_page_config(
    page_title="Kılıf Pro | Profesyonel Finans & Stok",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 14px 18px;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .badge-ok { background-color: #dcfce7; color: #166534; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 12px; display: inline-block; text-align: center; width: 100%; }
    .badge-warn { background-color: #fef9c3; color: #854d0e; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 12px; display: inline-block; text-align: center; width: 100%; }
    .badge-err { background-color: #fee2e2; color: #991b1b; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 12px; display: inline-block; text-align: center; width: 100%; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. GOOGLE SHEETS BAĞLANTI VE TABLO YAPISI
# ==============================================================================
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
TABLO_ID = "11rhLP78QL64toHA8jHRC-0gHL-YheY-A4IbE2wvt4Bg"

MODELLER = [
    ("IP1314", "iPhone 13 - 14 (Ortak Kılıf)"),
    ("IP15", "iPhone 15"),
    ("IP16", "iPhone 16"),
    ("IP14PM", "iPhone 14 Pro Max"),
    ("IP17PM", "iPhone 17 Pro Max")
]

@st.cache_resource
def google_baglan():
    if os.path.exists(".streamlit/secrets.json"):
        creds = Credentials.from_service_account_file(".streamlit/secrets.json", scopes=SCOPES)
    else:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(TABLO_ID)

@st.cache_data(ttl=30)
def verileri_yukle():
    sh = google_baglan()
    mevcut = [ws.title for ws in sh.worksheets()]
    if not all(s in mevcut for s in ["Stok_Detay", "Finans_Ayar", "Islem_Log"]):
        return False, None, None, None, None
        
    df_stok = pd.DataFrame(sh.worksheet("Stok_Detay").get_all_values())
    df_stok.columns = df_stok.iloc[0]
    df_stok = df_stok.drop(0).reset_index(drop=True)
    df_stok["Mevcut Stok"] = pd.to_numeric(df_stok["Mevcut Stok"], errors="coerce").fillna(0).astype(int)
    df_stok["Kritik Sınır"] = pd.to_numeric(df_stok["Kritik Sınır"], errors="coerce").fillna(3).astype(int)
    df_stok["Sheet_Satir"] = df_stok.index + 2
    
    df_fin = pd.DataFrame(sh.worksheet("Finans_Ayar").get_all_values())
    df_fin.columns = df_fin.iloc[0]
    df_fin = df_fin.drop(0).reset_index(drop=True)
    for col in df_fin.columns[1:]:
        df_fin[col] = pd.to_numeric(df_fin[col], errors="coerce").fillna(0.0)
        
    v_log = sh.worksheet("Islem_Log").get_all_values()
    df_log = pd.DataFrame(v_log[1:], columns=v_log[0]) if len(v_log) > 1 else pd.DataFrame(columns=["Tarih", "Ekip Üyesi", "Stok Kodu", "Model Grubu", "Renk Adı", "İşlem Türü", "Adet Değişimi", "Son Stok"])
    
    df_rap = pd.DataFrame(columns=["Tarih", "Kişi", "Rapor Detayı"])
    if "Rapor" in mevcut:
        v_r = sh.worksheet("Rapor").get_all_values()
        if len(v_r) > 1: df_rap = pd.DataFrame(v_r[1:], columns=["Tarih", "Kişi", "Rapor Detayı"])
            
    return True, df_stok, df_fin, df_log, df_rap

def tablo_kurulumu():
    sh = google_baglan()
    mevcut = [ws.title for ws in sh.worksheets()]
    
    ws_s = sh.worksheet("Stok_Detay") if "Stok_Detay" in mevcut else sh.add_worksheet("Stok_Detay", 65, 6)
    ws_s.clear()
    ws_s.update("A1:F51", [["Stok Kodu", "Model Grubu", "Renk Slotu", "Renk Adı", "Mevcut Stok", "Kritik Sınır"]] + [[f"{k}-R{r:02d}", m, f"Renk {r}", "", 10, 3] for k, m in MODELLER for r in range(1, 11)])
    
    ws_f = sh.worksheet("Finans_Ayar") if "Finans_Ayar" in mevcut else sh.add_worksheet("Finans_Ayar", 20, 11)
    ws_f.clear()
    ws_f.update("A1:K6", [["Model Grubu", "Gelis Fiyati", "Musteri Kargosu", "Vergi Orani (%)", "Sabit Vergi (TL)", "Shopier Komisyon (%)", "Shopier Sabit (TL)", "Senin Satis Fiyatin", "Toptan Koli Kargosu", "Koli Urun Adedi", "Paketleme Gideri (TL)"]] + [[m, 120.0, 45.0, 10.0, 0.0, 4.99, 0.49, 320.0, 150.0, 50, 5.0] for _, m in MODELLER])
    
    if "Islem_Log" not in mevcut:
        sh.add_worksheet("Islem_Log", 2000, 8).update("A1:H1", [["Tarih", "Ekip Üyesi", "Stok Kodu", "Model Grubu", "Renk Adı", "İşlem Türü", "Adet Değişimi", "Son Stok"]])
    if "Rapor" not in mevcut:
        sh.add_worksheet("Rapor", 500, 3).update("A1:C1", [["Tarih", "Kişi", "Rapor Detayı"]])
    st.cache_data.clear()

def stok_guncelle(satir, kod, model, renk, mevcut, degisim, tur, kisi):
    yeni = max(0, mevcut + degisim)
    sh = google_baglan()
    sh.worksheet("Stok_Detay").update_cell(satir, 5, yeni)
    sh.worksheet("Islem_Log").append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), kisi, kod, model, renk if renk else "İsimsiz", tur, degisim, yeni])
    st.session_state["undo"] = {"satir": satir, "kod": kod, "model": model, "renk": renk, "eski": mevcut, "yeni": yeni}
    st.cache_data.clear()

# ==============================================================================
# 3. YAN PANEL & GENEL KONTROLLER
# ==============================================================================
with st.sidebar:
    st.title("📱 Kılıf Pro v2.1")
    aktif_kisi = st.selectbox("👤 İşlem Yapan:", ["İlhan", "cevo", "enes"])
    
    if st.button("🔄 Verileri Yenile", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
        
    if "undo" in st.session_state and st.session_state["undo"]:
        u = st.session_state["undo"]
        st.info(f"Son İşlem: {u['kod']} ({u['eski']} ➔ {u['yeni']})")
        if st.button("↩️ Geri Al (Undo)", use_container_width=True):
            sh = google_baglan()
            sh.worksheet("Stok_Detay").update_cell(u["satir"], 5, u["eski"])
            sh.worksheet("Islem_Log").append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), aktif_kisi, u["kod"], u["model"], u["renk"], "Geri Al", u["eski"] - u["yeni"], u["eski"]])
            st.session_state["undo"] = None
            st.cache_data.clear()
            st.rerun()
            
    st.markdown("---")
    with st.expander("⚙️ Sistem Kurulumu"):
        if st.button("🚀 Tabloları Sıfırdan Kur", type="primary", use_container_width=True):
            tablo_kurulumu()
            st.success("Tablolar kuruldu!")
            st.rerun()

kuruldu, df_stok, df_fin, df_log, df_rap = verileri_yukle()
if not kurulu:
    st.warning("⚠️ Lütfen sol menüden **'⚙️ Sistem Kurulumu ➔ Tabloları Sıfırdan Kur'** butonuna tıklayın.")
    st.stop()

# Üst Özet Barı
c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 Toplam Stok", f"{int(df_stok['Mevcut Stok'].sum())} Adet")
c2.metric("⚠️ Kritik Renkler", f"{int(((df_stok['Mevcut Stok'] <= df_stok['Kritik Sınır']) & (df_stok['Mevcut Stok'] > 0)).sum())}")
c3.metric("🚨 Tükenen Renkler", f"{int((df_stok['Mevcut Stok'] == 0).sum())}")
c4.metric("🛒 Toplam Satış", f"{len(df_log[df_log['İşlem Türü'] == 'Satış (-1)']) if not df_log.empty else 0} Adet")

# ==============================================================================
# 4. ANA SEKMELER
# ==============================================================================
tab_stok, tab_finans, tab_solver, tab_log, tab_rapor = st.tabs([
    "📦 Canlı Stok & Butonlar",
    "💰 Dinamik Finans & %20 Kâr",
    "🎯 Solver Optimizasyonu",
    "📋 Satış Geçmişi",
    "📝 Raporlar"
])

# --- SEKME 1: STOK ---
with tab_stok:
    m_sec = st.selectbox("Model Seçin:", [m[1] for m in MODELLER])
    ara = st.text_input("🔍 Stok Kodu veya Renk Ara:", placeholder="Örn: Siyah, R01...")
    
    alt = df_stok[df_stok["Model Grubu"] == m_sec]
    if ara:
        alt = alt[alt["Renk Adı"].str.lower().str.contains(ara.lower()) | alt["Stok Kodu"].str.lower().str.contains(ara.lower())]
        
    for _, r in alt.iterrows():
        cols = st.columns([1.2, 1, 2.5, 1.1, 1.3, 1, 1])
        sat, kod, slot, renk, stok, kritik = int(r["Sheet_Satir"]), r["Stok Kodu"], r["Renk Slotu"], r["Renk Adı"], int(r["Mevcut Stok"]), int(r["Kritik Sınır"])
        
        cols[0].write(f"`{kod}`")
        cols[1].write(slot)
        cols[2].write(f"**{renk if renk else 'İsimsiz Renk'}**")
        cols[3].write(f"**{stok} Adet**")
        cols[4].markdown(('<span class="badge-err">TÜKENDİ</span>' if stok == 0 else ('<span class="badge-warn">KRİTİK</span>' if stok <= kritik else '<span class="badge-ok">YETERLİ</span>'), unsafe_allow_html=True)
        
        if cols[5].button("➕ +1", key=f"p_{kod}", use_container_width=True):
            stok_guncelle(sat, kod, m_sec, renk, stok, 1, "Stok Girişi (+1)", aktif_kisi)
            st.rerun()
        if cols[6].button("➖ -1", key=f"m_{kod}", use_container_width=True):
            if stok > 0:
                stok_guncelle(sat, kod, m_sec, renk, stok, -1, "Satış (-1)", aktif_kisi)
                st.rerun()
            else:
                st.toast("Stok zaten 0!", icon="⚠️")
                
    st.markdown("---")
    with st.expander("✏️ Renk İsimlerini ve Sınırları Düzenle"):
        ed = st.data_editor(alt[["Stok Kodu", "Renk Slotu", "Renk Adı", "Mevcut Stok", "Kritik Sınır"]], disabled=["Stok Kodu", "Renk Slotu"], use_container_width=True, hide_index=True)
        if st.button("💾 Değişiklikleri Kaydet", type="primary"):
            ws = google_baglan().worksheet("Stok_Detay")
            min_s, max_s = int(alt["Sheet_Satir"].min()), int(alt["Sheet_Satir"].max())
            ws.update(f"D{min_s}:F{max_s}", ed[["Renk Adı", "Mevcut Stok", "Kritik Sınır"]].values.tolist())
            st.cache_data.clear()
            st.success("Kaydedildi!")
            st.rerun()

# --- SEKME 2: FİNANS VE DİNAMİK FİYATLANDIRMA ---
with tab_finans:
    st.subheader("📊 Aylık Değişken Giderler (Aydan Aya Kolayca Güncelleyebilirsin)")
    st.caption("Kargo zamları, paketleme maliyetleri veya aylık sabit giderler değiştiğinde buradaki değerleri anında güncelleyebilirsin.")
    
    v_kargo = float(df_fin["Toptan Koli Kargosu"].iloc[0]) if not df_fin.empty else 150.0
    v_adet = int(df_fin["Koli Urun Adedi"].iloc[0]) if "Koli Urun Adedi" in df_fin.columns and not df_fin.empty else 50
    v_paket = float(df_fin["Paketleme Gideri (TL)"].iloc[0]) if "Paketleme Gideri (TL)" in df_fin.columns and not df_fin.empty else 5.0
    
    fc1, fc2, fc3, fc4 = st.columns(4)
    y_kargo = fc1.number_input("Toplam Koli Kargo Ücreti (₺):", value=v_kargo, step=10.0)
    y_adet = fc2.number_input("Kolideki Toplam Ürün Adedi:", value=v_adet, min_value=1, step=5)
    y_paket = fc3.number_input("Kılıf Başı Paketleme Gideri (₺):", value=v_paket, step=1.0)
    hedef_kar = fc4.number_input("Hedeflenen Net Kâr Oranı (%):", value=20.0, step=5.0)
    
    koli_kargo_payi = y_kargo / y_adet
    
    st.markdown("---")
    st.subheader("💵 Model Bazlı Gider ve Komisyon Ayarları")
    fin_ed = st.data_editor(
        df_fin[["Model Grubu", "Gelis Fiyati", "Musteri Kargosu", "Vergi Orani (%)", "Sabit Vergi (TL)", "Shopier Komisyon (%)", "Shopier Sabit (TL)", "Senin Satis Fiyatin"]],
        disabled=["Model Grubu"], use_container_width=True, hide_index=True
    )
    
    if st.button("💾 Finans ve Gider Ayarlarını Kaydet", type="primary"):
        ws_f = google_baglan().worksheet("Finans_Ayar")
        yeni_veri = []
        for _, r in fin_ed.iterrows():
            yeni_veri.append([r["Model Grubu"], float(r["Gelis Fiyati"]), float(r["Musteri Kargosu"]), float(r["Vergi Orani (%)"]), float(r["Sabit Vergi (TL)"]), float(r["Shopier Komisyon (%)"]), float(r["Shopier Sabit (TL)"]), float(r["Senin Satis Fiyatin"]), float(y_kargo), int(y_adet), float(y_paket)])
        ws_f.update("A2:K6", yeni_veri)
        st.cache_data.clear()
        st.success("Finans ayarları güncellendi!")
        st.rerun()

    st.markdown("---")
    st.subheader("📈 Profesyonel Başabaş & %20 Net Kâr Öneri Tablosu")
    
    sonuclar = []
    katsayi = 1.0 + (hedef_kar / 100.0)
    
    for _, r in fin_ed.iterrows():
        m, gelis, m_kargo = r["Model Grubu"], float(r["Gelis Fiyati"]), float(r["Musteri Kargosu"])
        v_oran = float(r["Vergi Orani (%)"]) / 100.0
        v_sabit = float(r["Sabit Vergi (TL)"])
        sh_oran = float(r["Shopier Komisyon (%)"]) / 100.0
        sh_sabit = float(r["Shopier Sabit (TL)"])
        satis = float(r["Senin Satis Fiyatin"])
        
        sabit_maliyet = gelis + koli_kargo_payi + m_kargo + y_paket + v_sabit + sh_sabit
        kesinti = (satis * (v_oran + sh_oran)) + v_sabit + sh_sabit + y_paket
        toplam_gider = gelis + koli_kargo_payi + m_kargo + kesinti
        
        # Profesyonel Ters Orantılı Başabaş Net Kâr Fiyatı
        payda = 1.0 - (katsayi * (v_oran + sh_oran))
        onerilen_fiyat = (sabit_maliyet * katsayi) / payda if payda > 0.05 else toplam_gider * katsayi
        
        net_kar = satis - toplam_gider
        satilan = len(df_log[(df_log["Model Grubu"] == m) & (df_log["İşlem Türü"] == "Satış (-1)")]) if not df_log.empty else 0
        
        sonuclar.append({
            "Model Grubu": m,
            "Birim Gider (Herşey Dahil)": f"{toplam_gider:.2f} ₺",
            f"💎 Net %{hedef_kar:.0f} Kârlı Önerilen Fiyat": f"{onerilen_fiyat:.2f} ₺",
            "Mevcut Satış Fiyatın": f"{satis:.2f} ₺",
            "Birim Net Kâr": f"{net_kar:.2f} ₺",
            "Satılan Adet": satilan,
            "Toplam Ciro (₺)": round(satilan * satis, 2),
            "Toplam Net Kâr (₺)": round(satilan * net_kar, 2)
        })
        
    df_sonuc = pd.DataFrame(sonuclar)
    st.dataframe(df_sonuc, use_container_width=True, hide_index=True)
    
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Toplam Ciro", f"{df_sonuc['Toplam Ciro (₺)'].sum():,.2f} ₺")
    sc2.metric("Toplam Net Kâr", f"{df_sonuc['Toplam Net Kâr (₺)'].sum():,.2f} ₺")

# --- SEKME 3: SOLVER OPTİMİZASYONU ---
with tab_solver:
    st.subheader("🎯 Bütçe & Sipariş Optimizasyonu (Solver)")
    b1, b2, b3 = st.columns(3)
    butce = b1.number_input("Alım Bütçesi (₺):", value=25000.0, step=1000.0)
    kapasite = b2.number_input("Maks. Adet:", value=250, step=10)
    min_s = b3.number_input("Model Başı Min:", value=10, step=5)
    
    if st.button("🚀 Optimum Dağılımı Hesapla", type="primary"):
        liste = []
        for _, r in fin_ed.iterrows():
            m, gelis = r["Model Grubu"], float(r["Gelis Fiyati"])
            satis = float(r["Senin Satis Fiyatin"])
            gider = gelis + koli_kargo_payi + float(r["Musteri Kargosu"]) + float(r["Paketleme Gideri (TL)"] if "Paketleme Gideri (TL)" in r else 5.0)
            liste.append({"Model": m, "Gelis": gelis, "Kar": satis - gider, "Adet": int(min_s)})
            
        harcanan = sum(x["Adet"] * x["Gelis"] for x in liste)
        toplam_a = sum(x["Adet"] for x in liste)
        
        if harcanan > butce or toplam_a > kapasite:
            st.error("Min adetler bütçeyi aşıyor!")
        else:
            sirali = sorted(liste, key=lambda x: x["Kar"] / max(1, x["Gelis"]), reverse=True)
            for m in sirali:
                while harcanan + m["Gelis"] <= butce and toplam_a + 1 <= kapasite:
                    m["Adet"] += 1
                    harcanan += m["Gelis"]
                    toplam_a += 1
            st.dataframe(pd.DataFrame(sirali), use_container_width=True, hide_index=True)
            st.success(f"Toplam Harcama: {harcanan:,.2f} ₺ | Toplam Adet: {toplam_a}")

# --- SEKME 4: LOG ---
with tab_log:
    st.subheader("📋 Satış ve Stok Geçmişi")
    if not df_log.empty:
        st.dataframe(df_log.iloc[::-1], use_container_width=True, hide_index=True)
    else:
        st.info("Kayıt yok.")

# --- SEKME 5: RAPORLAR ---
with tab_rapor:
    r1, r2 = st.columns([1, 1.5])
    with r1:
        with st.form("rap"):
            metin = st.text_area("Gün Sonu Raporu:")
            if st.form_submit_button("Gönder") and metin:
                google_baglan().worksheet("Rapor").append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), aktif_kisi, metin])
                st.cache_data.clear()
                st.rerun()
    with r2:
        if not df_rap.empty:
            for _, r in df_rap.iloc[::-1].iterrows():
                st.info(f"**{r['Kişi']}** ({r['Tarih']})\n\n{r['Rapor Detayı']}")
