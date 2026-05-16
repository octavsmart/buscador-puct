import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Buscador PUCT Pro", layout="centered")


@st.cache_data
def load_data():
    try:
        if os.path.exists("PUCT.csv"):
            df = pd.read_csv(
                "PUCT.csv", header=None, dtype=str, sep=None, engine="python"
            )
        else:
            df = pd.read_excel("PUCT.xlsx", header=None, dtype=str, engine="openpyxl")

        df = df.fillna("")
        mapeo = {
            0: "C",
            1: "G",
            2: "SG",
            3: "CP",
            4: "CA",
            5: "NOMBRE DE LA CUENTA",
            6: "COMERCIAL",
            7: "SERVICIOS",
            8: "TRANSPORTE",
            9: "INDUSTRIAL",
            10: "PETROLERA",
            11: "CONSTRUCCIÓN",
            12: "AGROPECUARIA",
            13: "MINERA",
        }
        df = df.rename(columns=mapeo)
        df["FAMILIA"] = (
            df["C"].astype(str) + "-" + df["G"].astype(str) + "-" + df["SG"].astype(str)
        )
        return df
    except Exception as e:
        st.error(f"Error: {e}")
        return None


df = load_data()

if df is not None:
    # --- LOGICA DE SINCRONIZACIÓN DE ESTADOS ---
    if "query_input" not in st.session_state:
        st.session_state.query_input = ""
    if "grupo_sel" not in st.session_state:
        st.session_state.grupo_sel = "TODOS"

    # --- BARRA LATERAL ---
    st.sidebar.header("🛠️ Configuración")
    actividades = [
        "COMERCIAL",
        "SERVICIOS",
        "TRANSPORTE",
        "INDUSTRIAL",
        "PETROLERA",
        "CONSTRUCCIÓN",
        "AGROPECUARIA",
        "MINERA",
    ]
    act_sel = st.sidebar.selectbox("Filtro de Actividad:", ["TODAS"] + actividades)

    # --- PREPARACIÓN DE GRUPOS ---
    mapa_clases = {
        "1": "ACTIVO",
        "2": "PASIVO",
        "3": "PATRIMONIO",
        "4": "INGRESOS",
        "5": "GASTOS",
        "6": "COSTOS",
    }
    macros_df = df[
        (df["C"].astype(str).str.strip() != "")
        & (df["G"].astype(str).str.strip() == "")
    ]
    for _, row in macros_df.iterrows():
        mapa_clases[str(row["C"]).strip()] = str(row["NOMBRE DE LA CUENTA"]).strip()

    condicion_titulo = (df["SG"].astype(str).str.strip() != "") & (
        df["CP"].astype(str).str.strip() == ""
    )
    if act_sel != "TODAS":
        detalles_con_x = df[
            (df["CP"].astype(str).str.strip() != "")
            & (df[act_sel].astype(str).str.upper().str.strip() == "X")
        ]
        fam_validas = detalles_con_x["FAMILIA"].unique()
        titulos = df[condicion_titulo & df["FAMILIA"].isin(fam_validas)].copy()
    else:
        titulos = df[condicion_titulo].copy()

    def crear_etiqueta(row):
        num = str(row["C"]).strip()
        return f"[{num} - {mapa_clases.get(num, 'OTRO')}] {row['NOMBRE DE LA CUENTA']}"

    titulos["ETIQUETA_MENU"] = titulos.apply(crear_etiqueta, axis=1)
    lista_grupos = ["TODOS"] + titulos["ETIQUETA_MENU"].tolist()

    # --- NORMALIZACIÓN SIN TILDES (siempre disponible) ---
    import unicodedata

    def normalizar(texto):
        """Quita tildes y pasa a minúsculas para comparar sin acento."""
        return "".join(
            c for c in unicodedata.normalize("NFD", str(texto))
            if unicodedata.category(c) != "Mn"
        ).lower()

    # Pre-calcular nombres normalizados una sola vez
    nombres_norm = df["NOMBRE DE LA CUENTA"].apply(normalizar)

    # --- FUNCIONES DE LIMPIEZA ---
    def on_query_change():
        st.session_state.grupo_sel = "TODOS"

    def on_group_change():
        st.session_state.query_input = ""

    # --- INTERFAZ ---
    st.title("🎯 Buscador PUCT")

    # Menú de Grupo — siempre activo; al elegir uno limpia el texto automáticamente
    grupo_sel = st.selectbox(
        "📂 1. Explorar por Grupo:",
        lista_grupos,
        key="grupo_sel",
        on_change=on_group_change,
    )

    # Buscador de Texto
    query = st.text_input(
        "🔍 2. O busca por palabra clave:",
        key="query_input",
        on_change=on_query_change,
    ).strip()

    df_mostrar = pd.DataFrame()

    # Primero verificamos el buscador
    indices_match = set()
    if query:
        query_norm = normalizar(query)

        mask_detalle = (
            nombres_norm.str.contains(query_norm, na=False)
            & (df["CP"].astype(str).str.strip() != "")
        )
        filas_detalle = df[mask_detalle]

        # Respetar filtro de actividad si está seleccionado
        if act_sel != "TODAS":
            filas_detalle = filas_detalle[
                filas_detalle[act_sel].astype(str).str.upper().str.strip() == "X"
            ]

        if filas_detalle.empty:
            st.info("No se encontraron cuentas que contengan esa palabra.")
        else:
            indices_match = set(filas_detalle.index)
            fam_con_coincidencia = filas_detalle["FAMILIA"].unique()

            # Detectar en qué clases (C) aparecen los resultados
            clases_encontradas = filas_detalle["C"].astype(str).str.strip().unique().tolist()

            # Resetear filtros si cambió la búsqueda
            if st.session_state.get("ultima_query") != query:
                st.session_state["clase_filtro"] = None
                st.session_state["subgrupo_filtro"] = None
                st.session_state["ultima_query"] = query

            if len(clases_encontradas) == 1:
                # Una sola clase → ir directo al paso 2 (subgrupos)
                st.session_state["clase_filtro"] = clases_encontradas[0]

            clase_activa = st.session_state.get("clase_filtro")

            # PASO 1: elegir clase
            if not clase_activa:
                st.markdown(f"**Paso 1 — ¿En qué sección está?**")
                cols = st.columns(len(clases_encontradas))
                for i, c_val in enumerate(clases_encontradas):
                    etiq = mapa_clases.get(c_val, f"CLASE {c_val}")
                    if cols[i].button(etiq, key=f"btn_clase_{c_val}"):
                        st.session_state["clase_filtro"] = c_val
                        st.session_state["subgrupo_filtro"] = None
                        st.rerun()

            else:
                # Subgrupos disponibles en esa clase
                fams_clase = filas_detalle[
                    filas_detalle["C"].astype(str).str.strip() == clase_activa
                ]["FAMILIA"].unique()

                etiq_clase = mapa_clases.get(clase_activa, clase_activa)

                # Construir etiquetas de subgrupo
                def etiqueta_corta_sg(nombre_grupo):
                    STOPWORDS = {"DE", "Y", "A", "EN", "DEL", "LA", "LOS", "LAS", "EL", "POR", "E"}
                    palabras = nombre_grupo.upper().split()
                    claves = [p for p in palabras if p not in STOPWORDS]
                    return " ".join(claves[:2]).lower()

                subgrupos = []
                for fam in fams_clase:
                    tit = df[
                        (df["FAMILIA"] == fam) & (df["CP"].astype(str).str.strip() == "")
                    ]
                    if not tit.empty:
                        nombre_sg = str(tit.iloc[0]["NOMBRE DE LA CUENTA"]).strip()
                        subgrupos.append((fam, nombre_sg, etiqueta_corta_sg(nombre_sg)))

                subgrupo_activo = st.session_state.get("subgrupo_filtro")

                if len(subgrupos) == 1:
                    # Un solo subgrupo → mostrar directo
                    st.session_state["subgrupo_filtro"] = subgrupos[0][0]
                    subgrupo_activo = subgrupos[0][0]

                if not subgrupo_activo:
                    # PASO 2: elegir subgrupo — solo mostrar los que tienen coincidencia real
                    subgrupos_con_match = [
                        (fam, nombre_sg, etiq_sg) for fam, nombre_sg, etiq_sg in subgrupos
                        if fam in fam_con_coincidencia
                    ]
                    st.markdown(f"**Paso 1 →** {etiq_clase} &nbsp;&nbsp; **| Paso 2 — ¿Qué tipo?**")
                    cols2 = st.columns(min(len(subgrupos_con_match), 4))
                    for i, (fam, nombre_sg, etiq_sg) in enumerate(subgrupos_con_match):
                        col_idx = i % 4
                        if cols2[col_idx].button(etiq_sg, key=f"btn_sg_{fam}"):
                            st.session_state["subgrupo_filtro"] = fam
                            st.rerun()
                    # Botón para volver al paso 1
                    if len(clases_encontradas) > 1:
                        if st.button("← volver a secciones"):
                            st.session_state["clase_filtro"] = None
                            st.session_state["subgrupo_filtro"] = None
                            st.rerun()
                else:
                    # PASO 3: mostrar resultado
                    nombre_sg_activo = next((n for f, n, e in subgrupos if f == subgrupo_activo), "")
                    st.markdown(f"**{etiq_clase}** › **{nombre_sg_activo}**")
                    if st.button("← volver a subgrupos"):
                        st.session_state["subgrupo_filtro"] = None
                        st.rerun()
                    df_mostrar = df[df["FAMILIA"] == subgrupo_activo]

    elif grupo_sel != "TODOS":
        st.session_state["clase_filtro"] = None
        fam_sel = titulos[titulos["ETIQUETA_MENU"] == grupo_sel]["FAMILIA"].values[0]
        df_mostrar = df[df["FAMILIA"] == fam_sel]

    # --- MOSTRAR ---
    if not df_mostrar.empty:
        if act_sel != "TODAS":
            es_tit = df_mostrar["CP"].astype(str).str.strip() == ""
            con_x = df_mostrar[act_sel].astype(str).str.upper().str.strip() == "X"
            fam_v = df_mostrar[(~es_tit) & con_x]["FAMILIA"].unique()
            df_mostrar = df_mostrar[
                (df_mostrar["FAMILIA"].isin(fam_v)) & (es_tit | con_x)
            ]

        # Construir mapa familia -> etiqueta corta del subgrupo
        def etiqueta_corta(nombre_grupo):
            """Extrae palabras clave del nombre del grupo para etiqueta corta."""
            STOPWORDS = {"DE", "Y", "A", "EN", "DEL", "LA", "LOS", "LAS", "EL", "POR", "E"}
            palabras = nombre_grupo.upper().split()
            claves = [p for p in palabras if p not in STOPWORDS]
            # Tomar hasta 2 palabras clave
            resumen = " ".join(claves[:2])
            return resumen.lower()

        mapa_etiqueta = {}
        for _, trow in df[df["CP"].astype(str).str.strip() == ""].iterrows():
            fam = str(trow["FAMILIA"])
            mapa_etiqueta[fam] = etiqueta_corta(str(trow["NOMBRE DE LA CUENTA"]))

        st.divider()
        for idx, row in df_mostrar.iterrows():
            nombre = str(row["NOMBRE DE LA CUENTA"]).replace("\n", " ").strip()
            es_tit = str(row["CP"]).strip() == ""
            if es_tit:
                st.markdown(f"### 📂 {nombre}")
            else:
                es_match = idx in indices_match
                icono = "⭐" if es_match else "🔹"
                etiq = mapa_etiqueta.get(str(row["FAMILIA"]), "")
                sufijo = f"  ·  *{etiq}*" if etiq else ""
                st.markdown(f"**{icono} {nombre}**{sufijo}")
                c, g, sg = [str(row[k]).split(".")[0].strip() for k in ["C", "G", "SG"]]
                cp = str(row["CP"]).split(".")[0].strip().zfill(3)
                ca = (
                    str(row["CA"]).split(".")[0].strip().zfill(3)
                    if row["CA"]
                    else "001"
                )
                st.code(f"{c}\t{g}\t{sg}\t{cp}\t{ca}\t{nombre}", language="text")
