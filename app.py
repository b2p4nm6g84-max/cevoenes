import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

# Arayüz Ayarları
st.set_page_config(page_title="Operasyon Merkezi", page_icon="📦", layout="centered")

# Google Sheets Bağlantı Ayarları
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
TABLO_ID = "11rhLP78QL64toHA8jHRC-0gHL-YheY-A4IbE2wvt4Bg"

@st.cache_resource
def google_baglan():
    if os.path.exists(".streamlit/secrets.json"):
        creds = Credentials.from_service_account_file(".streamlit/secrets.json", scopes=SCOPES)
    else:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    
    client = gspread.authorize(creds)
    return client.open_by_key(TABLO_ID)

def stok_getir():
    sheet = google_baglan().worksheet("Stok")
    veriler = sheet.get_all_values()
    if len(veriler) > 1:
        df = pd.DataFrame(veriler[1:], columns=["Ürün Adı", "Güncel Stok"])
        df = df[df["Ürün Adı"].str.strip() != ""] # Boş satırları ele
        df["Güncel Stok"] = pd.to_numeric(df["Güncel Stok"], errors="coerce").fillna(0).astype(int)
        return df
    else:
        return pd.DataFrame(columns=["Ürün Adı", "Güncel Stok"])

def rapor_getir():
    sheet = google_baglan().worksheet("Rapor")
    veriler = sheet.get_all_values()
    if len(veriler) > 1:
        return pd.DataFrame(veriler[1:], columns=["Tarih", "Kişi", "Rapor Detayı"])
    else:
        return pd.DataFrame(columns=["Tarih", "Kişi", "Rapor Detayı"])

st.sidebar.title("Kılıf Operasyon 📱")
menu = st.sidebar.radio("Menü Seçimi", ["📦 Canlı Stok", "📝 Rapor Ekle", "📊 Geçmiş Raporlar"])

if menu == "📦 Canlı Stok":
    st.header("Güncel Stok Durumu")
    try:
        df_stok = stok_getir()
        st.dataframe(df_stok, use_container_width=True)
        
        if not df_stok.empty:
            st.subheader("Stok Güncelle")
            col1, col2 = st.columns(2)
            with col1:
                secilen_urun = st.selectbox("Ürün Seç", df_stok["Ürün Adı"].tolist())
                islem_tipi = st.radio("İşlem", ["Stok Düş (-)", "Stok Ekle (+)"])
            with col2:
                adet = st.number_input("Adet", min_value=1, step=1)
                if st.button("Güncelle"):
                    sheet = google_baglan().worksheet("Stok")
                    kayitlar = sheet.get_all_records()
                    bulunan_satir = None
                    for index, kayit in enumerate(kayitlar):
                        if str(kayit.get("Ürün Adı", "")).strip() == str(secilen_urun).strip():
                            bulunan_satir = index + 2 # Başlık hariç olduğu için +2
                            break
                    
                    if bulunan_satir:
                        mevcut_deger = sheet.cell(bulunan_satir, 2).value
                        # DÜZELTME BURADA YAPILDI (if ve str arasına boşluk eklendi)
                        mevcut_stok = int(mevcut_deger) if str(mevcut_deger).isdigit() else 0
                        
                        yeni_stok = mevcut_stok - adet if islem_tipi == "Stok Düş (-)" else mevcut_stok + adet
                        if yeni_stok < 0: yeni_stok = 0
                        
                        sheet.update_cell(bulunan_satir, 2, yeni_stok)
                        st.success(f"{secilen_urun} stoğu güncellendi! Yeni Stok: {yeni_stok}")
                        st.rerun()
                    else:
                        st.error("Seçilen ürün tabloda bulunamadı.")
    except Exception as e:
        st.error(f"Tabloya bağlanılamadı. Hata: {e}")

elif menu == "📝 Rapor Ekle":
    st.header("Gün Sonu Raporu Gir")
    with st.form("rapor_formu"):
        kisi = st.selectbox("Ekip Üyesi", ["İlhan", "cevo", "enes"])
        yapilan_is = st.text_area("Bugün Neler Yaptın?")
        kaydet = st.form_submit_button("Raporu Gönder")
        
        if kaydet and yapilan_is.strip() != "":
            sheet = google_baglan().worksheet("Rapor")
            zaman = datetime.now().strftime("%Y-%m-%d %H:%M")
            sheet.append_row([zaman, kisi, yapilan_is])
            st.success("Rapor başarıyla kaydedildi!")

elif menu == "📊 Geçmiş Raporlar":
    st.header("Ekip Çalışma Geçmişi")
    try:
        df_rapor = rapor_getir()
        if not df_rapor.empty:
            df_rapor = df_rapor.iloc[::-1]
            for i, row in df_rapor.iterrows():
                st.info(f"**{row['Kişi']}** - {row['Tarih']}\n\n{row['Rapor Detayı']}")
        else:
            st.info("Henüz rapor yok.")
    except Exception as e:
        st.error(f"Raporlar çekilemedi. Hata: {e}")
