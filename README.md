
#  Mapeo Curricular con IA (BETO NLP)

Una aplicación web desarrollada en **Flask** que automatiza el análisis de syllabus universitarios (PDFs). Extrae los Resultados de Aprendizaje (RAs) y utiliza un modelo de Procesamiento de Lenguaje Natural (NLP) basado en **BETO fine-tuneado** para inferir conexiones semánticas entre asignaturas, generando grafos interactivos de la malla curricular.

## Características Principales

* **Extracción Automática:** Lectura de PDFs para identificar Códigos, Prerrequisitos y Resultados de Aprendizaje.
* **Inferencia Semántica:** Cruza los RAs usando un modelo de lenguaje (Transformer) para evaluar el % de similitud y dependencia.
* **Grafos Interactivos (PyVis):** Visualización Macro (ramos) y Micro (ramos + RAs) con buscador integrado y leyendas de color.
* **Exportación/Importación en Excel:** Genera reportes detallados y dashboards estadísticos, permitiendo recargar el estado del análisis desde el archivo Excel.

---

## Requisitos Previos

* [Python 3.14 o superior](https://www.python.org/downloads/)
* Git (Opcional, para clonar el repositorio)

---

## Instalación y Configuración

**1. Clonar el repositorio**
```bash
git clone [https://github.com/TU_USUARIO/TU_REPOSITORIO.git](https://github.com/TU_USUARIO/TU_REPOSITORIO.git)
cd TU_REPOSITORIO

```

**2. Crear y activar un entorno virtual (Recomendado)**
En windows:
```bash
python -m venv venv
venv\Scripts\activate

```


En Linux/MacOS:
```bash
python3 -m venv venv
source venv/bin/activate

```

**3. Instalar las dependencias**

```bash
pip install -r requirements.txt

```

**4. IMPORTANTE: Descargar el modelo NLP**
Debido a restricciones de tamaño (aprox. 6.5 GB), el modelo de Inteligencia Artificial no está incluido en este repositorio.

1. Descarga el modelo desde [INSERTA_TU_LINK_DE_DRIVE_O_HUGGINGFACE_AQUÍ].
2. Descomprime la carpeta y asegúrate de que se llame exactamente `resultados_beto_finetuned_negative`.
3. Colócala en la raíz del proyecto (al mismo nivel que `app.py`).

Tu estructura de carpetas debería verse así:

```text
tu-proyecto/
 ├── app.py
 ├── requirements.txt
 ├── templates/           # Archivos HTML (index, dashboard, etc.)
 ├── resultados_beto_finetuned_negative/  <-- EL MODELO DESCARGADO
 └── uploads/             # (Se generará sola) PDFs y Excels

```

---

## Uso de la Aplicación

**1. Iniciar el servidor**
Asegúrate de tener el entorno virtual activado y ejecuta:

```bash
python app.py

```

**2. Abrir en el navegador**
El servidor iniciará en el puerto 5000. Abre tu navegador web y entra a:
`http://localhost:5000` o `http://127.0.0.1:5000`



---

## Tecnologías Utilizadas

* **Backend:** Python, Flask
* **IA & NLP:** PyTorch, Transformers (Hugging Face)
* **Procesamiento de Datos:** Pandas, PyMuPDF (fitz)
* **Visualización:** PyVis (Vis.js), HTML/JS/CSS

