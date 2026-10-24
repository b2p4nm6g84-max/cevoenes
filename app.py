import os
from datetime import datetime

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# =============================================================================
# 1. SAYFA YAPILANDIRMASI
# =============================================================================

st.set_page_config(
    page_title="Kılıf Pro | Profesyonel Finans & Stok",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded",
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
    .badge-ok {
        background-color: #dcfce7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 12px;
        display: inline-block;
        text-align: center;
        width: 100%;
    }
    .badge-warn {
        background-color: #fef9c3;
        color: #854d0e;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 12px;
        display: inline-block;
        text-align: center;
        width: 100%;
    }
    .badge-err {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 12px;
        display: inline-block;
        text-align: center;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# 2. GOOGLE SHEETS AYARLARI
# =============================================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

TABLO_ID = "11rhLP78QL64toHA8jHRC-0gHL-YheY-A4IbE2wvt4Bg"

MODELLER = [
    ("IP1314", "iPhone 13 - 14 (Ortak Kılıf)"),
    ("IP15", "iPhone 15"),
    ("IP16", "iPhone 16"),
    ("IP14PM", "iPhone 14 Pro Max"),
    ("IP17PM", "iPhone 17 Pro Max"),
]

STOK_KOLONLARI = [
    "Stok Kodu",
    "Model Grubu",
    "Renk Slotu",
    "Renk Adı",
    "Mevcut Stok",
    "Kritik Sınır",
]

FINANS_KOLONLARI = [
    "Model Grubu",
    "Gelis Fiyati",
    "Musteri Kargosu",
    "Vergi Orani (%)",
    "Sabit Vergi (TL)",
    "Shopier Komisyon (%)",
    "Shopier Sabit (TL)",
    "Senin Satis Fiyatin",
    "Toptan Koli Kargosu",
    "Koli Urun Adedi",
    "Paketleme Gideri (TL)",
]

LOG_KOLONLARI = [
    "Tarih",
    "Ekip Üyesi",
    "Stok Kodu",
    "Model Grubu",
    "Renk Adı",
    "İşlem Türü",
    "Adet Değişimi",
    "Son Stok",
]

RAPOR_KOLONLARI = ["Tarih", "Kişi", "Rapor Detayı"]


# =============================================================================
# 3. GOOGLE SHEETS BAĞLANTISI
# =============================================================================

@st.cache_resource
def google_baglan():
    """Google Sheets bağlantısını kurar."""

    local_secrets = ".streamlit/secrets.json"

    if os.path.exists(local_secrets):
        creds = Credentials.from_service_account_file(
            local_secrets,
            scopes=SCOPES,
        )
    else:
        if "gcp_service_account" not in st.secrets:
            raise RuntimeError(
                "Google servis hesabı bulunamadı. "
                "Streamlit Cloud > Settings > Secrets bölümüne "
                "[gcp_service_account] yapılandırmasını ekleyin."
            )

        creds_dict = dict(st.secrets["gcp_service_account"])

        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=SCOPES,
        )

    client = gspread.authorize(creds)

    return client.open_by_key(TABLO_ID)


def worksheet_dataframe(sh, sayfa_adi, varsayilan_kolonlar):
    """Google Sheets sayfasını DataFrame'e dönüştürür."""

    values = sh.worksheet(sayfa_adi).get_all_values()

    if not values:
        return pd.DataFrame(columns=varsayilan_kolonlar)

    basliklar = values[0]

    if not basliklar:
        return pd.DataFrame(columns=varsayilan_kolonlar)

    satirlar = values[1:]

    if not satirlar:
        return pd.DataFrame(columns=basliklar)

    # Eksik veya fazla hücreleri başlık sayısına göre düzenle.
    duzenlenmis = []

    for satir in satirlar:
        satir = list(satir[:len(basliklar)])

        while len(satir) < len(basliklar):
            satir.append("")

        duzenlenmis.append(satir)

    return pd.DataFrame(duzenlenmis, columns=basliklar)


@st.cache_data(ttl=30)
def verileri_yukle():
    """Stok, finans, işlem ve rapor verilerini yükler."""

    try:
        sh = google_baglan()

        mevcut_sayfalar = [
            ws.title for ws in sh.worksheets()
        ]

        gerekli_sayfalar = [
            "Stok_Detay",
            "Finans_Ayar",
            "Islem_Log",
        ]

        eksik_sayfalar = [
            sayfa for sayfa in gerekli_sayfalar
            if sayfa not in mevcut_sayfalar
        ]

        if eksik_sayfalar:
            return (
                False, None, None, None, None,
                "Eksik sayfalar: " + ", ".join(eksik_sayfalar)
            )

        # STOK
        df_stok = worksheet_dataframe(
            sh, "Stok_Detay", STOK_KOLONLARI
        )

        eksik_stok = [
            kolon for kolon in STOK_KOLONLARI
            if kolon not in df_stok.columns
        ]

        if eksik_stok:
            return (
                False, None, None, None, None,
                "Stok sütunları eksik: " + ", ".join(eksik_stok)
            )

        if df_stok.empty:
            return (
                False, None, None, None, None,
                "Stok_Detay sayfasında henüz ürün bulunmuyor."
            )

        df_stok["Mevcut Stok"] = (
            pd.to_numeric(df_stok["Mevcut Stok"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
            .astype(int)
        )

        df_stok["Kritik Sınır"] = (
            pd.to_numeric(df_stok["Kritik Sınır"], errors="coerce")
            .fillna(3)
            .clip(lower=0)
            .astype(int)
        )

        # Başlık birinci satırdır, veriler ikinci satırdan başlar.
        df_stok["Sheet_Satir"] = range(2, len(df_stok) + 2)

        # FİNANS
        df_fin = worksheet_dataframe(
            sh, "Finans_Ayar", FINANS_KOLONLARI
        )

        eksik_finans = [
            kolon for kolon in FINANS_KOLONLARI
            if kolon not in df_fin.columns
        ]

        if eksik_finans:
            return (
                False, None, None, None, None,
                "Finans sütunları eksik: " + ", ".join(eksik_finans)
            )

        if df_fin.empty:
            return (
                False, None, None, None, None,
                "Finans_Ayar sayfasında henüz veri bulunmuyor."
            )

        for kolon in FINANS_KOLONLARI[1:]:
            df_fin[kolon] = (
                pd.to_numeric(df_fin[kolon], errors="coerce")
                .fillna(0.0)
            )

        df_fin["Koli Urun Adedi"] = (
            df_fin["Koli Urun Adedi"].clip(lower=1).astype(int)
        )

        # İŞLEM GEÇMİŞİ
        df_log = worksheet_dataframe(
            sh, "Islem_Log", LOG_KOLONLARI
        )

        for kolon in LOG_KOLONLARI:
            if kolon not in df_log.columns:
                df_log[kolon] = ""

        df_log = df_log[LOG_KOLONLARI]

        # RAPORLAR
        if "Rapor" in mevcut_sayfalar:
            df_rap = worksheet_dataframe(
                sh, "Rapor", RAPOR_KOLONLARI
            )

            for kolon in RAPOR_KOLONLARI:
                if kolon not in df_rap.columns:
                    df_rap[kolon] = ""

            df_rap = df_rap[RAPOR_KOLONLARI]
        else:
            df_rap = pd.DataFrame(columns=RAPOR_KOLONLARI)

        return True, df_stok, df_fin, df_log, df_rap, None

    except Exception as e:
        return (
            False, None, None, None, None,
            f"{type(e).__name__}: {e}"
        )


# =============================================================================
# 4. TABLO KURULUMU
# =============================================================================

def tablo_kurulumu():
    """
    Eksik sayfaları oluşturur.
    Mevcut sayfaları silmez veya sıfırlamaz.
    """

    sh = google_baglan()

    mevcut = [ws.title for ws in sh.worksheets()]

    if "Stok_Detay" not in mevcut:
        ws_stok = sh.add_worksheet(
            title="Stok_Detay",
            rows=51,
            cols=6,
        )

        stok_verisi = [STOK_KOLONLARI]

        for kod, model in MODELLER:
            for r in range(1, 11):
                stok_verisi.append([
                    f"{kod}-R{r:02d}",
                    model,
                    f"Renk {r}",
                    "",
                    10,
                    3,
                ])

        ws_stok.update("A1:F51", stok_verisi)

    if "Finans_Ayar" not in mevcut:
        ws_finans = sh.add_worksheet(
            title="Finans_Ayar",
            rows=6,
            cols=11,
        )

        finans_verisi = [FINANS_KOLONLARI]

        for _, model in MODELLER:
            finans_verisi.append([
                model,
                120.0,
                45.0,
                10.0,
                0.0,
                4.99,
                0.49,
                320.0,
                150.0,
                50,
                5.0,
            ])

        ws_finans.update("A1:K6", finans_verisi)

    if "Islem_Log" not in mevcut:
        ws_log = sh.add_worksheet(
            title="Islem_Log",
            rows=2000,
            cols=8,
        )
        ws_log.update("A1:H1", [LOG_KOLONLARI])

    if "Rapor" not in mevcut:
        ws_rapor = sh.add_worksheet(
            title="Rapor",
            rows=500,
            cols=3,
        )
        ws_rapor.update("A1:C1", [RAPOR_KOLONLARI])

    st.cache_data.clear()


# =============================================================================
# 5. STOK GÜNCELLEME
# =============================================================================

def stok_guncelle(
    satir,
    kod,
    model,
    renk,
    mevcut,
    degisim,
    tur,
    kisi,
):
    """Stok miktarını değiştirir ve işlem geçmişine kaydeder."""

    mevcut = int(mevcut)
    yeni = max(0, mevcut + int(degisim))

    sh = google_baglan()

    sh.worksheet("Stok_Detay").update_cell(
        int(satir), 5, yeni
    )

    sh.worksheet("Islem_Log").append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        kisi,
        kod,
        model,
        renk if renk and renk != "nan" else "İsimsiz",
        tur,
        int(degisim),
        yeni,
    ])

    st.session_state["undo"] = {
        "satir": int(satir),
        "kod": kod,
        "model": model,
        "renk": renk,
        "eski": mevcut,
        "yeni": yeni,
    }

    st.cache_data.clear()


# =============================================================================
# 6. YAN PANEL
# =============================================================================

with st.sidebar:

    st.title("📱 Kılıf Pro v2.1")

    aktif_kisi = st.selectbox(
        "👤 İşlem Yapan:",
        ["İlhan", "cevo", "enes"],
    )

    if st.button(
        "🔄 Verileri Yenile",
        use_container_width=True,
    ):
        st.cache_data.clear()
        st.rerun()

    if st.session_state.get("undo"):

        u = st.session_state["undo"]

        st.info(
            f"Son İşlem: {u['kod']} "
            f"({u['eski']} ➔ {u['yeni']})"
        )

        if st.button(
            "↩️ Geri Al (Undo)",
            use_container_width=True,
        ):
            try:
                sh = google_baglan()

                ws_stok = sh.worksheet("Stok_Detay")
                ws_log = sh.worksheet("Islem_Log")

                ws_stok.update_cell(
                    u["satir"], 5, u["eski"]
                )

                ws_log.append_row([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    aktif_kisi,
                    u["kod"],
                    u["model"],
                    u["renk"] if u["renk"] else "İsimsiz",
                    "Geri Al",
                    u["eski"] - u["yeni"],
                    u["eski"],
                ])

                st.session_state["undo"] = None
                st.cache_data.clear()
                st.success("Son işlem geri alındı.")
                st.rerun()

            except Exception as e:
                st.error(f"Geri alma işlemi başarısız: {e}")

    st.markdown("---")

    with st.expander("⚙️ Sistem Kurulumu"):

        st.warning(
            "Bu işlem mevcut tabloları silmez. "
            "Yalnızca eksik sayfaları oluşturur."
        )

        if st.button(
            "🚀 Eksik Tabloları Oluştur",
            type="primary",
            use_container_width=True,
        ):
            try:
                tablo_kurulumu()
                st.success("Eksik tablolar oluşturuldu.")
                st.rerun()

            except Exception as e:
                st.error(f"Tablo kurulumu başarısız: {e}")


# =============================================================================
# 7. VERİLERİ YÜKLE
# =============================================================================

kuruldu, df_stok, df_fin, df_log, df_rap, yukleme_hatasi = (
    verileri_yukle()
)

if not kuruldu:

    st.warning(
        "⚠️ Google Sheets tabloları henüz oluşturulmamış "
        "veya veriler yüklenemedi."
    )

    if yukleme_hatasi:
        st.error(f"Bağlantı / veri hatası: {yukleme_hatasi}")

    st.info(
        "Sol menüden Sistem Kurulumu bölümüne girip "
        "'Eksik Tabloları Oluştur' butonunu kullanın. "
        "Google servis hesabının Google Sheets dosyasına "
        "erişim izni olduğundan emin olun."
    )

    st.stop()


# =============================================================================
# 8. ÜST ÖZET
# =============================================================================

c1, c2, c3, c4 = st.columns(4)

toplam_stok = int(df_stok["Mevcut Stok"].sum())

kritik_sayi = int((
    (df_stok["Mevcut Stok"] <= df_stok["Kritik Sınır"])
    & (df_stok["Mevcut Stok"] > 0)
).sum())

tukenen_sayi = int(
    (df_stok["Mevcut Stok"] == 0).sum()
)

satis_sayi = (
    int((df_log["İşlem Türü"] == "Satış (-1)").sum())
    if not df_log.empty else 0
)

c1.metric("📦 Toplam Stok", f"{toplam_stok} Adet")
c2.metric("⚠️ Kritik Renkler", str(kritik_sayi))
c3.metric("🚨 Tükenen Renkler", str(tukenen_sayi))
c4.metric("🛒 Toplam Satış", f"{satis_sayi} Adet")


# =============================================================================
# 9. ANA SEKMELER
# =============================================================================

tab_stok, tab_finans, tab_solver, tab_log, tab_rapor = st.tabs([
    "📦 Canlı Stok & Butonlar",
    "💰 Dinamik Finans & Kâr",
    "🎯 Solver Optimizasyonu",
    "📋 Satış Geçmişi",
    "📝 Raporlar",
])


# =============================================================================
# SEKME 1: STOK
# =============================================================================

with tab_stok:

    m_sec = st.selectbox(
        "Model Seçin:",
        [m[1] for m in MODELLER],
    )

    ara = st.text_input(
        "🔍 Stok Kodu veya Renk Ara:",
        placeholder="Örn: Siyah, R01...",
    )

    alt = df_stok[
        df_stok["Model Grubu"] == m_sec
    ].copy()

    if ara:
        renk_eslesme = (
            alt["Renk Adı"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.contains(ara.lower(), na=False)
        )

        kod_eslesme = (
            alt["Stok Kodu"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.contains(ara.lower(), na=False)
        )

        alt = alt[renk_eslesme | kod_eslesme]

    for _, r in alt.iterrows():

        cols = st.columns([1.2, 1, 2.5, 1.1, 1.3, 1, 1])

        sat = int(r["Sheet_Satir"])
        kod = str(r["Stok Kodu"])
        slot = str(r["Renk Slotu"])
        renk = str(r["Renk Adı"])
        stok = int(r["Mevcut Stok"])
        kritik = int(r["Kritik Sınır"])

        cols[0].write(f"`{kod}`")
        cols[1].write(slot)

        cols[2].write(
            f"**{renk if renk and renk != 'nan' else 'İsimsiz Renk'}**"
        )

        cols[3].write(f"**{stok} Adet**")

        if stok == 0:
            durum_html = (
                '<span class="badge-err">TÜKENDİ</span>'
            )
        elif stok <= kritik:
            durum_html = (
                '<span class="badge-warn">KRİTİK</span>'
            )
        else:
            durum_html = (
                '<span class="badge-ok">YETERLİ</span>'
            )

        cols[4].markdown(
            durum_html,
            unsafe_allow_html=True,
        )

        if cols[5].button(
            "➕ +1",
            key=f"p_{kod}",
            use_container_width=True,
        ):
            try:
                stok_guncelle(
                    sat, kod, m_sec, renk, stok,
                    1, "Stok Girişi (+1)", aktif_kisi,
                )
                st.rerun()
            except Exception as e:
                st.error(f"Stok girişi başarısız: {e}")

        if cols[6].button(
            "➖ -1",
            key=f"m_{kod}",
            use_container_width=True,
        ):
            if stok > 0:
                try:
                    stok_guncelle(
                        sat, kod, m_sec, renk, stok,
                        -1, "Satış (-1)", aktif_kisi,
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Stok çıkışı başarısız: {e}")
            else:
                st.toast("Stok zaten 0!", icon="⚠️")

    st.markdown("---")

    with st.expander("✏️ Renk İsimlerini ve Sınırları Düzenle"):

        if not alt.empty:

            edit_df = alt[
                [
                    "Stok Kodu",
                    "Renk Slotu",
                    "Renk Adı",
                    "Mevcut Stok",
                    "Kritik Sınır",
                ]
            ].copy()

            ed = st.data_editor(
                edit_df,
                disabled=["Stok Kodu", "Renk Slotu"],
                use_container_width=True,
                hide_index=True,
                key=f"stok_editor_{m_sec}",
            )

            if st.button(
                "💾 Değişiklikleri Kaydet",
                type="primary",
                key="stok_kaydet",
            ):
                try:
                    ws = google_baglan().worksheet("Stok_Detay")

                    # Filtreleme yapılmış olsa bile doğru satıra yaz.
                    for pozisyon, (_, edited_row) in enumerate(ed.iterrows()):

                        sheet_row = int(
                            alt.iloc[pozisyon]["Sheet_Satir"]
                        )

                        stok_raw = pd.to_numeric(
                            edited_row["Mevcut Stok"],
                            errors="coerce",
                        )

                        kritik_raw = pd.to_numeric(
                            edited_row["Kritik Sınır"],
                            errors="coerce",
                        )

                        stok_val = max(
                            0,
                            int(stok_raw) if pd.notna(stok_raw) else 0,
                        )

                        kritik_val = max(
                            0,
                            int(kritik_raw) if pd.notna(kritik_raw) else 3,
                        )

                        renk_adi = (
                            str(edited_row["Renk Adı"])
                            if pd.notna(edited_row["Renk Adı"])
                            else ""
                        )

                        ws.update(
                            f"D{sheet_row}:F{sheet_row}",
                            [[renk_adi, stok_val, kritik_val]],
                        )

                    st.cache_data.clear()
                    st.success("Değişiklikler kaydedildi.")
                    st.rerun()

                except Exception as e:
                    st.error(f"Stok düzenleme kaydedilemedi: {e}")

        else:
            st.info("Bu model için eşleşen stok kaydı bulunamadı.")


# =============================================================================
# SEKME 2: FİNANS VE FİYATLANDIRMA
# =============================================================================

with tab_finans:

    st.subheader("📊 Aylık Değişken Giderler")

    v_kargo = (
        float(df_fin["Toptan Koli Kargosu"].iloc[0])
        if not df_fin.empty else 150.0
    )

    v_adet = (
        int(df_fin["Koli Urun Adedi"].iloc[0])
        if not df_fin.empty else 50
    )

    v_paket = (
        float(df_fin["Paketleme Gideri (TL)"].iloc[0])
        if not df_fin.empty else 5.0
    )

    fc1, fc2, fc3, fc4 = st.columns(4)

    y_kargo = fc1.number_input(
        "Toplam Koli Kargo Ücreti (₺):",
        value=max(0.0, v_kargo),
        min_value=0.0,
        step=10.0,
    )

    y_adet = fc2.number_input(
        "Kolideki Toplam Ürün Adedi:",
        value=max(1, v_adet),
        min_value=1,
        step=5,
    )

    y_paket = fc3.number_input(
        "Kılıf Başı Paketleme Gideri (₺):",
        value=max(0.0, v_paket),
        min_value=0.0,
        step=1.0,
    )

    hedef_kar = fc4.number_input(
        "Hedeflenen Net Kâr Oranı (%):",
        value=20.0,
        min_value=0.0,
        step=5.0,
    )

    koli_kargo_payi = y_kargo / y_adet

    st.markdown("---")
    st.subheader("💵 Model Bazlı Gider ve Komisyon Ayarları")

    finans_edit_cols = [
        "Model Grubu",
        "Gelis Fiyati",
        "Musteri Kargosu",
        "Vergi Orani (%)",
        "Sabit Vergi (TL)",
        "Shopier Komisyon (%)",
        "Shopier Sabit (TL)",
        "Senin Satis Fiyatin",
    ]

    fin_ed = st.data_editor(
        df_fin[finans_edit_cols].copy(),
        disabled=["Model Grubu"],
        use_container_width=True,
        hide_index=True,
        key="finans_editor",
    )

    if st.button(
        "💾 Finans ve Gider Ayarlarını Kaydet",
        type="primary",
    ):
        try:
            ws_f = google_baglan().worksheet("Finans_Ayar")

            yeni_veri = []

            for _, r in fin_ed.iterrows():
                yeni_veri.append([
                    r["Model Grubu"],
                    float(r["Gelis Fiyati"]),
                    float(r["Musteri Kargosu"]),
                    float(r["Vergi Orani (%)"]),
                    float(r["Sabit Vergi (TL)"]),
                    float(r["Shopier Komisyon (%)"]),
                    float(r["Shopier Sabit (TL)"]),
                    float(r["Senin Satis Fiyatin"]),
                    float(y_kargo),
                    int(y_adet),
                    float(y_paket),
                ])

            if yeni_veri:
                ws_f.update(
                    f"A2:K{len(yeni_veri) + 1}",
                    yeni_veri,
                )

            st.cache_data.clear()
            st.success("Finans ayarları güncellendi.")
            st.rerun()

        except Exception as e:
            st.error(f"Finans ayarları kaydedilemedi: {e}")

    st.markdown("---")

    st.subheader(
        f"📈 Başabaş ve %{hedef_kar:.0f} Kâr Öneri Tablosu"
    )

    sonuclar = []
    katsayi = 1.0 + hedef_kar / 100.0

    for _, r in fin_ed.iterrows():

        model = r["Model Grubu"]
        gelis = float(r["Gelis Fiyati"])
        musteri_kargo = float(r["Musteri Kargosu"])
        vergi_oran = float(r["Vergi Orani (%)"]) / 100.0
        vergi_sabit = float(r["Sabit Vergi (TL)"])
        shopier_oran = float(r["Shopier Komisyon (%)"]) / 100.0
        shopier_sabit = float(r["Shopier Sabit (TL)"])
        satis = float(r["Senin Satis Fiyatin"])

        degisken_maliyet = (
            gelis
            + koli_kargo_payi
            + musteri_kargo
            + y_paket
        )

        sabit_kesintiler = vergi_sabit + shopier_sabit
        kesinti_orani = vergi_oran + shopier_oran

        toplam_gider = (
            degisken_maliyet
            + satis * kesinti_orani
            + sabit_kesintiler
        )

        # Hedef kârı, satış fiyatı üzerinden değil maliyet üzerine
        # eklenen oran olarak ele alır.
        payda = 1.0 - (katsayi * kesinti_orani)

        fiyat_pay = (
            degisken_maliyet + sabit_kesintiler
        ) * katsayi

        onerilen_fiyat = (
            fiyat_pay / payda
            if payda > 0.05
            else toplam_gider * katsayi
        )

        net_kar = satis - toplam_gider

        if not df_log.empty:
            satilan = int((
                (df_log["Model Grubu"] == model)
                & (df_log["İşlem Türü"] == "Satış (-1)")
            ).sum())
        else:
            satilan = 0

        sonuclar.append({
            "Model Grubu": model,
            "Birim Gider (Her Şey Dahil)": f"{toplam_gider:.2f} ₺",
            f"💎 %{hedef_kar:.0f} Kârlı Önerilen Fiyat": f"{onerilen_fiyat:.2f} ₺",
            "Mevcut Satış Fiyatın": f"{satis:.2f} ₺",
            "Birim Net Kâr": f"{net_kar:.2f} ₺",
            "Satılan Adet": satilan,
            "Toplam Ciro (₺)": round(satilan * satis, 2),
            "Toplam Net Kâr (₺)": round(satilan * net_kar, 2),
        })

    df_sonuc = pd.DataFrame(sonuclar)

    st.dataframe(
        df_sonuc,
        use_container_width=True,
        hide_index=True,
    )

    sc1, sc2 = st.columns(2)

    if not df_sonuc.empty:
        sc1.metric(
            "Toplam Ciro",
            f"{df_sonuc['Toplam Ciro (₺)'].sum():,.2f} ₺",
        )

        sc2.metric(
            "Toplam Net Kâr",
            f"{df_sonuc['Toplam Net Kâr (₺)'].sum():,.2f} ₺",
        )
    else:
        sc1.metric("Toplam Ciro", "0,00 ₺")
        sc2.metric("Toplam Net Kâr", "0,00 ₺")


# =============================================================================
# SEKME 3: SOLVER OPTİMİZASYONU
# =============================================================================

with tab_solver:

    st.subheader("🎯 Bütçe & Sipariş Optimizasyonu (Solver)")

    b1, b2, b3 = st.columns(3)

    butce = b1.number_input(
        "Alım Bütçesi (₺):",
        value=25000.0,
        min_value=0.0,
        step=1000.0,
    )

    kapasite = b2.number_input(
        "Maks. Adet:",
        value=250,
        min_value=1,
        step=10,
    )

    min_adet = b3.number_input(
        "Model Başı Min:",
        value=10,
        min_value=0,
        step=5,
    )

    if st.button(
        "🚀 Optimum Dağılımı Hesapla",
        type="primary",
    ):

        liste = []

        for _, r in fin_ed.iterrows():

            model = r["Model Grubu"]
            gelis = float(r["Gelis Fiyati"])
            satis = float(r["Senin Satis Fiyatin"])

            vergi_oran = float(r["Vergi Orani (%)"]) / 100.0
            shopier_oran = float(r["Shopier Komisyon (%)"]) / 100.0

            gider = (
                gelis
                + koli_kargo_payi
                + float(r["Musteri Kargosu"])
                + float(y_paket)
                + float(r["Sabit Vergi (TL)"])
                + float(r["Shopier Sabit (TL)"])
                + satis * (vergi_oran + shopier_oran)
            )

            liste.append({
                "Model": model,
                "Birim Alış Maliyeti": gelis,
                "Birim Tahmini Net Kâr": satis - gider,
                "Adet": int(min_adet),
            })

        harcanan = sum(
            item["Adet"] * item["Birim Alış Maliyeti"]
            for item in liste
        )

        toplam_adet = sum(
            item["Adet"] for item in liste
        )

        if harcanan > butce or toplam_adet > kapasite:

            st.error(
                "Minimum adetler bütçeyi veya kapasiteyi aşıyor. "
                "Minimum adedi azaltın veya bütçeyi artırın."
            )

        else:

            sirali = sorted(
                liste,
                key=lambda item: (
                    item["Birim Tahmini Net Kâr"]
                    / max(1.0, item["Birim Alış Maliyeti"])
                ),
                reverse=True,
            )

            for item in sirali:

                maliyet = item["Birim Alış Maliyeti"]

                while (
                    maliyet > 0
                    and harcanan + maliyet <= butce
                    and toplam_adet + 1 <= kapasite
                ):
                    item["Adet"] += 1
                    harcanan += maliyet
                    toplam_adet += 1

            st.dataframe(
                pd.DataFrame(sirali),
                use_container_width=True,
                hide_index=True,
            )

            st.success(
                f"Toplam Harcama: {harcanan:,.2f} ₺ "
                f"| Toplam Adet: {toplam_adet}"
            )

            st.caption(
                "Bu yöntem hızlı bir yaklaşık dağılım yapar; "
                "matematiksel olarak en iyi sonucu garanti etmez."
            )


# =============================================================================
# SEKME 4: SATIŞ VE STOK GEÇMİŞİ
# =============================================================================

with tab_log:

    st.subheader("📋 Satış ve Stok Geçmişi")

    if not df_log.empty:
        st.dataframe(
            df_log.iloc[::-1],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Henüz işlem kaydı bulunmuyor.")


# =============================================================================
# SEKME 5: RAPORLAR
# =============================================================================

with tab_rapor:

    r1, r2 = st.columns([1, 1.5])

    with r1:

        with st.form("rapor_formu"):

            metin = st.text_area(
                "Gün Sonu Raporu:"
            )

            gonder = st.form_submit_button("Gönder")

            if gonder:

                if metin.strip():

                    try:
                        google_baglan().worksheet("Rapor").append_row([
                            datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            aktif_kisi,
                            metin.strip(),
                        ])

                        st.cache_data.clear()
                        st.success("Rapor gönderildi.")
                        st.rerun()

                    except Exception as e:
                        st.error(
                            f"Rapor gönderilemedi: {e}"
                        )

                else:
                    st.warning("Lütfen rapor metnini yazın.")

    with r2:

        st.subheader("📝 Gönderilen Raporlar")

        if not df_rap.empty:

            for _, r in df_rap.iloc[::-1].iterrows():

                st.info(
                    f"**{r['Kişi']}** ({r['Tarih']})\n\n"
                    f"{r['Rapor Detayı']}"
                )

        else:
            st.info("Henüz rapor bulunmuyor.")
