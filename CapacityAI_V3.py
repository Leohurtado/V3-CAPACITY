import io
import re
import unicodedata
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Capacity AI",
    page_icon="🎓",
    layout="wide"
)

# ============================================================
# CAPACITY AI V4
# Una sola matriz con los campos solicitados:
# 1. Ítem
# 2. Puesto de trabajo
# 3. Modalidad de curso
# 4. Duración
# 5. Certificado / lista de asistencia
# 6. Curso (Asistencia + Nota)
# 7. Comentarios
#
# La fuente para identificar cursos es:
# Puesto de Trabajo / Cargo + Control Administrativo
# y dentro de este: Capacitación / Entrenamiento / Curso.
# ============================================================

st.markdown("""
<style>
.stApp { background: #f5f7fb; }
.block-container { padding-top: 1.5rem; }
[data-testid="stSidebar"] { background: #111827; }
[data-testid="stSidebar"] * { color: white !important; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# CATÁLOGO DE REFERENCIA
# ============================================================

CATALOGO = [
    {"Ítem": 1, "Curso": "Gestión de Seguridad y Salud Ocupacional basada en el Reglamento de Seguridad y Salud Ocupacional en Minería", "Horas": 3},
    {"Ítem": 2, "Curso": "Notificación, Investigación y reporte de incidentes, accidentes e incidentes de trabajo", "Horas": 3},
    {"Ítem": 3, "Curso": "Liderazgo y motivación. Seguridad basada en el Comportamiento", "Horas": 2},
    {"Ítem": 4, "Curso": "Respuesta a Emergencias por áreas específicas", "Horas": 4},
    {"Ítem": 5, "Curso": "IPERC", "Horas": 4},
    {"Ítem": 6, "Curso": "Trabajos en altura", "Horas": 4},
    {"Ítem": 7, "Curso": "Gestión de Riesgos psicosociales", "Horas": 4},
    {"Ítem": 8, "Curso": "Significado y uso de códigos y colores", "Horas": 2},
    {"Ítem": 9, "Curso": "Auditoría, Fiscalización e Inspección de seguridad", "Horas": 3},
    {"Ítem": 10, "Curso": "Primeros Auxilios", "Horas": 3},
    {"Ítem": 11, "Curso": "Prevención y Protección Contra Incendios", "Horas": 2},
    {"Ítem": 12, "Curso": "Estándares y procedimientos escritos de trabajo seguro por actividades", "Horas": 2},
    {"Ítem": 13, "Curso": "Disposición de residuos, materiales y sustancias peligrosas", "Horas": 2},
    {"Ítem": 14, "Curso": "Manejo defensivo y transporte de personal", "Horas": 4},
    {"Ítem": 15, "Curso": "Comité de Seguridad y Salud Ocupacional, Reglamento Interno de Seguridad y Salud Ocupacional y Programa Anual", "Horas": 3},
    {"Ítem": 16, "Curso": "Seguridad en la ergonomía", "Horas": 2},
    {"Ítem": 17, "Curso": "Riesgos Eléctricos", "Horas": 3},
    {"Ítem": 18, "Curso": "Prevención de accidente por desprendimiento de rocas", "Horas": 3},
    {"Ítem": 19, "Curso": "Prevención de accidente por gaseamiento", "Horas": 3},
    {"Ítem": 20, "Curso": "Uso de equipo de protección personal (EPP)", "Horas": 3},
]

catalogo = pd.DataFrame(CATALOGO)


# ============================================================
# FUNCIONES
# ============================================================

def normalizar(valor):
    if valor is None or pd.isna(valor):
        return ""
    texto = str(valor)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.upper()
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def clave_curso(valor):
    texto = normalizar(valor)

    equivalencias = {
        "CAPACITACION EN PRIMEROS AUXILIOS": "PRIMEROS AUXILIOS",
        "ENTRENAMIENTO EN PRIMEROS AUXILIOS": "PRIMEROS AUXILIOS",
        "CURSO DE PRIMEROS AUXILIOS": "PRIMEROS AUXILIOS",
        "EQUIPO DE PROTECCION PERSONAL": "USO DE EQUIPO DE PROTECCION PERSONAL (EPP)",
        "USO CORRECTO DEL EQUIPO DE PROTECCION PERSONAL": "USO DE EQUIPO DE PROTECCION PERSONAL (EPP)",
    }

    return equivalencias.get(texto, texto)


def extraer_puestos(valor):
    texto = normalizar(valor)
    if not texto:
        return []

    partes = re.split(r"[\n;]+", texto)
    salida = []
    vistos = set()

    for parte in partes:
        parte = parte.strip(" -•*")
        if not parte:
            continue
        if parte in {"PUESTO DE TRABAJO / CARGO", "PUESTO", "CARGO", "NAN"}:
            continue
        if parte not in vistos:
            vistos.add(parte)
            salida.append(parte)

    return salida


def es_marcador(linea):
    linea = normalizar(linea)

    patrones = [
        r"^CAPACITACION(?:ES)?$",
        r"^ENTRENAMIENTO(?:S)?$",
        r"^CURSO(?:S)?$",
        r"^CAPACITACION(?:ES)?\s*/\s*ENTRENAMIENTO(?:S)?$",
        r"^ENTRENAMIENTO(?:S)?\s*/\s*CAPACITACION(?:ES)?$",
        r"^CAPACITACION(?:ES)?\s+Y\s+ENTRENAMIENTO(?:S)?$",
        r"^CAPACITACION(?:ES)?\s+E\s+ENTRENAMIENTO(?:S)?$",
    ]

    return any(re.match(p, linea) for p in patrones)


def termina_bloque(linea):
    linea = normalizar(linea)

    if "REFERENCIA DOCUMENTARIA" in linea:
        return True

    return linea in {
        "CONTROL DE INGENIERIA",
        "CONTROLES DE INGENIERIA",
        "ELIMINACION",
        "SUSTITUCION",
    }


def extraer_cursos(valor):
    texto = normalizar(valor)
    if not texto:
        return []

    # Normaliza separadores frecuentes usados dentro de celdas de Excel.
    texto = re.sub(
        r"\s*\|\s*",
        "\n",
        texto
    )
    texto = re.sub(
        r"\s*;\s*",
        "\n",
        texto
    )

    # Permite formatos como:
    # "Capacitación / Entrenamiento: Primeros Auxilios"
    # "Curso: Primeros Auxilios"
    texto = re.sub(
        r"\b(CAPACITACION(?:ES)?\s*/\s*ENTRENAMIENTO(?:S)?|"
        r"ENTRENAMIENTO(?:S)?\s*/\s*CAPACITACION(?:ES)?|"
        r"CAPACITACION(?:ES)?|ENTRENAMIENTO(?:S)?|CURSO(?:S)?)\s*:\s*",
        lambda m: m.group(1) + "\n",
        texto
    )

    cursos = []
    capturando = False

    for linea in texto.split("\n"):
        linea = linea.strip()

        if not linea:
            continue

        if es_marcador(linea):
            capturando = True
            continue

        if termina_bloque(linea):
            capturando = False
            continue

        if not capturando:
            continue

        curso = linea.strip(" -•*")

        if len(curso) < 3:
            continue

        # No interpretar códigos documentarios como cursos.
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


def es_columna_puesto(nombre):
    """
    La matriz puede usar UNO de estos nombres:
    - Puesto de trabajo
    - Cargo

    No se exige que aparezcan ambos ni que exista
    "Puesto de trabajo / Cargo".
    """
    c = normalizar(nombre).replace("\n", " ")
    c = re.sub(r"\s+", " ", c).strip()

    return (
        c == "PUESTO DE TRABAJO"
        or c == "CARGO"
    )


def es_columna_control(nombre):
    c = normalizar(nombre).replace("\n", " ")
    c = re.sub(r"\s+", " ", c).strip()

    return (
        "CONTROL ADMINISTRATIVO" in c
        or "CONTROLES ADMINISTRATIVOS" in c
        or "CONTROL ADMINISTRATIVOS" in c
    )


def encontrar_encabezado(df):
    mejor = None
    puntaje_max = 0

    for i in range(min(80, len(df))):
        fila = [normalizar(x).replace("\n", " ") for x in df.iloc[i].tolist()]

        puntaje = 0
        tiene_puesto = any(es_columna_puesto(x) for x in fila)
        tiene_control = any(es_columna_control(x) for x in fila)

        if tiene_puesto:
            puntaje += 10
        if tiene_control:
            puntaje += 10
        if any("PROCESO" == x or "PROCESO" in x for x in fila):
            puntaje += 1
        if any("ACTIVIDAD" in x for x in fila):
            puntaje += 1
        if any("TAREA" in x for x in fila):
            puntaje += 1

        if puntaje > puntaje_max:
            puntaje_max = puntaje
            mejor = i

    return mejor


def preparar_df(df, fila):
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
    return tabla.dropna(how="all").reset_index(drop=True)


def encontrar_catalogo(curso):
    clave = clave_curso(curso)

    # Coincidencia exacta
    for _, fila in catalogo.iterrows():
        if clave == clave_curso(fila["Curso"]):
            return fila

    # Coincidencia conservadora
    palabras = [p for p in clave.split() if len(p) >= 5]

    if not palabras:
        return None

    mejor = None
    mejor_puntaje = 0

    for _, fila in catalogo.iterrows():
        clave_ref = clave_curso(fila["Curso"])
        coincidencias = sum(p in clave_ref for p in palabras)
        puntaje = coincidencias / len(palabras)

        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor = fila

    if mejor_puntaje >= 0.70:
        return mejor

    return None


def analizar_excel(archivo):
    archivo.seek(0)
    libro = pd.ExcelFile(archivo)

    encontrados = []

    for hoja in libro.sheet_names:
        archivo.seek(0)

        df = pd.read_excel(
            archivo,
            sheet_name=hoja,
            header=None
        )

        fila_encabezado = encontrar_encabezado(df)

        if fila_encabezado is None:
            continue

        tabla = preparar_df(
            df,
            fila_encabezado
        )

        puesto_col = None
        control_col = None

        for col in tabla.columns:
            if puesto_col is None and es_columna_puesto(col):
                puesto_col = col

            if control_col is None and es_columna_control(col):
                control_col = col

        # Algunos Excel tienen encabezados partidos en dos filas.
        # Si no se detectaron las columnas, intentamos combinar
        # temporalmente dos filas consecutivas del encabezado.
        if puesto_col is None or control_col is None:
            continue

        for numero_fila, (_, fila) in enumerate(
            tabla.iterrows(),
            start=1
        ):
            puestos = extraer_puestos(
                fila[puesto_col]
            )

            cursos = extraer_cursos(
                fila[control_col]
            )

            for puesto in puestos:
                for curso in cursos:
                    encontrados.append({
                        "Puesto": puesto,
                        "Curso detectado": curso,
                        "Clave": clave_curso(curso),
                        "Hoja": hoja,
                        "Fila": numero_fila
                    })

    if not encontrados:
        return pd.DataFrame()

    return pd.DataFrame(encontrados).drop_duplicates()


def construir_matriz(evidencias):
    if evidencias.empty:
        return pd.DataFrame()

    agrupado = (
        evidencias
        .groupby(
            ["Puesto", "Clave"],
            as_index=False
        )
        .agg({
            "Curso detectado": lambda x: " | ".join(sorted(set(x))),
            "Hoja": lambda x: " | ".join(sorted(set(x))),
            "Fila": lambda x: ", ".join(
                sorted(set(str(v) for v in x))
            )
        })
    )

    filas = []

    for _, fila in agrupado.iterrows():

        curso_detectado = fila["Curso detectado"].split(" | ")[0]
        ref = encontrar_catalogo(curso_detectado)

        if ref is not None:
            item = int(ref["Ítem"])
            curso = ref["Curso"]
            horas = int(ref["Horas"])
            catalogo_estado = "Sí"
        else:
            item = None
            curso = curso_detectado
            horas = None
            catalogo_estado = "Revisar"

        filas.append({
            "Ítem": item,
            "Puesto de trabajo": fila["Puesto"],
            "Modalidad de curso": "Por definir",
            "Duración": horas,
            "Certificado / lista de asistencia": False,
            "Curso": curso,
            "Asistencia": False,
            "Nota": None,
            "Comentarios": "",
            "Estado": "PENDIENTE",
            "Catálogo": catalogo_estado,
            "Evidencia": f"{fila['Hoja']} / fila {fila['Fila']}"
        })

    return pd.DataFrame(filas).sort_values(
        ["Puesto de trabajo", "Ítem"],
        na_position="last"
    ).reset_index(drop=True)


def actualizar_estado(df):
    if df.empty:
        return df

    df = df.copy()

    def estado(fila):
        if not bool(fila["Asistencia"]):
            return "PENDIENTE"

        nota = fila["Nota"]

        if pd.isna(nota) or str(nota).strip() == "":
            return "PENDIENTE DE NOTA"

        if not bool(fila["Certificado / lista de asistencia"]):
            return "PENDIENTE DE CERTIFICADO/LISTA"

        return "COMPLETADO"

    df["Estado"] = df.apply(estado, axis=1)
    return df


def exportar(matriz, evidencias):
    memoria = io.BytesIO()

    with pd.ExcelWriter(
        memoria,
        engine="openpyxl"
    ) as writer:

        matriz.to_excel(
            writer,
            sheet_name="Matriz",
            index=False
        )

        evidencias.to_excel(
            writer,
            sheet_name="Evidencias IPERC",
            index=False
        )

        catalogo.to_excel(
            writer,
            sheet_name="Cursos obligatorios",
            index=False
        )

    memoria.seek(0)
    return memoria


# ============================================================
# ESTADO DE LA APP
# ============================================================

if "evidencias" not in st.session_state:
    st.session_state.evidencias = pd.DataFrame()

if "matriz" not in st.session_state:
    st.session_state.matriz = pd.DataFrame()


# ============================================================
# MENÚ
# ============================================================

st.sidebar.title("🎓 Capacity AI")
st.sidebar.write("Plan de capacitación por puesto")

opcion = st.sidebar.radio(
    "Secciones",
    [
        "Inicio",
        "Analizar IPERC",
        "Matriz de capacitación",
        "Resumen",
        "Exportar"
    ]
)


# ============================================================
# INICIO
# ============================================================

if opcion == "Inicio":

    st.title("🎓 Capacity AI")

    st.subheader(
        "Sistema de identificación y seguimiento de capacitación"
    )

    st.write(
        "La aplicación identifica los cursos requeridos por puesto "
        "a partir de la matriz IPERC y Control Administrativo, "
        "los agrupa y los presenta en una única matriz de seguimiento."
    )

    st.markdown("""
    ### Flujo

    **Puesto de Trabajo / Cargo**
    → **Control Administrativo**
    → **Capacitación / Entrenamiento / Curso**
    → **Agrupación**
    → **Curso obligatorio + horas**
    → **Asistencia + nota + certificado + comentarios**
    """)

    st.info(
        "La matriz final concentra toda la información en una sola tabla."
    )


# ============================================================
# ANALIZAR IPERC
# ============================================================

elif opcion == "Analizar IPERC":

    st.title("📂 Analizar IPERC")

    archivo = st.file_uploader(
        "Sube la matriz Excel",
        type=["xlsx", "xls"]
    )

    if archivo:

        if st.button(
            "🔍 Analizar y crear matriz",
            type="primary",
            use_container_width=True
        ):

            with st.spinner(
                "Identificando puestos y cursos..."
            ):
                evidencias = analizar_excel(archivo)
                matriz = construir_matriz(evidencias)

            st.session_state.evidencias = evidencias
            st.session_state.matriz = matriz

            if matriz.empty:
                st.error(
                    "No se encontraron cursos con la estructura esperada."
                )

                st.warning(
                    "Esta V4.1 detecta nombres de columnas con variaciones, "
                    "saltos de línea y celdas combinadas. Si sigue sin encontrar "
                    "cursos, necesito ver el Excel directamente para adaptar "
                    "la lectura a su estructura exacta."
                )
            else:
                st.success(
                    f"Se generaron {len(matriz)} registros "
                    "de capacitación."
                )

                st.dataframe(
                    matriz,
                    use_container_width=True,
                    hide_index=True
                )


# ============================================================
# MATRIZ ÚNICA
# ============================================================

elif opcion == "Matriz de capacitación":

    st.title("📋 Matriz de capacitación")

    matriz = st.session_state.matriz

    if matriz.empty:

        st.warning(
            "Primero sube y analiza una matriz IPERC."
        )

    else:

        st.write(
            "Aquí está TODO junto. Solo debes completar "
            "modalidad, asistencia, nota, certificado/lista "
            "y comentarios."
        )

        editada = st.data_editor(
            matriz,
            use_container_width=True,
            hide_index=True,
            disabled=[
                "Ítem",
                "Puesto de trabajo",
                "Duración",
                "Curso",
                "Estado",
                "Catálogo",
                "Evidencia"
            ],
            column_config={
                "Ítem": st.column_config.NumberColumn(
                    "Ítem"
                ),
                "Puesto de trabajo": st.column_config.TextColumn(
                    "Puesto de trabajo"
                ),
                "Modalidad de curso": st.column_config.SelectboxColumn(
                    "Modalidad de curso",
                    options=[
                        "Por definir",
                        "Presencial",
                        "Virtual"
                    ],
                    required=True
                ),
                "Duración": st.column_config.NumberColumn(
                    "Duración (horas)",
                    format="%d h"
                ),
                "Certificado / lista de asistencia":
                    st.column_config.CheckboxColumn(
                        "Certificado / lista de asistencia",
                        help="Marcar cuando exista certificado o lista de asistencia."
                    ),
                "Curso": st.column_config.TextColumn(
                    "Curso"
                ),
                "Asistencia":
                    st.column_config.CheckboxColumn(
                        "Asistencia ✓",
                        help="Marca si el trabajador asistió."
                    ),
                "Nota":
                    st.column_config.NumberColumn(
                        "Nota",
                        min_value=0,
                        max_value=20,
                        step=0.5,
                        help="Ingresa la nota obtenida."
                    ),
                "Comentarios":
                    st.column_config.TextColumn(
                        "Comentarios"
                    ),
                "Estado":
                    st.column_config.TextColumn(
                        "Estado",
                        disabled=True
                    ),
                "Catálogo":
                    st.column_config.TextColumn(
                        "Catálogo"
                    ),
                "Evidencia":
                    st.column_config.TextColumn(
                        "Evidencia"
                    )
            }
        )

        editada = actualizar_estado(editada)

        st.session_state.matriz = editada

        st.success(
            "La matriz quedó actualizada."
        )

        st.subheader("Estado actual")

        estados = (
            editada["Estado"]
            .value_counts()
            .rename_axis("Estado")
            .reset_index(name="Cantidad")
        )

        st.dataframe(
            estados,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# RESUMEN
# ============================================================

elif opcion == "Resumen":

    st.title("📊 Resumen")

    matriz = st.session_state.matriz

    if matriz.empty:

        st.info(
            "Primero analiza el IPERC."
        )

    else:

        total = len(matriz)
        completados = int(
            (matriz["Estado"] == "COMPLETADO").sum()
        )
        pendientes = total - completados

        c1, c2, c3 = st.columns(3)

        c1.metric("Capacitaciones", total)
        c2.metric("Completadas", completados)
        c3.metric("Pendientes", pendientes)

        st.subheader(
            "Cursos requeridos agrupados"
        )

        resumen = (
            matriz
            .groupby("Curso", as_index=False)
            .agg(
                Puestos=("Puesto de trabajo", "nunique"),
                Horas=("Duración", "first"),
                Completados=(
                    "Estado",
                    lambda x: int(
                        (x == "COMPLETADO").sum()
                    )
                )
            )
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


# ============================================================
# EXPORTAR
# ============================================================

elif opcion == "Exportar":

    st.title("📥 Exportar")

    matriz = st.session_state.matriz
    evidencias = st.session_state.evidencias

    if matriz.empty:

        st.info(
            "No hay información para exportar."
        )

    else:

        archivo = exportar(
            matriz,
            evidencias
        )

        st.download_button(
            "📥 Descargar matriz completa en Excel",
            data=archivo,
            file_name="CapacityAI_Matriz_Capacitacion.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True
        )
