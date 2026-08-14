
import io
import re
import unicodedata
from collections import defaultdict

import pandas as pd
import streamlit as st


# ============================================================
# CAPACITY AI - V3
# Identificación de cursos por puesto + catálogo obligatorio
# + seguimiento de modalidad, asistencia, nota y certificado.
#
# Lógica principal:
# Puesto de Trabajo / Cargo
#        ↓
# Control Administrativo
#        ↓
# Capacitación / Entrenamiento / Curso
#        ↓
# Curso requerido
#        ↓
# Comparación con catálogo obligatorio
#        ↓
# Matriz de seguimiento
# ============================================================

st.set_page_config(
    page_title="Capacity AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------
# ESTILOS
# ----------------------------
st.markdown("""
<style>
.stApp {
    background: #f5f7fb;
}
.block-container {
    padding-top: 1.8rem;
}
[data-testid="stSidebar"] {
    background: #111827;
}
[data-testid="stSidebar"] * {
    color: white !important;
}
.kpi {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 16px;
}
.small-note {
    color: #6b7280;
    font-size: 0.85rem;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# CATÁLOGO OBLIGATORIO
# ============================================================
# Los nombres se dejan editables desde la sección "Catálogo".
# Las horas corresponden a la tabla de referencia proporcionada.
# Si se dispone del Excel/PDF oficial del Anexo, conviene reemplazar
# los nombres por su texto exacto.

CATALOGO_INICIAL = [
    {"Item": 1, "Curso": "Gestión de Seguridad y Salud Ocupacional basada en el Reglamento de Seguridad y Salud Ocupacional en Minería", "Horas": 3},
    {"Item": 2, "Curso": "Notificación, Investigación y reporte de incidentes, accidentes e incidentes de trabajo", "Horas": 3},
    {"Item": 3, "Curso": "Liderazgo y motivación. Seguridad basada en el Comportamiento", "Horas": 2},
    {"Item": 4, "Curso": "Respuesta a Emergencias por áreas específicas", "Horas": 4},
    {"Item": 5, "Curso": "IPERC", "Horas": 4},
    {"Item": 6, "Curso": "Trabajos en altura", "Horas": 4},
    {"Item": 7, "Curso": "Gestión de Riesgos psicosociales", "Horas": 4},
    {"Item": 8, "Curso": "Significado y uso de códigos y colores", "Horas": 2},
    {"Item": 9, "Curso": "Auditoría, Fiscalización e Inspección de seguridad", "Horas": 3},
    {"Item": 10, "Curso": "Primeros Auxilios", "Horas": 3},
    {"Item": 11, "Curso": "Prevención y Protección Contra Incendios", "Horas": 2},
    {"Item": 12, "Curso": "Estándares y procedimientos escritos de trabajo seguro por actividades", "Horas": 2},
    {"Item": 13, "Curso": "Disposición de residuos, materiales y sustancias peligrosas", "Horas": 2},
    {"Item": 14, "Curso": "Manejo defensivo y transporte de personal", "Horas": 4},
    {"Item": 15, "Curso": "Comité de Seguridad y Salud Ocupacional, Reglamento Interno de Seguridad y Salud Ocupacional y Programa Anual", "Horas": 3},
    {"Item": 16, "Curso": "Seguridad en la ergonomía", "Horas": 2},
    {"Item": 17, "Curso": "Riesgos Eléctricos", "Horas": 3},
    {"Item": 18, "Curso": "Prevención de accidente por desprendimiento de rocas", "Horas": 3},
    {"Item": 19, "Curso": "Prevención de accidente por gaseamiento", "Horas": 3},
    {"Item": 20, "Curso": "Uso de equipo de protección personal (EPP)", "Horas": 3},
]


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
    texto = normalizar(texto)

    # Equivalencias muy conservadoras.
    equivalencias = {
        "CAPACITACION EN PRIMEROS AUXILIOS": "PRIMEROS AUXILIOS",
        "CURSO DE PRIMEROS AUXILIOS": "PRIMEROS AUXILIOS",
        "ENTRENAMIENTO EN PRIMEROS AUXILIOS": "PRIMEROS AUXILIOS",
        "EQUIPO DE PROTECCION PERSONAL": "USO DE EQUIPO DE PROTECCION PERSONAL (EPP)",
        "USO CORRECTO DEL EQUIPO DE PROTECCION PERSONAL": "USO DE EQUIPO DE PROTECCION PERSONAL (EPP)",
    }

    return equivalencias.get(texto, texto)


def extraer_puestos(valor):
    texto = normalizar(valor)

    if not texto:
        return []

    partes = re.split(r"[\n;]+", texto)

    resultado = []
    vistos = set()

    for parte in partes:
        parte = parte.strip(" -•*")
        if not parte:
            continue

        if parte in {
            "PUESTO DE TRABAJO / CARGO",
            "PUESTO",
            "CARGO",
            "NAN"
        }:
            continue

        if parte not in vistos:
            vistos.add(parte)
            resultado.append(parte)

    return resultado


# ============================================================
# DETECCIÓN DE CAPACITACIÓN EN CONTROL ADMINISTRATIVO
# ============================================================

PATRONES_CAPACITACION = [
    re.compile(r"^\s*CAPACITACION(?:ES)?\s*:?\s*$", re.I),
    re.compile(r"^\s*ENTRENAMIENTO(?:S)?\s*:?\s*$", re.I),
    re.compile(r"^\s*CURSO(?:S)?\s*:?\s*$", re.I),
    re.compile(
        r"^\s*(?:CAPACITACION(?:ES)?\s*/\s*ENTRENAMIENTO(?:S)?|"
        r"ENTRENAMIENTO(?:S)?\s*/\s*CAPACITACION(?:ES)?|"
        r"CAPACITACION(?:ES)?\s+Y\s+ENTRENAMIENTO(?:S)?|"
        r"CAPACITACION(?:ES)?\s+E\s+ENTRENAMIENTO(?:S)?)\s*:?\s*$",
        re.I
    ),
]


def es_marcador_capacitacion(linea):
    linea = normalizar(linea)
    return any(p.match(linea) for p in PATRONES_CAPACITACION)


def es_fin_capacitacion(linea):
    linea = normalizar(linea)

    if "REFERENCIA DOCUMENTARIA" in linea:
        return True

    encabezados = [
        "CONTROL DE INGENIERIA",
        "CONTROLES DE INGENIERIA",
        "ELIMINACION",
        "SUSTITUCION",
    ]

    return linea in encabezados


def extraer_cursos_control(valor):
    texto = normalizar(valor)

    if not texto:
        return []

    cursos = []
    capturando = False

    for linea in texto.split("\n"):
        linea = linea.strip()

        if not linea:
            continue

        if es_marcador_capacitacion(linea):
            capturando = True
            continue

        if es_fin_capacitacion(linea):
            capturando = False
            continue

        if not capturando:
            continue

        curso = linea.strip(" -•*")
        if len(curso) < 3:
            continue

        # Evitar líneas claramente documentarias.
        if re.match(r"^(YAN[-\s]|ISO\s*\d|NTP\s*\d|DS\s*\d)", curso):
            continue

        cursos.append(curso)

    salida = []
    claves = set()

    for curso in cursos:
        clave = clave_curso(curso)

        if clave and clave not in claves:
            claves.add(clave)
            salida.append(curso)

    return salida


# ============================================================
# LECTURA DEL EXCEL
# ============================================================

def encontrar_encabezado(df):
    mejor_fila = None
    mejor_puntaje = 0

    for i in range(min(60, len(df))):
        fila = [normalizar(x) for x in df.iloc[i].tolist()]

        puntaje = 0

        if "PUESTO DE TRABAJO / CARGO" in fila:
            puntaje += 10

        if "CONTROL ADMINISTRATIVO" in fila:
            puntaje += 10

        if "PROCESO" in fila:
            puntaje += 1

        if "ACTIVIDAD" in fila:
            puntaje += 1

        if "TAREA" in fila:
            puntaje += 1

        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor_fila = i

    return mejor_fila


def preparar_tabla(df, fila):
    encabezados = []
    repetidos = {}

    for i, valor in enumerate(df.iloc[fila].tolist()):
        nombre = normalizar(valor)

        if not nombre:
            nombre = f"COLUMNA_{i+1}"

        if nombre in repetidos:
            repetidos[nombre] += 1
            nombre = f"{nombre}_{repetidos[nombre]}"
        else:
            repetidos[nombre] = 1

        encabezados.append(nombre)

    tabla = df.iloc[fila + 1:].copy()
    tabla.columns = encabezados
    tabla = tabla.dropna(how="all")

    return tabla.reset_index(drop=True)


def analizar_excel(archivo):
    archivo.seek(0)
    xls = pd.ExcelFile(archivo)

    evidencias = []

    for hoja in xls.sheet_names:
        archivo.seek(0)
        df = pd.read_excel(
            archivo,
            sheet_name=hoja,
            header=None
        )

        fila = encontrar_encabezado(df)

        if fila is None:
            continue

        tabla = preparar_tabla(df, fila)
        columnas = list(tabla.columns)

        puestos_col = None
        controles = []

        for col in columnas:
            c = normalizar(col)

            if c == "PUESTO DE TRABAJO / CARGO":
                puestos_col = col

            if c.startswith("CONTROL ADMINISTRATIVO"):
                controles.append(col)

        if not puestos_col or not controles:
            continue

        # Tomamos el primer Control Administrativo.
        # Si el archivo tiene varios, se puede cambiar aquí.
        control_col = controles[0]

        for numero, (_, fila_datos) in enumerate(
            tabla.iterrows(),
            start=1
        ):
            puestos = extraer_puestos(
                fila_datos[puestos_col]
            )

            cursos = extraer_cursos_control(
                fila_datos[control_col]
            )

            if not puestos or not cursos:
                continue

            for puesto in puestos:
                for curso in cursos:
                    evidencias.append({
                        "Puesto de trabajo": puesto,
                        "Curso detectado": curso,
                        "Curso clave": clave_curso(curso),
                        "Hoja": hoja,
                        "Fila": numero,
                        "Fuente": "Control Administrativo"
                    })

    if not evidencias:
        return pd.DataFrame()

    return pd.DataFrame(evidencias).drop_duplicates()


# ============================================================
# CRUCE CON CATÁLOGO
# ============================================================

def preparar_catalogo():
    df = pd.DataFrame(CATALOGO_INICIAL)
    df["Clave"] = df["Curso"].apply(clave_curso)
    return df


def buscar_catalogo(curso, catalogo):
    clave = clave_curso(curso)

    # Coincidencia exacta
    encontrado = catalogo[
        catalogo["Clave"] == clave
    ]

    if not encontrado.empty:
        return encontrado.iloc[0]

    # Coincidencia conservadora por inclusión.
    palabras = [
        p for p in clave.split()
        if len(p) >= 5
    ]

    if not palabras:
        return None

    candidatos = []

    for _, fila in catalogo.iterrows():
        clave_catalogo = fila["Clave"]

        coincidencias = sum(
            1 for palabra in palabras
            if palabra in clave_catalogo
        )

        porcentaje = coincidencias / len(palabras)

        if porcentaje >= 0.70:
            candidatos.append(
                (porcentaje, fila)
            )

    if candidatos:
        candidatos.sort(
            key=lambda x: x[0],
            reverse=True
        )
        return candidatos[0][1]

    return None


def generar_matriz(evidencias, catalogo):
    filas = []

    agrupado = (
        evidencias
        .groupby(
            [
                "Puesto de trabajo",
                "Curso clave"
            ]
        )
        .agg(
            Curso_detectado=(
                "Curso detectado",
                lambda x: " | ".join(sorted(set(x)))
            ),
            Evidencias=("Curso detectado", "count")
        )
        .reset_index()
    )

    for _, fila in agrupado.iterrows():

        curso_detectado = fila["Curso_detectado"].split(" | ")[0]

        match = buscar_catalogo(
            curso_detectado,
            catalogo
        )

        if match is not None:
            item = int(match["Item"])
            curso_catalogo = match["Curso"]
            horas = int(match["Horas"])
            coincide = "Sí"
        else:
            item = None
            curso_catalogo = curso_detectado
            horas = None
            coincide = "No encontrado en catálogo"

        filas.append({
            "Ítem": item,
            "Puesto de trabajo": fila["Puesto de trabajo"],
            "Modalidad": "Por definir",
            "Duración (horas)": horas,
            "Certificado / Lista de asistencia": False,
            "Curso": curso_catalogo,
            "Asistencia": False,
            "Nota": None,
            "Comentarios": "",
            "Estado": "Pendiente",
            "Coincide con catálogo": coincide,
            "Evidencias IPERC": int(fila["Evidencias"]),
            "Curso detectado": fila["Curso_detectado"]
        })

    if not filas:
        return pd.DataFrame()

    return pd.DataFrame(filas).sort_values(
        ["Puesto de trabajo", "Ítem"],
        na_position="last"
    ).reset_index(drop=True)


# ============================================================
# ESTADO
# ============================================================

def calcular_estado(fila):
    asistencia = bool(fila.get("Asistencia", False))
    certificado = bool(
        fila.get(
            "Certificado / Lista de asistencia",
            False
        )
    )

    nota = fila.get("Nota")

    if not asistencia:
        return "PENDIENTE"

    if pd.isna(nota) or nota is None or str(nota).strip() == "":
        return "PENDIENTE DE NOTA"

    if not certificado:
        return "PENDIENTE DE CERTIFICADO/LISTA"

    return "COMPLETADO"


def actualizar_estados(df):
    if df.empty:
        return df

    df = df.copy()
    df["Estado"] = df.apply(
        calcular_estado,
        axis=1
    )

    return df


# ============================================================
# EXPORTAR
# ============================================================

def exportar_excel(matriz, evidencias, catalogo):
    salida = io.BytesIO()

    with pd.ExcelWriter(
        salida,
        engine="openpyxl"
    ) as writer:

        matriz.to_excel(
            writer,
            sheet_name="Matriz de capacitación",
            index=False
        )

        catalogo.to_excel(
            writer,
            sheet_name="Catálogo obligatorio",
            index=False
        )

        evidencias.to_excel(
            writer,
            sheet_name="Evidencias IPERC",
            index=False
        )

    salida.seek(0)
    return salida


# ============================================================
# SESSION STATE
# ============================================================

if "catalogo" not in st.session_state:
    st.session_state.catalogo = preparar_catalogo()

if "evidencias" not in st.session_state:
    st.session_state.evidencias = pd.DataFrame()

if "matriz" not in st.session_state:
    st.session_state.matriz = pd.DataFrame()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🎓 Capacity AI")
st.sidebar.caption(
    "Identificación y seguimiento de capacitación"
)

menu = st.sidebar.radio(
    "Módulos",
    [
        "🏠 Dashboard",
        "📂 Analizar IPERC",
        "👔 Por puesto",
        "📋 Matriz de capacitación",
        "📚 Catálogo obligatorio",
        "📊 Resumen",
        "📥 Exportar"
    ]
)


# ============================================================
# DASHBOARD
# ============================================================

if menu == "🏠 Dashboard":

    st.title("🎓 Capacity AI")

    st.subheader(
        "Matriz inteligente de capacitación por puesto"
    )

    st.write(
        "La aplicación identifica las capacitaciones, "
        "entrenamientos y cursos dentro de Control Administrativo, "
        "los agrupa por puesto y los cruza con el catálogo "
        "obligatorio."
    )

    matriz = st.session_state.matriz

    puestos = (
        matriz["Puesto de trabajo"].nunique()
        if not matriz.empty else 0
    )

    cursos = (
        matriz["Curso"].nunique()
        if not matriz.empty else 0
    )

    pendientes = (
        int((matriz["Estado"] == "PENDIENTE").sum())
        if not matriz.empty else 0
    )

    completados = (
        int((matriz["Estado"] == "COMPLETADO").sum())
        if not matriz.empty else 0
    )

    a, b, c, d = st.columns(4)

    a.metric("Puestos", puestos)
    b.metric("Cursos", cursos)
    c.metric("Pendientes", pendientes)
    d.metric("Completados", completados)

    st.divider()

    st.info(
        "Flujo: Puesto de trabajo → Control Administrativo → "
        "Capacitación/Entrenamiento/Curso → Catálogo → "
        "Asistencia + Nota + Certificado → Estado."
    )


# ============================================================
# ANALIZAR IPERC
# ============================================================

elif menu == "📂 Analizar IPERC":

    st.title("📂 Analizar matriz IPERC")

    archivo = st.file_uploader(
        "Carga el Excel de prueba o una matriz IPERC",
        type=["xlsx", "xls"]
    )

    if archivo:

        st.success(
            f"Archivo listo: {archivo.name}"
        )

        if st.button(
            "🔍 Analizar y generar matriz",
            type="primary",
            use_container_width=True
        ):

            with st.spinner(
                "Analizando puestos y Control Administrativo..."
            ):

                evidencias = analizar_excel(
                    archivo
                )

                if evidencias.empty:
                    matriz = pd.DataFrame()
                else:
                    matriz = generar_matriz(
                        evidencias,
                        st.session_state.catalogo
                    )

            st.session_state.evidencias = evidencias
            st.session_state.matriz = matriz

            if matriz.empty:

                st.error(
                    "No se encontraron cursos. "
                    "Verifica que el Excel tenga las columnas "
                    "'Puesto de Trabajo / Cargo' y "
                    "'Control Administrativo', y que dentro del "
                    "control existan bloques de Capacitación, "
                    "Entrenamiento o Curso."
                )

            else:

                st.success(
                    f"Listo. Se encontraron "
                    f"{len(matriz)} relaciones puesto-curso."
                )

                st.dataframe(
                    matriz,
                    use_container_width=True,
                    hide_index=True
                )


# ============================================================
# POR PUESTO
# ============================================================

elif menu == "👔 Por puesto":

    st.title("👔 Capacitación por puesto")

    matriz = st.session_state.matriz

    if matriz.empty:

        st.info(
            "Primero analiza una matriz IPERC."
        )

    else:

        puestos = sorted(
            matriz["Puesto de trabajo"].unique()
        )

        puesto = st.selectbox(
            "Selecciona el puesto",
            puestos
        )

        datos = matriz[
            matriz["Puesto de trabajo"] == puesto
        ].copy()

        st.metric(
            "Cursos requeridos",
            len(datos)
        )

        st.dataframe(
            datos[
                [
                    "Ítem",
                    "Curso",
                    "Duración (horas)",
                    "Modalidad",
                    "Asistencia",
                    "Nota",
                    "Certificado / Lista de asistencia",
                    "Estado",
                    "Comentarios"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# MATRIZ DE CAPACITACIÓN
# ============================================================

elif menu == "📋 Matriz de capacitación":

    st.title("📋 Matriz de capacitación")

    matriz = st.session_state.matriz

    if matriz.empty:

        st.info(
            "Primero analiza una matriz IPERC."
        )

    else:

        st.write(
            "Marca asistencia y certificado/lista de asistencia. "
            "Ingresa la nota cuando corresponda. "
            "La aplicación actualizará el estado automáticamente."
        )

        editada = st.data_editor(
            matriz,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "Modalidad": st.column_config.SelectboxColumn(
                    "Modalidad",
                    options=[
                        "Por definir",
                        "Presencial",
                        "Virtual"
                    ],
                    required=True
                ),
                "Duración (horas)": st.column_config.NumberColumn(
                    "Duración (horas)",
                    min_value=0,
                    step=1
                ),
                "Certificado / Lista de asistencia":
                    st.column_config.CheckboxColumn(
                        "Certificado / Lista de asistencia"
                    ),
                "Asistencia":
                    st.column_config.CheckboxColumn(
                        "Asistencia"
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
                        "Comentarios"
                    ),
                "Estado":
                    st.column_config.TextColumn(
                        "Estado",
                        disabled=True
                    )
            }
        )

        editada = actualizar_estados(
            editada
        )

        st.session_state.matriz = editada

        st.success(
            "Cambios guardados en la sesión."
        )


# ============================================================
# CATÁLOGO
# ============================================================

elif menu == "📚 Catálogo obligatorio":

    st.title("📚 Catálogo obligatorio")

    st.write(
        "Aquí se mantiene el catálogo de referencia. "
        "Puedes corregir los nombres si luego nos entregan "
        "el documento oficial en Excel/PDF."
    )

    catalogo = st.data_editor(
        st.session_state.catalogo,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Item": st.column_config.NumberColumn(
                "Ítem",
                disabled=True
            ),
            "Horas": st.column_config.NumberColumn(
                "Horas obligatorias",
                min_value=0,
                step=1
            ),
            "Curso": st.column_config.TextColumn(
                "Curso obligatorio"
            ),
            "Clave": None
        }
    )

    catalogo["Clave"] = catalogo["Curso"].apply(
        clave_curso
    )

    st.session_state.catalogo = catalogo


# ============================================================
# RESUMEN
# ============================================================

elif menu == "📊 Resumen":

    st.title("📊 Resumen de capacitación")

    matriz = st.session_state.matriz

    if matriz.empty:

        st.info(
            "Primero analiza una matriz IPERC."
        )

    else:

        completados = int(
            (matriz["Estado"] == "COMPLETADO").sum()
        )

        pendientes = int(
            (matriz["Estado"] != "COMPLETADO").sum()
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Total de capacitaciones",
            len(matriz)
        )

        c2.metric(
            "Completadas",
            completados
        )

        c3.metric(
            "Pendientes",
            pendientes
        )

        st.subheader(
            "Cursos que se deben llevar"
        )

        resumen = (
            matriz
            .groupby("Curso")
            .agg(
                Puestos=(
                    "Puesto de trabajo",
                    lambda x: len(set(x))
                ),
                Horas=(
                    "Duración (horas)",
                    "first"
                ),
                Completados=(
                    "Estado",
                    lambda x: int(
                        (x == "COMPLETADO").sum()
                    )
                )
            )
            .reset_index()
            .sort_values(
                "Puestos",
                ascending=False
            )
        )

        st.dataframe(
            resumen,
            use_container_width=True,
            hide_index=True
        )

        st.subheader(
            "Estado por puesto"
        )

        resumen_puesto = (
            matriz
            .groupby("Puesto de trabajo")
            .agg(
                Cursos=(
                    "Curso",
                    "count"
                ),
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
            .reset_index()
        )

        st.dataframe(
            resumen_puesto,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# EXPORTAR
# ============================================================

elif menu == "📥 Exportar":

    st.title("📥 Exportar matriz")

    matriz = st.session_state.matriz
    evidencias = st.session_state.evidencias
    catalogo = st.session_state.catalogo

    if matriz.empty:

        st.info(
            "Primero analiza una matriz."
        )

    else:

        archivo = exportar_excel(
            matriz,
            evidencias,
            catalogo
        )

        st.download_button(
            "📥 Descargar Excel",
            data=archivo,
            file_name="CapacityAI_Matriz_Capacitacion.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True
        )
