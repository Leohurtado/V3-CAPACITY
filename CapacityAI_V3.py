import io
import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# CAPACITY AI V5
#
# Lee varios tipos de Excel:
#   1) IPERC Línea Base
#   2) Diagnóstico / Anexo 6
#   3) Matriz de entrenamiento / Malla
#   4) HR Connect / Posiciones / personal
#
# Genera UNA sola matriz:
# Ítem | Puesto de trabajo | Modalidad de curso | Duración |
# Certificado / lista de asistencia | Curso | Asistencia | Nota |
# Comentarios
#
# REGLA PRINCIPAL DEL IPERC:
# Puesto de trabajo O Cargo
#        +
# Control Administrativo
#        ->
# Capacitación / Entrenamiento / Curso
#
# No se exige que existan las dos columnas "Puesto" y "Cargo".
# ============================================================

st.set_page_config(
    page_title="Capacity AI",
    page_icon="🎓",
    layout="wide"
)

st.markdown("""
<style>
.stApp { background: #f5f7fb; }
.block-container { padding-top: 1.5rem; }
[data-testid="stSidebar"] { background: #111827; }
[data-testid="stSidebar"] * { color: white !important; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# UTILIDADES
# ============================================================

def norm(value):
    if value is None or pd.isna(value):
        return ""

    text = str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        c for c in text if not unicodedata.combining(c)
    )
    text = text.upper()
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def norm_col(value):
    return re.sub(r"\s+", " ", norm(value).replace("\n", " ")).strip()


def course_key(value):
    text = norm(value)

    replacements = {
        "CAPACITACION EN PRIMEROS AUXILIOS": "PRIMEROS AUXILIOS",
        "ENTRENAMIENTO EN PRIMEROS AUXILIOS": "PRIMEROS AUXILIOS",
        "CURSO DE PRIMEROS AUXILIOS": "PRIMEROS AUXILIOS",
        "EQUIPO DE PROTECCION PERSONAL": "USO DE EQUIPO DE PROTECCION PERSONAL (EPP)",
        "USO CORRECTO DEL EQUIPO DE PROTECCION PERSONAL":
            "USO DE EQUIPO DE PROTECCION PERSONAL (EPP)",
        "USO DE EPP":
            "USO DE EQUIPO DE PROTECCION PERSONAL (EPP)",
        "MANEJO DEFENSIVO Y TRANSPORTE DE PERSONAL":
            "MANEJO DEFENSIVO Y/O TRANSPORTE DE PERSONAL",
    }

    return replacements.get(text, text)


def unique_keep_order(values):
    result = []
    seen = set()

    for value in values:
        key = norm(value)
        if key and key not in seen:
            seen.add(key)
            result.append(str(value).strip())

    return result


# ============================================================
# IDENTIFICACIÓN DE COLUMNAS
# ============================================================

def is_position_col(name):
    c = norm_col(name)

    # UNO u OTRO:
    # "Puesto de trabajo" O "Cargo".
    return c in {
        "PUESTO DE TRABAJO",
        "CARGO",
        "POSICION",
        "POSICIÓN",
    }


def is_control_col(name):
    c = norm_col(name)

    return (
        "CONTROL ADMINISTRATIVO" in c
        or "CONTROLES ADMINISTRATIVOS" in c
    )


def is_course_col(name):
    c = norm_col(name)

    return (
        c == "CURSO"
        or c == "CURSOS"
        or "TEMA DE CAPACITACION" in c
        or "TEMA DE CAPACITACIÓN" in c
    )


# ============================================================
# CLASIFICAR DOCUMENTOS
# ============================================================

def classify_file(file_bytes, filename):
    """
    Clasificación rápida:
    primero usa el nombre y los nombres de hojas.
    Solo inspecciona una pequeña muestra cuando hace falta.
    """
    name = norm(filename)

    if "IPERC" in name:
        return "IPERC"
    if "DIAGNOSTICO" in name or "DIAGNÓSTICO" in name:
        return "DIAGNOSTICO"
    if "MALLA" in name or "BDQ1" in name or "BDQ2" in name:
        return "ENTRENAMIENTO"
    if "HR CONNECT" in name or "POSICIONES" in name:
        return "PERSONAL"

    try:
        xls = pd.ExcelFile(io.BytesIO(file_bytes))
        sheets = [norm(s) for s in xls.sheet_names]
        joined = " ".join(sheets)

        if "IPERC" in joined:
            return "IPERC"
        if "DIAGNOSTICO" in joined or "DIAGNÓSTICO" in joined:
            return "DIAGNOSTICO"
        if "MALLA" in joined or "BDQ1" in joined or "BDQ2" in joined:
            return "ENTRENAMIENTO"
        if "POSICIONES" in joined or "HR CONNECT" in joined:
            return "PERSONAL"

        # Solo si el nombre de hoja no ayuda, mirar una muestra pequeña.
        for sheet in xls.sheet_names[:5]:
            sample = pd.read_excel(
                xls,
                sheet_name=sheet,
                header=None,
                nrows=12
            )

            values = " ".join(
                norm(x)
                for x in sample.astype(object).values.flatten()
                if pd.notna(x)
            )

            if (
                "CONTROL ADMINISTRATIVO" in values
                and (
                    "PUESTO DE TRABAJO" in values
                    or "CARGO" in values
                )
            ):
                return "IPERC"

            if "HORAS MINIMAS" in values or "HORAS MÍNIMAS" in values:
                return "DIAGNOSTICO"

            if (
                "MODALIDAD DE ITEM" in values
                or "MODALIDAD DE ÍTEM" in values
                or "CODIGO ITEM" in values
                or "CÓDIGO ITEM" in values
            ):
                return "ENTRENAMIENTO"

    except Exception:
        pass

    return "OTRO"


# ============================================================
# LECTURA IPERC
# ============================================================

def find_iperc_header(df):
    best = None
    score_best = 0

    for i in range(min(80, len(df))):
        row = [norm_col(x) for x in df.iloc[i].tolist()]

        has_position = any(is_position_col(x) for x in row)
        has_control = any(is_control_col(x) for x in row)

        score = 0

        if has_position:
            score += 10
        if has_control:
            score += 10
        if "PROCESO" in row:
            score += 1
        if "ACTIVIDAD" in row:
            score += 1
        if "TAREA" in row:
            score += 1

        if score > score_best:
            score_best = score
            best = i

    return best


def prepare_header(df, row):
    columns = []
    repeated = {}

    for i, value in enumerate(df.iloc[row].tolist()):
        name = norm_col(value)

        if not name:
            name = f"COLUMNA_{i+1}"

        if name in repeated:
            repeated[name] += 1
            name = f"{name}_{repeated[name]}"
        else:
            repeated[name] = 1

        columns.append(name)

    table = df.iloc[row + 1:].copy()
    table.columns = columns

    return table.dropna(how="all").reset_index(drop=True)


def extract_positions(value):
    text = str(value) if value is not None else ""

    if not text or text == "nan":
        return []

    parts = re.split(r"[\n;]+", text)

    result = []

    for part in parts:
        part = part.strip(" -•*")
        if not part:
            continue

        if norm(part) in {
            "PUESTO DE TRABAJO",
            "CARGO",
            "POSICION",
            "POSICIÓN",
        }:
            continue

        result.append(part)

    return unique_keep_order(result)


def is_training_marker(line):
    c = norm(line)

    patterns = [
        r"^CAPACITACION(?:ES)?$",
        r"^ENTRENAMIENTO(?:S)?$",
        r"^CURSO(?:S)?$",
        r"^CAPACITACION(?:ES)?\s*/\s*ENTRENAMIENTO(?:S)?$",
        r"^ENTRENAMIENTO(?:S)?\s*/\s*CAPACITACION(?:ES)?$",
        r"^CAPACITACION(?:ES)?\s+Y\s+ENTRENAMIENTO(?:S)?$",
        r"^CAPACITACION(?:ES)?\s+E\s+ENTRENAMIENTO(?:S)?$",
    ]

    return any(re.match(p, c) for p in patterns)


def extract_iperc_courses(value):
    if value is None or pd.isna(value):
        return []

    text = str(value).replace("\r", "\n")

    # Formatos del tipo:
    # Capacitación / Entrenamiento: curso
    text = re.sub(
        r"(?i)(CAPACITACION(?:ES)?\s*/\s*ENTRENAMIENTO(?:S)?|"
        r"ENTRENAMIENTO(?:S)?\s*/\s*CAPACITACION(?:ES)?|"
        r"CAPACITACION(?:ES)?|ENTRENAMIENTO(?:S)?|CURSO(?:S)?)\s*:\s*",
        lambda m: m.group(1) + "\n",
        text
    )

    lines = text.split("\n")
    courses = []
    active = False

    for line in lines:
        raw = line.strip()

        if not raw:
            continue

        if is_training_marker(raw):
            active = True
            continue

        upper = norm(raw)

        # Las referencias documentarias NO son cursos.
        if "REFERENCIA DOCUMENTARIA" in upper:
            active = False
            continue

        # Otros controles terminan el bloque.
        if upper in {
            "CONTROL DE INGENIERIA",
            "CONTROLES DE INGENIERIA",
            "ELIMINACION",
            "SUSTITUCION",
            "EPP",
        }:
            active = False
            continue

        if not active:
            continue

        course = raw.strip(" -•*")

        # Ignorar códigos documentarios.
        if re.match(
            r"^(YAN[-\s]|ISO\s*\d|NTP\s*\d|DS\s*\d)",
            course,
            flags=re.I
        ):
            continue

        # Ignorar frases que claramente son instrucciones de control.
        if norm(course).startswith(
            (
                "CONTAR CON ",
                "ESTAR ATENTO",
                "VERIFICAR LA ",
                "RESPETAR LAS ",
                "CUMPLIMIENTO DE ",
                "COORDINAR PREVIAMENTE",
            )
        ):
            continue

        if len(course) >= 3:
            courses.append(course)

    return unique_keep_order(courses)


def read_iperc(file_bytes, filename):
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    results = []

    for sheet in xls.sheet_names:
        df = pd.read_excel(
            io.BytesIO(file_bytes),
            sheet_name=sheet,
            header=None
        )

        header = find_iperc_header(df)

        if header is None:
            continue

        table = prepare_header(df, header)

        position_col = None
        control_col = None

        # UNO de los dos:
        # Puesto de trabajo O Cargo.
        for col in table.columns:
            if position_col is None and is_position_col(col):
                position_col = col

            if control_col is None and is_control_col(col):
                control_col = col

        if position_col is None or control_col is None:
            continue

        for row_number, (_, row) in enumerate(
            table.iterrows(),
            start=header + 2
        ):
            positions = extract_positions(
                row[position_col]
            )

            courses = extract_iperc_courses(
                row[control_col]
            )

            for position in positions:
                for course in courses:
                    results.append({
                        "Puesto": position,
                        "Curso detectado": course,
                        "Curso clave": course_key(course),
                        "Documento": filename,
                        "Hoja": sheet,
                        "Fila": row_number,
                    })

    return pd.DataFrame(results).drop_duplicates()


# ============================================================
# DIAGNÓSTICO / ANEXO 6
# ============================================================

def read_diagnostico(file_bytes, filename):
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    results = []

    for sheet in xls.sheet_names:
        df = pd.read_excel(
            io.BytesIO(file_bytes),
            sheet_name=sheet,
            header=None
        )

        # Buscamos la fila "Tema de Capacitación".
        header_row = None
        for i in range(min(15, len(df))):
            row = [norm_col(x) for x in df.iloc[i].tolist()]
            if any(
                "TEMA DE CAPACITACION" in x
                or "TEMA DE CAPACITACIÓN" in x
                for x in row
            ):
                header_row = i
                break

        if header_row is None:
            continue

        # La fila inmediatamente siguiente contiene Horas mínimas.
        hours_row = header_row + 1

        courses = df.iloc[header_row].tolist()
        hours = (
            df.iloc[hours_row].tolist()
            if hours_row < len(df)
            else []
        )

        for col, course in enumerate(courses):
            if pd.isna(course):
                continue

            course = str(course).strip()

            if norm(course) in {
                "",
                "TEMA DE CAPACITACION",
                "TEMA DE CAPACITACIÓN",
                "N°",
            }:
                continue

            if norm(course) == "HORAS MINIMAS":
                continue

            hour = None

            if col < len(hours):
                try:
                    value = hours[col]
                    if pd.notna(value):
                        hour = float(value)
                except Exception:
                    hour = None

            results.append({
                "Curso": course,
                "Curso clave": course_key(course),
                "Horas": hour,
                "Documento": filename,
                "Hoja": sheet,
            })

    if not results:
        return pd.DataFrame(
            columns=[
                "Curso",
                "Curso clave",
                "Horas",
                "Documento",
                "Hoja",
            ]
        )

    result = pd.DataFrame(results)

    # Conserva la primera definición de cada curso.
    return result.drop_duplicates(
        subset=["Curso clave"],
        keep="first"
    )


# ============================================================
# MALLA / MATRIZ DE ENTRENAMIENTO
# ============================================================

def find_header_with_text(df, required_terms):
    for i in range(min(15, len(df))):
        row = " ".join(
            norm_col(x)
            for x in df.iloc[i].tolist()
            if pd.notna(x)
        )

        if all(term in row for term in required_terms):
            return i

    return None


def read_malla(file_bytes, filename):
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    results = []

    for sheet in xls.sheet_names:
        df_raw = pd.read_excel(
            io.BytesIO(file_bytes),
            sheet_name=sheet,
            header=None
        )

        header = find_header_with_text(
            df_raw,
            ["CURSO", "HORAS ITEM"]
        )

        if header is None:
            continue

        df = pd.read_excel(
            io.BytesIO(file_bytes),
            sheet_name=sheet,
            header=header
        )

        df.columns = [
            norm_col(c)
            for c in df.columns
        ]

        course_col = next(
            (
                c for c in df.columns
                if norm_col(c) == "CURSO"
            ),
            None
        )

        hours_col = next(
            (
                c for c in df.columns
                if "HORAS ITEM" in norm_col(c)
            ),
            None
        )

        modality_col = next(
            (
                c for c in df.columns
                if "MODALIDAD" in norm_col(c)
            ),
            None
        )

        code_col = next(
            (
                c for c in df.columns
                if "CODIGO ITEM" in norm_col(c)
                or "CÓDIGO ITEM" in norm_col(c)
            ),
            None
        )

        if course_col is None:
            continue

        for _, row in df.iterrows():
            course = row[course_col]

            if pd.isna(course):
                continue

            course = str(course).strip()

            if not course:
                continue

            hours = None
            if hours_col:
                try:
                    if pd.notna(row[hours_col]):
                        hours = float(row[hours_col])
                except Exception:
                    pass

            modality = (
                str(row[modality_col]).strip()
                if modality_col and pd.notna(row[modality_col])
                else ""
            )

            code = (
                str(row[code_col]).strip()
                if code_col and pd.notna(row[code_col])
                else ""
            )

            results.append({
                "Curso": course,
                "Curso clave": course_key(course),
                "Horas": hours,
                "Modalidad": modality,
                "Código": code,
                "Documento": filename,
                "Hoja": sheet,
            })

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).drop_duplicates(
        subset=["Curso clave", "Código"],
        keep="first"
    )


# ============================================================
# PERSONAL / POSICIONES
# ============================================================

def read_personal(file_bytes, filename):
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    results = []

    for sheet in xls.sheet_names:
        df = pd.read_excel(
            io.BytesIO(file_bytes),
            sheet_name=sheet,
            header=None,
            nrows=10
        )

        header = find_header_with_text(
            df,
            ["PERSONA"]
        )

        # HR Connect normalmente tiene EMPLEADO y POSICION.
        if header is None:
            for i in range(min(10, len(df))):
                row = [norm_col(x) for x in df.iloc[i].tolist()]
                if (
                    any("EMPLEADO" == x for x in row)
                    and any(
                        x in {"POSICION", "POSICIÓN", "CARGO"}
                        for x in row
                    )
                ):
                    header = i
                    break

        if header is None:
            continue

        full = pd.read_excel(
            io.BytesIO(file_bytes),
            sheet_name=sheet,
            header=header
        )

        full.columns = [
            norm_col(c)
            for c in full.columns
        ]

        employee_col = next(
            (
                c for c in full.columns
                if c in {
                    "EMPLEADO",
                    "PERSONA",
                    "APELLIDOS Y NOMBRES"
                }
            ),
            None
        )

        position_col = next(
            (
                c for c in full.columns
                if c in {
                    "POSICION",
                    "POSICIÓN",
                    "CARGO"
                }
            ),
            None
        )

        if employee_col is None or position_col is None:
            continue

        for _, row in full.iterrows():
            employee = row[employee_col]
            position = row[position_col]

            if pd.isna(employee) or pd.isna(position):
                continue

            results.append({
                "Trabajador": str(employee).strip(),
                "Puesto": str(position).strip(),
                "Documento": filename,
                "Hoja": sheet,
            })

    return pd.DataFrame(results).drop_duplicates()


# ============================================================
# CRUCE CURSO - CATÁLOGO
# ============================================================

def build_course_catalog(diagnostico, malla):
    parts = []

    if not diagnostico.empty:
        d = diagnostico[
            ["Curso", "Curso clave", "Horas"]
        ].copy()
        d["Fuente"] = "Diagnóstico / Anexo 6"
        d["Modalidad"] = ""
        parts.append(d)

    if not malla.empty:
        mm = malla[
            ["Curso", "Curso clave", "Horas", "Modalidad"]
        ].copy()
        mm["Fuente"] = "Malla / Matriz de entrenamiento"
        parts.append(mm)

    if not parts:
        return pd.DataFrame(
            columns=[
                "Curso",
                "Curso clave",
                "Horas",
                "Modalidad",
                "Fuente"
            ]
        )

    catalog = pd.concat(
        parts,
        ignore_index=True
    )

    # Prioridad: Malla si existe modalidad/hora; si no, Diagnóstico.
    catalog["Horas"] = pd.to_numeric(
        catalog["Horas"],
        errors="coerce"
    )

    catalog["Modalidad"] = catalog["Modalidad"].fillna("")

    catalog = (
        catalog
        .sort_values(
            by=["Curso clave", "Horas"],
            na_position="last"
        )
        .drop_duplicates(
            subset=["Curso clave"],
            keep="first"
        )
        .reset_index(drop=True)
    )

    return catalog


def find_course_reference(course, catalog):
    if catalog.empty:
        return None

    key = course_key(course)

    exact = catalog[
        catalog["Curso clave"] == key
    ]

    if not exact.empty:
        return exact.iloc[0]

    # Coincidencia por palabras para pequeñas diferencias de nombre.
    words = [
        w for w in key.split()
        if len(w) >= 5
    ]

    if not words:
        return None

    best = None
    best_score = 0

    for _, row in catalog.iterrows():
        ref = row["Curso clave"]

        score = sum(
            word in ref
            for word in words
        ) / len(words)

        if score > best_score:
            best_score = score
            best = row

    if best is not None and best_score >= 0.70:
        return best

    return None


# ============================================================
# GENERAR UNA SOLA MATRIZ
# ============================================================

def generate_matrix(iperc, catalog):
    if iperc.empty:
        return pd.DataFrame()

    grouped = (
        iperc
        .groupby(
            ["Puesto", "Curso clave"],
            as_index=False
        )
        .agg(
            Curso_detectado=(
                "Curso detectado",
                lambda x: " | ".join(
                    sorted(set(x))
                )
            ),
            Evidencias=("Curso detectado", "count")
        )
    )

    rows = []

    for _, item in grouped.iterrows():

        detected = item["Curso_detectado"].split(" | ")[0]
        reference = find_course_reference(
            detected,
            catalog
        )

        if reference is not None:
            course = reference["Curso"]
            hours = reference["Horas"]
            modality = reference["Modalidad"]

            if pd.isna(hours):
                hours = None

            if not modality:
                modality = "Por definir"

            catalog_status = "Encontrado"
        else:
            course = detected
            hours = None
            modality = "Por definir"
            catalog_status = "Revisar"

        rows.append({
            "Ítem": None,
            "Puesto de trabajo": item["Puesto"],
            "Modalidad de curso": modality,
            "Duración": hours,
            "Certificado / lista de asistencia": False,
            "Curso": course,
            "Asistencia": False,
            "Nota": None,
            "Comentarios": "",
            "Estado": "PENDIENTE",
            "Catálogo": catalog_status,
            "Evidencias IPERC": int(item["Evidencias"]),
        })

    result = pd.DataFrame(rows)

    if result.empty:
        return result

    result = result.sort_values(
        ["Puesto de trabajo", "Curso"]
    ).reset_index(drop=True)

    result["Ítem"] = range(1, len(result) + 1)

    return result


def update_status(df):
    if df.empty:
        return df

    result = df.copy()

    def get_status(row):
        if not bool(row["Asistencia"]):
            return "PENDIENTE"

        note = row["Nota"]

        if pd.isna(note) or str(note).strip() == "":
            return "PENDIENTE DE NOTA"

        if not bool(
            row["Certificado / lista de asistencia"]
        ):
            return "PENDIENTE DE CERTIFICADO/LISTA"

        return "COMPLETADO"

    result["Estado"] = result.apply(
        get_status,
        axis=1
    )

    return result


# ============================================================
# EXPORTACIÓN
# ============================================================

def export_excel(matrix, iperc, catalog, personal):
    memory = io.BytesIO()

    with pd.ExcelWriter(
        memory,
        engine="openpyxl"
    ) as writer:

        matrix.to_excel(
            writer,
            sheet_name="Matriz de capacitación",
            index=False
        )

        iperc.to_excel(
            writer,
            sheet_name="Cursos desde IPERC",
            index=False
        )

        catalog.to_excel(
            writer,
            sheet_name="Catálogo de cursos",
            index=False
        )

        if not personal.empty:
            personal.to_excel(
                writer,
                sheet_name="Personal",
                index=False
            )

    memory.seek(0)
    return memory


# ============================================================
# SESSION STATE
# ============================================================

for key, default in {
    "files_info": pd.DataFrame(),
    "iperc": pd.DataFrame(),
    "diagnostico": pd.DataFrame(),
    "malla": pd.DataFrame(),
    "personal": pd.DataFrame(),
    "catalog": pd.DataFrame(),
    "matrix": pd.DataFrame(),
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🎓 Capacity AI")
st.sidebar.caption(
    "Análisis y planificación de capacitación"
)

page = st.sidebar.radio(
    "Módulos",
    [
        "🏠 Inicio",
        "📂 Documentos",
        "📋 Matriz de capacitación",
        "📊 Resumen",
        "📥 Exportar"
    ]
)


# ============================================================
# INICIO
# ============================================================

if page == "🏠 Inicio":

    st.title("🎓 Capacity AI")
    st.subheader(
        "Sistema inteligente de planificación de capacitación"
    )

    st.write(
        "Carga tus documentos y Capacity AI identifica los puestos, "
        "cursos, horas y modalidades, agrupando la información "
        "en una única matriz de capacitación."
    )

    st.markdown("""
    ### Fuentes que puede leer

    **IPERC Línea Base**
    → puesto/cargo + Control Administrativo + cursos

    **Diagnóstico / Anexo 6**
    → cursos + horas mínimas

    **Malla / Matriz de entrenamiento**
    → cursos + horas + modalidad

    **HR Connect / Posiciones**
    → trabajador + posición
    """)

    st.info(
        "La matriz final permite marcar asistencia, "
        "certificado/lista, registrar nota y comentarios."
    )


# ============================================================
# DOCUMENTOS
# ============================================================

elif page == "📂 Documentos":

    st.title("📂 Documentos")

    uploaded = st.file_uploader(
        "Carga uno o varios archivos Excel",
        type=["xlsx", "xls"],
        accept_multiple_files=True
    )

    if uploaded:

        if st.button(
            "🔍 Analizar documentos",
            type="primary",
            use_container_width=True
        ):

            total_files = len(uploaded)
            progress = st.progress(0)
            status = st.empty()

            iperc_parts = []
            diag_parts = []
            malla_parts = []
            personal_parts = []
            info = []

            # ------------------------------------------------
            # ETAPA 1: identificar archivos
            # ------------------------------------------------
            status.info(
                f"Etapa 1/3 — Identificando {total_files} documento(s)..."
            )

            file_data = []

            for number, uploaded_file in enumerate(uploaded, start=1):
                try:
                    content = uploaded_file.getvalue()

                    if not content:
                        raise ValueError("El archivo está vacío.")

                    doc_type = classify_file(
                        content,
                        uploaded_file.name
                    )

                    file_data.append(
                        (
                            uploaded_file.name,
                            content,
                            doc_type
                        )
                    )

                    info.append({
                        "Documento": uploaded_file.name,
                        "Tipo identificado": doc_type,
                        "Estado": "Listo"
                    })

                except Exception as error:
                    info.append({
                        "Documento": uploaded_file.name,
                        "Tipo identificado": "ERROR",
                        "Estado": str(error)
                    })

                progress.progress(
                    min(number / max(total_files, 1) * 0.20, 0.20)
                )

            # ------------------------------------------------
            # ETAPA 2: leer fuentes
            # ------------------------------------------------
            status.info(
                "Etapa 2/3 — Leyendo IPERC, diagnóstico, "
                "malla y posiciones..."
            )

            valid_files = [
                item for item in file_data
                if item[2] != "OTRO"
            ]

            total_valid = max(len(valid_files), 1)

            for number, (filename, content, doc_type) in enumerate(
                valid_files,
                start=1
            ):

                try:

                    status.info(
                        f"Etapa 2/3 — {number}/{len(valid_files)}: "
                        f"{filename} → {doc_type}"
                    )

                    if doc_type == "IPERC":
                        result = read_iperc(
                            content,
                            filename
                        )

                        if not result.empty:
                            iperc_parts.append(result)

                    elif doc_type == "DIAGNOSTICO":
                        result = read_diagnostico(
                            content,
                            filename
                        )

                        if not result.empty:
                            diag_parts.append(result)

                    elif doc_type == "ENTRENAMIENTO":
                        result = read_malla(
                            content,
                            filename
                        )

                        if not result.empty:
                            malla_parts.append(result)

                    elif doc_type == "PERSONAL":
                        result = read_personal(
                            content,
                            filename
                        )

                        if not result.empty:
                            personal_parts.append(result)

                    # Si un archivo falla, los demás siguen.
                    for item in info:
                        if item["Documento"] == filename:
                            item["Estado"] = "Procesado"

                except Exception as error:

                    for item in info:
                        if item["Documento"] == filename:
                            item["Estado"] = (
                                "Error: " + str(error)
                            )

                progress.progress(
                    0.20 +
                    (number / total_valid) * 0.60
                )

            # ------------------------------------------------
            # Consolidar
            # ------------------------------------------------
            st.session_state.files_info = pd.DataFrame(info)

            st.session_state.iperc = (
                pd.concat(
                    iperc_parts,
                    ignore_index=True
                )
                if iperc_parts
                else pd.DataFrame()
            )

            st.session_state.diagnostico = (
                pd.concat(
                    diag_parts,
                    ignore_index=True
                )
                if diag_parts
                else pd.DataFrame()
            )

            st.session_state.malla = (
                pd.concat(
                    malla_parts,
                    ignore_index=True
                )
                if malla_parts
                else pd.DataFrame()
            )

            st.session_state.personal = (
                pd.concat(
                    personal_parts,
                    ignore_index=True
                )
                if personal_parts
                else pd.DataFrame()
            )

            # ------------------------------------------------
            # ETAPA 3: cruzar y construir matriz
            # ------------------------------------------------
            status.info(
                "Etapa 3/3 — Agrupando cursos y construyendo la matriz..."
            )

            catalog = build_course_catalog(
                st.session_state.diagnostico,
                st.session_state.malla
            )

            st.session_state.catalog = catalog

            matrix = generate_matrix(
                st.session_state.iperc,
                catalog
            )

            st.session_state.matrix = matrix

            progress.progress(1.0)
            status.success(
                "✅ Análisis terminado. Ya puedes abrir "
                "Matriz de capacitación y Resumen."
            )

        if not st.session_state.files_info.empty:

            st.subheader("📄 Documentos identificados")

            st.dataframe(
                st.session_state.files_info,
                use_container_width=True,
                hide_index=True
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Cursos desde IPERC",
                len(st.session_state.iperc)
            )

            c2.metric(
                "Cursos catálogo",
                len(st.session_state.catalog)
            )

            c3.metric(
                "Puestos",
                (
                    st.session_state.matrix[
                        "Puesto de trabajo"
                    ].nunique()
                    if not st.session_state.matrix.empty
                    else 0
                )
            )

            c4.metric(
                "Registros matriz",
                len(st.session_state.matrix)
            )

            if not st.session_state.matrix.empty:

                st.subheader("📋 Vista previa de la matriz")

                st.dataframe(
                    st.session_state.matrix,
                    use_container_width=True,
                    hide_index=True
                )

            elif not st.session_state.iperc.empty:

                st.warning(
                    "Se leyó el IPERC, pero todavía no se pudo "
                    "relacionar algún curso con el catálogo. "
                    "La información detectada se conserva para revisión."
                )

                st.dataframe(
                    st.session_state.iperc,
                    use_container_width=True,
                    hide_index=True
                )

            elif st.session_state.files_info.empty is False:

                st.warning(
                    "Los documentos fueron cargados, pero no se "
                    "detectó una estructura IPERC compatible."
                )



# ============================================================
# MATRIZ
# ============================================================

elif page == "📋 Matriz de capacitación":

    st.title("📋 Matriz de capacitación")

    matrix = st.session_state.matrix

    if matrix.empty:

        st.warning(
            "Primero carga y analiza los documentos."
        )

    else:

        st.write(
            "Todo está concentrado en una sola matriz. "
            "Los campos de seguimiento se pueden marcar directamente."
        )

        edited = st.data_editor(
            matrix,
            use_container_width=True,
            hide_index=True,
            disabled=[
                "Ítem",
                "Puesto de trabajo",
                "Duración",
                "Curso",
                "Estado",
                "Catálogo",
                "Evidencias IPERC",
            ],
            column_config={
                "Ítem": st.column_config.NumberColumn(
                    "Ítem"
                ),
                "Puesto de trabajo": st.column_config.TextColumn(
                    "Puesto de trabajo"
                ),
                "Modalidad de curso":
                    st.column_config.SelectboxColumn(
                        "Modalidad de curso",
                        options=[
                            "Por definir",
                            "Presencial",
                            "Virtual",
                            "Híbrido",
                            "Online"
                        ],
                        required=True
                    ),
                "Duración":
                    st.column_config.NumberColumn(
                        "Duración (horas)",
                        format="%g h"
                    ),
                "Certificado / lista de asistencia":
                    st.column_config.CheckboxColumn(
                        "Certificado / lista de asistencia ✓"
                    ),
                "Curso":
                    st.column_config.TextColumn(
                        "Curso"
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
                        "Comentarios"
                    ),
                "Estado":
                    st.column_config.TextColumn(
                        "Estado",
                        disabled=True
                    ),
                "Catálogo":
                    st.column_config.TextColumn(
                        "Catálogo",
                        disabled=True
                    ),
                "Evidencias IPERC":
                    st.column_config.NumberColumn(
                        "Evidencias IPERC",
                        disabled=True
                    ),
            }
        )

        edited = update_status(edited)

        st.session_state.matrix = edited

        st.success(
            "Matriz actualizada."
        )


# ============================================================
# RESUMEN
# ============================================================

elif page == "📊 Resumen":

    st.title("📊 Resumen")

    matrix = st.session_state.matrix

    if matrix.empty:

        st.info(
            "No hay una matriz generada todavía."
        )

    else:

        total = len(matrix)
        completed = int(
            (matrix["Estado"] == "COMPLETADO").sum()
        )
        pending = total - completed

        a, b, c = st.columns(3)

        a.metric("Capacitaciones", total)
        b.metric("Completadas", completed)
        c.metric("Pendientes", pending)

        st.subheader(
            "Cursos agrupados"
        )

        summary = (
            matrix
            .groupby("Curso", as_index=False)
            .agg(
                Puestos=(
                    "Puesto de trabajo",
                    "nunique"
                ),
                Duración=(
                    "Duración",
                    "first"
                ),
                Completadas=(
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
            summary,
            use_container_width=True,
            hide_index=True
        )

        st.subheader(
            "Puestos y cursos"
        )

        by_position = (
            matrix
            .groupby("Puesto de trabajo", as_index=False)
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
        )

        st.dataframe(
            by_position,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# EXPORTAR
# ============================================================

elif page == "📥 Exportar":

    st.title("📥 Exportar")

    matrix = st.session_state.matrix

    if matrix.empty:

        st.info(
            "No hay datos para exportar."
        )

    else:

        file = export_excel(
            matrix,
            st.session_state.iperc,
            st.session_state.catalog,
            st.session_state.personal
        )

        st.download_button(
            "📥 Descargar matriz completa",
            data=file,
            file_name="CapacityAI_Matriz_Capacitacion.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True
        )
