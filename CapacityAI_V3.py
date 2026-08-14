import io
import re
import unicodedata
import pandas as pd
import streamlit as st

# ============================================================
# CAPACITY AI - RÉPLICA ANEXO N° 6
# Catálogo obligatorio + matriz de capacitación por puesto.
# ============================================================

st.set_page_config(
    page_title="Capacity AI | Anexo N° 6",
    page_icon="🎓",
    layout="wide"
)

# -----------------------------
# Estilos
# -----------------------------
st.markdown("""
<style>
.main-title {
    font-size: 2.1rem;
    font-weight: 800;
    margin-bottom: 0.1rem;
}
.subtitle {
    color: #667085;
    margin-bottom: 1.5rem;
}
.course-card {
    border: 1px solid #d9dee8;
    border-radius: 12px;
    padding: 14px;
    margin-bottom: 10px;
    background: white;
}
.small-muted {
    color: #667085;
    font-size: 0.85rem;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# CATÁLOGO OFICIAL DE LA IMAGEN
# ============================================================

CATALOGO = [
    {
        "Item": 1,
        "Curso": "Gestión de la Seguridad y Salud Ocupacional basada en el Reglamento de Seguridad y Salud Ocupacional y Política de Seguridad y Salud Ocupacional",
        "Horas": 3,
    },
    {
        "Item": 2,
        "Curso": "Notificación, Investigación y reporte de Incidentes, Incidentes peligrosos y accidentes de trabajo",
        "Horas": 3,
    },
    {
        "Item": 3,
        "Curso": "Liderazgo y Motivación. Seguridad basada en el Comportamiento",
        "Horas": 2,
    },
    {
        "Item": 4,
        "Curso": "Respuesta a Emergencias por áreas específicas",
        "Horas": 4,
    },
    {
        "Item": 5,
        "Curso": "IPERC",
        "Horas": 4,
    },
    {
        "Item": 6,
        "Curso": "Trabajos en altura",
        "Horas": 4,
    },
    {
        "Item": 7,
        "Curso": "Mapa de Riesgos psicosociales",
        "Horas": 4,
    },
    {
        "Item": 8,
        "Curso": "Significado y uso de código de señales y colores",
        "Horas": 2,
    },
    {
        "Item": 9,
        "Curso": "Auditoría, Fiscalización e Inspección de Seguridad",
        "Horas": 3,
    },
    {
        "Item": 10,
        "Curso": "Primeros Auxilios",
        "Horas": 2,
    },
    {
        "Item": 11,
        "Curso": "Prevención y Protección Contra Incendios",
        "Horas": 2,
    },
    {
        "Item": 12,
        "Curso": "Estándares y procedimientos escrito de trabajo seguro por actividades",
        "Horas": 2,
    },
    {
        "Item": 13,
        "Curso": "Higiene Ocupacional (Agentes Físicos, Químicos, Biológicos), Disposición de residuos sólidos, Control de Sustancias peligrosas",
        "Horas": 2,
    },
    {
        "Item": 14,
        "Curso": "Manejo defensivo y/o transporte de personal",
        "Horas": 4,
    },
    {
        "Item": 15,
        "Curso": "Comité de Seguridad y Salud Ocupacional. Reglamento Interno de Seguridad y Salud Ocupacional. Programa Anual de Seguridad y Salud Ocupacional. (03 Cursos fusionados)",
        "Horas": 3,
    },
    {
        "Item": 16,
        "Curso": "Seguridad en la oficina y ergonomía",
        "Horas": 2,
    },
    {
        "Item": 17,
        "Curso": "Riesgos Eléctricos",
        "Horas": 3,
    },
    {
        "Item": 18,
        "Curso": "Prevención de accidente por desprendimiento de rocas",
        "Horas": 3,
    },
    {
        "Item": 19,
        "Curso": "Prevención de accidente por gaseamiento",
        "Horas": 3,
    },
    {
        "Item": 20,
        "Curso": "El Uso de equipo de protección personal (EPP)",
        "Horas": 2,
    },
]

catalogo = pd.DataFrame(CATALOGO)


# ============================================================
# UTILIDADES
# ============================================================

def normalizar(texto):
    if texto is None or pd.isna(texto):
        return ""
    texto = str(texto)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    texto = texto.upper()
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def clave_curso(texto):
    x = normalizar(texto)

    equivalencias = {
        "IPERC": "IPERC",
        "PRIMEROS AUXILIOS": "PRIMEROS AUXILIOS",
        "TRABAJOS EN ALTURA": "TRABAJOS EN ALTURA",
        "RIESGOS ELECTRICOS": "RIESGOS ELECTRICOS",
        "MANEJO DEFENSIVO": "MANEJO DEFENSIVO Y/O TRANSPORTE DE PERSONAL",
        "MANEJO DEFENSIVO Y TRANSPORTE DE PERSONAL":
            "MANEJO DEFENSIVO Y/O TRANSPORTE DE PERSONAL",
        "USO DE EPP":
            "EL USO DE EQUIPO DE PROTECCION PERSONAL (EPP)",
        "USO CORRECTO DEL EQUIPO DE PROTECCION PERSONAL":
            "EL USO DE EQUIPO DE PROTECCION PERSONAL (EPP)",
    }

    return equivalencias.get(x, x)


def buscar_catalogo(nombre):
    key = clave_curso(nombre)

    for _, fila in catalogo.iterrows():
        if key == clave_curso(fila["Curso"]):
            return fila

    # Coincidencia por palabras importantes.
    palabras = [
        p for p in key.split()
        if len(p) >= 5
    ]

    mejor = None
    mejor_score = 0

    for _, fila in catalogo.iterrows():
        ref = clave_curso(fila["Curso"])
        score = sum(p in ref for p in palabras) / max(len(palabras), 1)

        if score > mejor_score:
            mejor_score = score
            mejor = fila

    if mejor_score >= 0.65:
        return mejor

    return None


# ============================================================
# MATRIZ DE SEGUIMIENTO
# ============================================================

def crear_matriz_puestos(puestos):
    filas = []

    puestos = sorted(
        set(
            str(p).strip()
            for p in puestos
            if str(p).strip()
        )
    )

    for puesto in puestos:
        for _, curso in catalogo.iterrows():
            filas.append({
                "Item": int(curso["Item"]),
                "Puesto de trabajo": puesto,
                "Modalidad de curso": "Presencial",
                "Duración": int(curso["Horas"]),
                "Certificado / lista de asistencia": False,
                "Curso": curso["Curso"],
                "Asistencia": False,
                "Nota": None,
                "Comentarios": "",
                "Estado": "PENDIENTE",
            })

    return pd.DataFrame(filas)


def actualizar_estado(df):
    if df.empty:
        return df

    df = df.copy()

    def estado(row):
        if not row["Asistencia"]:
            return "PENDIENTE"

        if pd.isna(row["Nota"]) or str(row["Nota"]).strip() == "":
            return "PENDIENTE DE NOTA"

        if not row["Certificado / lista de asistencia"]:
            return "PENDIENTE DE CERTIFICADO/LISTA"

        return "COMPLETADO"

    df["Estado"] = df.apply(estado, axis=1)
    return df


# ============================================================
# LECTOR SIMPLE DE EXCEL
# ============================================================

def encontrar_columna(columnas, opciones):
    for col in columnas:
        n = normalizar(col)
        for opcion in opciones:
            if n == opcion or opcion in n:
                return col
    return None


def extraer_puestos_excel(archivo):
    datos = pd.ExcelFile(io.BytesIO(archivo))
    puestos = []

    for hoja in datos.sheet_names:
        try:
            df = pd.read_excel(
                io.BytesIO(archivo),
                sheet_name=hoja
            )
        except Exception:
            continue

        if df.empty:
            continue

        puesto_col = encontrar_columna(
            df.columns,
            [
                "PUESTO DE TRABAJO",
                "CARGO",
                "POSICION",
                "POSICIÓN"
            ]
        )

        if puesto_col:
            for valor in df[puesto_col].dropna():
                texto = str(valor).strip()
                if texto:
                    puestos.append(texto)

    return sorted(set(puestos))


# ============================================================
# ESTADO
# ============================================================

if "matriz" not in st.session_state:
    st.session_state.matriz = pd.DataFrame()

if "puestos" not in st.session_state:
    st.session_state.puestos = []


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🎓 Capacity AI")
st.sidebar.caption("Capacitación en Seguridad y Salud Ocupacional")

pagina = st.sidebar.radio(
    "Menú",
    [
        "Inicio",
        "Cursos obligatorios",
        "Matriz de capacitación",
        "Resumen",
        "Exportar"
    ]
)


# ============================================================
# INICIO
# ============================================================

if pagina == "Inicio":

    st.markdown(
        '<div class="main-title">🎓 Capacity AI</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">Matriz de capacitación basada en el Anexo N° 6</div>',
        unsafe_allow_html=True
    )

    st.info(
        "Los cursos y las horas obligatorias están cargados "
        "directamente según la tabla proporcionada."
    )

    st.subheader("¿Qué hace el programa?")

    c1, c2, c3 = st.columns(3)

    c1.metric("Cursos obligatorios", 20)
    c2.metric(
        "Horas diferentes",
        int(catalogo["Horas"].nunique())
    )
    c3.metric(
        "Horas acumuladas catálogo",
        int(catalogo["Horas"].sum())
    )

    st.markdown("""
    ### Flujo

    **Puesto de trabajo / Cargo**

    ↓

    **Cursos que corresponden según IPERC**

    ↓

    **Curso obligatorio del Anexo N° 6**

    ↓

    **Duración mínima obligatoria**

    ↓

    **Asistencia + Nota + Certificado/Lista + Comentarios**
    """)

    st.success(
        "La matriz final reúne todos los puntos en una sola pantalla."
    )


# ============================================================
# CURSOS OBLIGATORIOS
# ============================================================

elif pagina == "Cursos obligatorios":

    st.title("📚 Cursos obligatorios")

    st.write(
        "Catálogo cargado desde el Anexo N° 6 proporcionado."
    )

    vista = catalogo.copy()
    vista["Duración mínima"] = vista["Horas"].astype(str) + " horas"

    st.dataframe(
        vista[
            ["Item", "Curso", "Duración mínima"]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Item": st.column_config.NumberColumn("Ítem"),
            "Curso": st.column_config.TextColumn(
                "Curso",
                width="large"
            ),
            "Duración mínima": st.column_config.TextColumn(
                "Duración mínima"
            )
        }
    )

    st.caption(
        "Nota del documento: los cursos que debe llevar cada trabajador "
        "se determinan de acuerdo al puesto y en base a la IPERC."
    )


# ============================================================
# MATRIZ
# ============================================================

elif pagina == "Matriz de capacitación":

    st.title("📋 Matriz de capacitación")

    st.write(
        "Cada puesto puede tener los 20 cursos del catálogo. "
        "La selección final de cursos por puesto se puede alimentar "
        "desde el análisis IPERC."
    )

    # Crear puestos manualmente o desde Excel.
    st.subheader("1. Puestos de trabajo")

    col1, col2 = st.columns([3, 1])

    with col1:
        puesto_nuevo = st.text_input(
            "Agregar puesto de trabajo",
            placeholder="Ejemplo: Operador de Camión Mina"
        )

    with col2:
        st.write("")
        st.write("")
        if st.button("➕ Agregar puesto"):
            if puesto_nuevo.strip():
                if puesto_nuevo.strip() not in st.session_state.puestos:
                    st.session_state.puestos.append(
                        puesto_nuevo.strip()
                    )
                    st.session_state.matriz = crear_matriz_puestos(
                        st.session_state.puestos
                    )
                    st.rerun()

    archivo = st.file_uploader(
        "O carga un Excel para detectar automáticamente Puesto de trabajo / Cargo",
        type=["xlsx", "xls"],
        key="matriz_excel"
    )

    if archivo:
        if st.button(
            "🔎 Detectar puestos del Excel",
            use_container_width=True
        ):
            try:
                puestos = extraer_puestos_excel(
                    archivo.getvalue()
                )

                if puestos:
                    st.session_state.puestos = sorted(
                        set(
                            st.session_state.puestos + puestos
                        )
                    )

                    st.session_state.matriz = crear_matriz_puestos(
                        st.session_state.puestos
                    )

                    st.success(
                        f"Se detectaron {len(puestos)} puesto(s)."
                    )
                else:
                    st.warning(
                        "No se encontró una columna Puesto de trabajo, "
                        "Cargo o Posición."
                    )

            except Exception as e:
                st.error(f"No se pudo leer el Excel: {e}")

    if not st.session_state.matriz.empty:

        st.subheader("2. Matriz")

        editada = st.data_editor(
            st.session_state.matriz,
            use_container_width=True,
            hide_index=True,
            disabled=[
                "Item",
                "Puesto de trabajo",
                "Duración",
                "Curso",
                "Estado"
            ],
            column_config={
                "Item": st.column_config.NumberColumn(
                    "Ítem"
                ),
                "Puesto de trabajo": st.column_config.TextColumn(
                    "Puesto de trabajo"
                ),
                "Modalidad de curso":
                    st.column_config.SelectboxColumn(
                        "Modalidad de curso",
                        options=[
                            "Presencial",
                            "Virtual"
                        ],
                        required=True
                    ),
                "Duración":
                    st.column_config.NumberColumn(
                        "Duración",
                        format="%d h"
                    ),
                "Certificado / lista de asistencia":
                    st.column_config.CheckboxColumn(
                        "Certificado / lista de asistencia ✓"
                    ),
                "Curso":
                    st.column_config.TextColumn(
                        "Curso",
                        width="large"
                    ),
                "Asistencia":
                    st.column_config.CheckboxColumn(
                        "Asistencia ✓"
                    ),
                "Nota":
                    st.column_config.NumberColumn(
                        "Nota",
                        min_value=0,
                        max_value=20,
                        step=0.5
                    ),
                "Comentarios":
                    st.column_config.TextColumn(
                        "Comentarios",
                        width="large"
                    ),
                "Estado":
                    st.column_config.TextColumn(
                        "Estado"
                    )
            }
        )

        st.session_state.matriz = actualizar_estado(editada)

        st.success("Cambios guardados en la matriz.")

    else:
        st.info(
            "Agrega un puesto o carga un Excel para generar la matriz."
        )


# ============================================================
# RESUMEN
# ============================================================

elif pagina == "Resumen":

    st.title("📊 Resumen")

    matriz = st.session_state.matriz

    if matriz.empty:
        st.info(
            "Todavía no hay puestos cargados."
        )
    else:

        total = len(matriz)
        completados = int(
            (matriz["Estado"] == "COMPLETADO").sum()
        )
        pendientes = total - completados

        a, b, c = st.columns(3)

        a.metric("Registros", total)
        b.metric("Completados", completados)
        c.metric("Pendientes", pendientes)

        st.subheader("Cursos por puesto")

        resumen = (
            matriz
            .groupby("Puesto de trabajo", as_index=False)
            .agg(
                Cursos=("Curso", "count"),
                Completados=(
                    "Estado",
                    lambda x: int(
                        (x == "COMPLETADO").sum()
                    )
                ),
                Pendientes=(
                    "Estado",
                    lambda x: int(
                        (x != "COMPLETADO").sum()
                    )
                )
            )
        )

        st.dataframe(
            resumen,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# EXPORTAR
# ============================================================

elif pagina == "Exportar":

    st.title("📥 Exportar")

    matriz = st.session_state.matriz

    if matriz.empty:
        st.info(
            "No hay una matriz para exportar."
        )
    else:

        memoria = io.BytesIO()

        with pd.ExcelWriter(
            memoria,
            engine="openpyxl"
        ) as writer:

            matriz.to_excel(
                writer,
                sheet_name="Matriz de capacitación",
                index=False
            )

            catalogo.to_excel(
                writer,
                sheet_name="Cursos obligatorios",
                index=False
            )

        memoria.seek(0)

        st.download_button(
            "📥 Descargar matriz en Excel",
            data=memoria,
            file_name="CapacityAI_Matriz_Capacitacion.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True
        )
