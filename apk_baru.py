# ======================================================
# IMPORT LIBRARY
# ======================================================
import pandas as pd
import numpy as np
import streamlit as st
import warnings
import mysql.connector

from datetime import datetime

from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error
)

warnings.filterwarnings("ignore")

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(
    page_title="Prediksi Stok ARIMA",
    page_icon="📦",
    layout="wide"
)
# ======================================================
# DATABASE MYSQL LARAGON
# ======================================================

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="prediksi_stok"
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS stok (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nama_bahan VARCHAR(100) UNIQUE,
    jumlah DOUBLE,
    tanggal_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS mutasi_stok (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tanggal TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    nama_bahan VARCHAR(100),
    masuk DOUBLE,
    keluar DOUBLE,
    stok_akhir DOUBLE
)
""")

conn.commit()

# ======================================================
# CUSTOM CSS
# ======================================================
st.markdown("""
<style>

.stApp {
    background-color: #f8fafc;
}

[data-testid="stSidebar"] {
    background: #dbeafe;
}

h1 {
    color: #1e3a8a;
    font-weight: bold;
}

h2, h3 {
    color: #334155;
}

p, label, div {
    color: #1e293b;
}

[data-testid="metric-container"] {
    background-color: white;
    border-radius: 15px;
    padding: 20px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 10px rgba(0,0,0,0.08);
}

.stButton>button {
    background-color: #2563eb;
    color: white;
    border-radius: 10px;
    border: none;
    height: 45px;
    width: 100%;
    font-size: 16px;
    font-weight: bold;
}

.stDownloadButton>button {
    background-color: #16a34a;
    color: white;
    border-radius: 10px;
    border: none;
    height: 45px;
    width: 100%;
    font-size: 16px;
    font-weight: bold;
}

</style>
""", unsafe_allow_html=True)

# ======================================================
# DATA AWAL
# ======================================================
stok_awal = {
    "Tepung (kg)": 16000,
    "Margarin A (gram)": 2000,
    "Margarin B (gram)": 2500,
    "Telur (butir)": 50,
    "Air (ml)": 16000,
    "Gula (gram)": 8000,
    "Fermipan (sdm)": 30
}

for bahan, jumlah in stok_awal.items():

    cursor.execute("""
INSERT IGNORE INTO stok
(
    nama_bahan,
    jumlah
)
VALUES (%s, %s)
""",
(
    bahan,
    jumlah
))

conn.commit()

bahan_baku = {
    "Tepung (kg)": 1000,
    "Margarin A (gram)": 100,
    "Margarin B (gram)": 100,
    "Telur (butir)": 8,
    "Air (ml)": 800,
    "Gula (gram)": 400,
    "Fermipan (sdm)": 1
}

# ======================================================
# FUNCTION DATABASE
# ======================================================

def load_stok():

    cursor.execute("""
    SELECT
        nama_bahan,
        jumlah
    FROM stok
    """)

    hasil = cursor.fetchall()

    return {
        row[0]: float(row[1])
        for row in hasil
    }

def update_stok(
    bahan,
    stok_baru
):

    cursor.execute("""
UPDATE stok
SET jumlah = %s
WHERE nama_bahan = %s
""",
(
    stok_baru,
    bahan
))

    conn.commit()

def simpan_mutasi(
    bahan,
    masuk,
    keluar,
    stok_akhir
):

    cursor.execute("""
    INSERT INTO mutasi_stok
    (
        nama_bahan,
        masuk,
        keluar,
        stok_akhir
    )
    VALUES
    (
        %s, %s, %s, %s
    )
    """,
    (
        bahan,
        masuk,
        keluar,
        stok_akhir
    ))

    conn.commit()

# ======================================================
# SESSION STATE
# ======================================================
if "stok_kg" not in st.session_state:

    st.session_state["stok_kg"] = load_stok()
if "df_bahan" not in st.session_state:
    st.session_state["df_bahan"] = None

if "restock" not in st.session_state:
    st.session_state["restock"] = []

if "forecast" not in st.session_state:
    st.session_state["forecast"] = None

# ======================================================
# SIDEBAR
# ======================================================
st.sidebar.title("📊 MENU APLIKASI")

menu = st.sidebar.radio(
    "Pilih Menu",
    [
        "📈 Prediksi Stok",
        "🚨 Notifikasi Restock",
        "📥📤 Manajemen Stok"
    ]
)

# ======================================================
# PREDIKSI STOK
# ======================================================
if menu == "📈 Prediksi Stok":

    st.title("🔮 Prediksi Stok Barang")

    st.markdown("### 📘 Penjelasan Sistem Prediksi")
    st.info("""
📂 Membaca Dataset  
🧹 Membersihkan Data  
🔄 Training Model ARIMA Otomatis  
📊 Evaluasi Akurasi Model  
📦 Forecast Stok Otomatis  
🧾 Menghitung Kebutuhan Bahan  
🚨 Menampilkan Notifikasi Restock  
""")

    # ======================================================
    # UPLOAD FILE
    # ======================================================
    file = st.file_uploader(
        "📂 Upload Dataset Excel",
        type=["xlsx"]
    )

    if file is not None:

        # ======================================================
        # MEMBACA DATASET
        # ======================================================
        df = pd.read_excel(file)

        df.columns = (
            df.columns.str.lower().str.strip()
        )

        # ======================================================
        # VALIDASI DATA
        # ======================================================
        if "nyata" not in df.columns:

            st.error(
                "❌ Kolom 'nyata' tidak ditemukan"
            )

            st.stop()

        # ======================================================
        # PREPROCESSING DATA
        # ======================================================
        series = df["nyata"].astype(str)

        series = series.str.replace(
            ",",
            "",
            regex=False
        )

        series = series.str.replace(
            ".",
            "",
            regex=False
        )

        series = pd.to_numeric(
            series,
            errors="coerce"
        ).dropna()

        series = series.astype(float)

        # ======================================================
        # INDEX TANGGAL
        # ======================================================
        series.index = pd.date_range(
            start="2025-11-27",
            periods=len(series),
            freq="D"
        )

        # ======================================================
        # DATA SIAP DIPROSES
        # ======================================================
        st.write("## 📄 Data Siap Diproses")

        st.dataframe(
            series.tail(),
            use_container_width=True
        )

        # ======================================================
        # TRAIN TEST SPLIT
        # ======================================================
        train_size = int(
            len(series) * 0.8
        )

        train = series[:train_size]
        test = series[train_size:]

        st.info(
            f"""
            Total Data : {len(series)}
            | Training : {len(train)}
            | Testing : {len(test)}
            """
        )

        # ======================================================
        # TRAINING OTOMATIS
        # ======================================================
        st.write("## 🔄 Training Model Otomatis")

        progress = st.progress(0)

        with st.spinner(
            "Sedang melakukan training otomatis..."
        ):

            progress.progress(20)

            model_eval = ARIMA(
                train,
                order=(1,1,1)
            )

            progress.progress(50)

            model_eval_fit = (
                model_eval.fit()
            )

            progress.progress(80)

            pred_test = (
                model_eval_fit.forecast(
                    steps=len(test)
                )
            )

            progress.progress(100)

        st.success(
            """
            ✅ Training otomatis berhasil
            dilakukan
            """
        )

        # ======================================================
        # EVALUASI MODEL
        # ======================================================
        mae = mean_absolute_error(
            test,
            pred_test
        )

        rmse = np.sqrt(
            mean_squared_error(
                test,
                pred_test
            )
        )

        mape = np.mean(
            np.abs(
                (test - pred_test)
                / test
            )
        ) * 100

        akurasi = 100 - mape

        # ======================================================
        # TAMPILKAN AKURASI
        # ======================================================
        st.write("## 📊 Evaluasi Akurasi")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "MAE",
            f"{mae:.2f}"
        )

        col2.metric(
            "RMSE",
            f"{rmse:.2f}"
        )

        col3.metric(
            "Akurasi",
            f"{akurasi:.2f}%"
        )

        # ======================================================
        # PENJELASAN AKURASI
        # ======================================================
        if akurasi >= 90:

            st.success(
                """
                ✅ Model memiliki
                akurasi sangat baik
                """
            )

        elif akurasi >= 75:

            st.info(
                """
                ℹ️ Model memiliki
                akurasi cukup baik
                """
            )

        else:

            st.warning(
                """
                ⚠️ Akurasi model
                masih rendah
                """
            )

        # ======================================================
        # FORECAST OTOMATIS
        # ======================================================
        # Input jumlah hari prediksi
        jumlah_hari_input = st.text_input(
            "Masukkan Jumlah Hari Prediksi",
            value="3"
        )
        
        try:
            jumlah_hari = int(jumlah_hari_input)
        
            if jumlah_hari < 1:
                jumlah_hari = 3
        
        except:
            jumlah_hari = 3

        st.write("## 📦 Prediksi Otomatis")

        with st.spinner("Membuat prediksi stok..."):
        
            model = ARIMA(
                series,
                order=(1,1,1)
            )

            model_fit = model.fit()

            forecast = model_fit.forecast(
                steps=jumlah_hari
            )

            forecast = np.round(
                forecast
            ).astype(int)

            forecast[forecast < 0] = 0

        # ======================================================
        # SIMPAN SESSION
        # ======================================================
        st.session_state["forecast"] = forecast

        # ======================================================
        # HASIL PREDIKSI
        # ======================================================
        for i, val in enumerate(
            forecast,
            start=1
        ):

            st.success(
                f"📅 Hari ke-{i}: {val} kg"
            )

        # ======================================================
        # TOTAL PREDIKSI
        # ======================================================
        total_prediksi = int(
            forecast.sum()
        )

        st.info(
            f"📦 Total Prediksi {jumlah_hari} Hari: {total_prediksi} kg"
        )

        # ======================================================
        # GRAFIK
        # ======================================================
        
        forecast_df = pd.DataFrame({
            "Hari": [
                f"Hari {i:02d}"
                for i in range(1, jumlah_hari + 1)
            ],
            "Prediksi": forecast
        })
        
        st.line_chart(
            forecast_df.set_index("Hari")
        )

        # ======================================================
        # PENJELASAN HASIL
        # ======================================================
        st.write("## 📝 Penjelasan Hasil")

        st.write(
            f"""
            Berdasarkan hasil training
            otomatis menggunakan metode
            ARIMA, sistem memprediksi
            total kebutuhan stok selama
            {jumlah_hari} hari ke depan sebesar
            {total_prediksi} kg.

            Nilai akurasi model sebesar
            {akurasi:.2f}% menunjukkan
            performa model dalam
            melakukan prediksi stok.
            """
        )

        # ======================================================
        # BAHAN TERPAKAI
        # ======================================================
        st.write("## 🧾 Bahan Terpakai")

        data_bahan = []

        for bahan, kebutuhan in (
            bahan_baku.items()
        ):

            total_pakai = (
                total_prediksi
                * kebutuhan
            )

            data_bahan.append({
                "Bahan": bahan,
                "Kebutuhan per Adonan":
                    kebutuhan,
                "Total Terpakai":
                    total_pakai
            })

        df_bahan = pd.DataFrame(
            data_bahan
        )

        st.session_state[
            "df_bahan"
        ] = df_bahan

        st.dataframe(
            df_bahan,
            use_container_width=True
        )

        # ======================================================
        # RESTOCK OTOMATIS
        # ======================================================
        restock = []

        for _, row in (
            df_bahan.iterrows()
        ):

            bahan = row["Bahan"]

            kebutuhan = row[
                "Total Terpakai"
            ]

            stok = stok_awal[bahan]

            if kebutuhan > stok:

                restock.append({
                    "Bahan": bahan,
                    "Stok": stok,
                    "Kebutuhan":
                        kebutuhan,
                    "Kekurangan":
                        kebutuhan - stok
                })
                
        st.session_state[
            "restock"
        ] = restock
        

# ======================================================
# BAHAN TERPAKAI
# ======================================================
elif menu == "🧾 Bahan Terpakai":

    st.title("🧾 Rincian Bahan Terpakai")

    if st.session_state["df_bahan"] is not None:

        st.dataframe(
            st.session_state["df_bahan"],
            use_container_width=True
        )

    else:

        st.warning(
            "Silakan lakukan prediksi terlebih dahulu"
        )

# ======================================================
# RESTOCK
# ======================================================
elif menu == "🚨 Notifikasi Restock":

    st.title("🚨 Notifikasi Restock")

    if len(st.session_state["restock"]) > 0:

        st.error(
            """
            ⚠️ Beberapa bahan perlu dilakukan
            restock karena stok tidak mencukupi
            kebutuhan produksi.
            """
        )

        # ======================================================
        # DATAFRAME RESTOCK
        # ======================================================
        restock_df = pd.DataFrame(
            st.session_state["restock"]
        )

        st.dataframe(
            restock_df,
            use_container_width=True
        )


# ======================================================
# MANAJEMEN STOK
# ======================================================
elif menu == "📥📤 Manajemen Stok":

    st.title("📥📤 Manajemen Stok")

    with st.form("form_stok"):

        bahan = st.selectbox(
            "Pilih Bahan",
            list(
                st.session_state[
                    "stok_kg"
                ].keys()
            )
        )

        masuk = st.number_input(
            "Barang Masuk",
            min_value=0.0,
            step=0.1
        )

        keluar = st.number_input(
            "Barang Keluar",
            min_value=0.0,
            step=0.1
        )

        submit = st.form_submit_button(
            "Update Stok"
        )

    if submit:

        stok_baru = (
            st.session_state["stok_kg"][bahan]
            + masuk
            - keluar
        )

        st.session_state["stok_kg"][bahan] = stok_baru

        update_stok(
            bahan,
            stok_baru
        )

        simpan_mutasi(
            bahan,
            masuk,
            keluar,
            stok_baru
        )
        st.success(
            f"Stok {bahan} berhasil diperbarui"
        )

    st.write("## 📦 Stok Saat Ini")

    stok_df = pd.DataFrame.from_dict(
        st.session_state["stok_kg"],
        orient="index",
        columns=["Jumlah"]
    )

    st.dataframe(
        stok_df,
        use_container_width=True
    )
