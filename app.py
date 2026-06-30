from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import re
import threading
import fitz  # PyMuPDF
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from pyvis.network import Network
import uuid
from datetime import datetime
import pandas as pd  # Importado para la generación del reporte Excel
import textwrap
import json
import hashlib
app = Flask(__name__)
CORS(app)

# Configuración básica (Se usan las carpetas por defecto)
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
GRAPHS_FOLDER = os.path.join(os.getcwd(), 'static', 'graphs')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GRAPHS_FOLDER, exist_ok=True)

# Variables globales
malla_curricular = {}
enlaces_semanticos = []
modelo_nlp = None
tokenizer = None
proceso_activo = False
estado_general = {"mensaje": "Inicializando...", "porcentaje": 0, "estado": "iniciando"}

def cargar_modelo():
    """Carga el modelo BETO fine-tuneado en un thread separado"""
    global modelo_nlp, tokenizer
    try:
        print("Cargando modelo BETO Fine-tuneado...")
        estado_general["mensaje"] = "Cargando modelo BETO..."
        ruta_modelo = "./resultados_beto_finetuned_negative"
        tokenizer = AutoTokenizer.from_pretrained(ruta_modelo)
        modelo_nlp = AutoModelForSequenceClassification.from_pretrained(ruta_modelo)
        modelo_nlp.eval()
        print("¡Modelo cargado correctamente!")
        estado_general["mensaje"] = "Modelo listo"
        estado_general["estado"] = "listo"
    except Exception as e:
        print(f"Error cargando modelo: {e}")
        estado_general["mensaje"] = f"Error: {str(e)}"
        estado_general["estado"] = "error"

# Iniciar carga al arrancar
threading.Thread(target=cargar_modelo, daemon=True).start()
def inyectar_buscador_grafo(ruta_html):
    """Inyecta el buscador con flechas coloreadas por dirección."""
    with open(ruta_html, "r", encoding="utf-8") as f:
        html_content = f.read()

    js_codigo = """
    (function() {
        // ── Panel de búsqueda ──────────────────────────────────────────────────
        var panelBusqueda =
            '<div id="panelBuscador" style="position:fixed;top:20px;left:20px;z-index:9999;' +
            'background:rgba(20,20,20,0.97);padding:15px;border-radius:10px;border:1px solid #555;' +
            'color:white;font-family:sans-serif;box-shadow:0 6px 18px rgba(0,0,0,0.5);width:290px;">' +
                '<b style="font-size:14px;margin-bottom:10px;display:block;">Buscador de Ramo / RA</b>' +
                '<input type="text" id="buscadorNodos" placeholder="Ej: ING 1201 o nombre RA" ' +
                    'style="width:100%;box-sizing:border-box;padding:8px;margin-bottom:8px;' +
                    'background:#222;color:white;border:1px solid #555;border-radius:4px;">' +
                '<div style="display:flex;justify-content:space-between;align-items:center;' +
                    'margin-bottom:8px;background:#222;padding:5px 8px;border-radius:4px;">' +
                    '<button id="btnPrev" style="background:#444;color:white;border:none;cursor:pointer;' +
                        'padding:4px 10px;border-radius:3px;">◀</button>' +
                    '<span id="matchCount" style="font-size:12px;color:#aaa;">0 / 0</span>' +
                    '<button id="btnNext" style="background:#444;color:white;border:none;cursor:pointer;' +
                        'padding:4px 10px;border-radius:3px;">▶</button>' +
                '</div>' +
                '<div style="display:flex;gap:8px;margin-bottom:10px;">' +
                    '<button id="btnBuscar" style="flex:1;padding:8px;background:#3498db;color:white;' +
                        'border:none;cursor:pointer;border-radius:4px;">Buscar</button>' +
                    '<button id="btnReset" style="flex:1;padding:8px;background:#e74c3c;color:white;' +
                        'border:none;cursor:pointer;border-radius:4px;">Limpiar</button>' +
                '</div>' +
                '<!-- Leyenda de colores de flechas -->' +
                '<div style="border-top:1px solid #444;padding-top:8px;font-size:11px;line-height:1.8;">' +
                    '<b style="color:#aaa;">Leyenda de flechas:</b><br>' +
                    '<span style="color:#2ecc71;">━━▶</span>  Entran al nodo <span style="color:#888;">(prerrequisitos)</span><br>' +
                    '<span style="color:#e74c3c;">━━▶</span>  Salen del nodo <span style="color:#888;">(ramos que lo usan)</span><br>' +
                    '<span style="color:#95a5a6;">━━▶</span>  Interna del ramo <span style="color:#888;">(mismo ramo)</span>' +
                '</div>' +
            '</div>';

        document.body.insertAdjacentHTML('afterbegin', panelBusqueda);

        setTimeout(function() {
            if (typeof network === 'undefined') return;

            var originalNodeColors = {};
            var originalEdgeColors = {};
            var originalEdgeWidths  = {};
            var currentMatches = [];
            var currentIndex  = 0;

            // Capturamos estado inicial (con un pequeño delay extra por si el layout aún anima)
            function capturarEstadoInicial() {
                nodes.get().forEach(function(n) {
                    originalNodeColors[n.id] = (n.color && typeof n.color === 'object')
                        ? n.color
                        : (n.color || "#3498db");
                });
                edges.get().forEach(function(e) {
                    originalEdgeColors[e.id] = e.color || "#aaaaaa";
                    originalEdgeWidths[e.id] = e.width || 1;
                });
            }
            capturarEstadoInicial();
            setTimeout(capturarEstadoInicial, 600);

            // ── Función principal
            function enfocarActual() {
                if (currentMatches.length === 0) return;
                var selectedId = currentMatches[currentIndex].id;
                var baseRamoId = String(selectedId).split("_")[0];

                // Reset visual (todo apagado)
                nodes.update(nodes.get().map(function(n) {
                    return { id: n.id, color: "rgba(80,80,80,0.15)", opacity: 0.08 };
                }));
                edges.update(edges.get().map(function(e) {
                    return { id: e.id, color: "rgba(100,100,100,0.04)", width: 1 };
                }));

                // ── Conexiones a 2 saltos
                // Salto 0: todos los nodos RA del ramo seleccionado
                var ramoNodes = nodes.get().filter(function(n) {
                    return n.id === selectedId || String(n.id).startsWith(baseRamoId + "_");
                }).map(function(n) { return n.id; });

                var edgesIn       = new Set(); // flechas que llegan al grupo del ramo
                var edgesOut      = new Set(); // flechas que salen del grupo del ramo
                var edgesInternal = new Set(); // flechas internas ramo→RA (estructurales)
                var visibleNodes  = new Set(ramoNodes);
                var hop1Neighbors = new Set(); // vecinos directos (salto 1)

                function procesarEdge(edgeId, esSegundoSalto) {
                    var edge = edges.get(edgeId);
                    if (!edge) return;
                    var fromBase = String(edge.from).split("_")[0];
                    var toBase   = String(edge.to).split("_")[0];

                    // Interna: ramo→su RA propio
                    if (fromBase === toBase && fromBase === baseRamoId) {
                        edgesInternal.add(edgeId);
                        visibleNodes.add(edge.from);
                        visibleNodes.add(edge.to);
                        return;
                    }

                    // Entra al grupo del ramo base
                    if (toBase === baseRamoId) {
                        edgesIn.add(edgeId);
                        visibleNodes.add(edge.from);
                        visibleNodes.add(String(edge.from).split("_")[0]);
                        if (!esSegundoSalto) hop1Neighbors.add(edge.from);
                        return;
                    }

                    // Sale del grupo del ramo base
                    if (fromBase === baseRamoId) {
                        edgesOut.add(edgeId);
                        visibleNodes.add(edge.to);
                        visibleNodes.add(String(edge.to).split("_")[0]);
                        if (!esSegundoSalto) hop1Neighbors.add(edge.to);
                    }
                }

                // Salto 1: edges directos del grupo del ramo
                ramoNodes.forEach(function(nodeId) {
                    network.getConnectedEdges(nodeId).forEach(function(edgeId) {
                        procesarEdge(edgeId, false);
                    });
                });

                // Salto 2: edges de los vecinos del salto 1
                // Solo mostramos las flechas entre vecinos (no arrastramos más nodos nuevos al visibleNodes)
                hop1Neighbors.forEach(function(neighborId) {
                    network.getConnectedEdges(neighborId).forEach(function(edgeId) {
                        var edge = edges.get(edgeId);
                        if (!edge) return;
                        // Solo si ambos extremos ya son visibles (conexión entre vecinos conocidos)
                        if (visibleNodes.has(edge.from) && visibleNodes.has(edge.to)) {
                            var fromBase = String(edge.from).split("_")[0];
                            var toBase   = String(edge.to).split("_")[0];
                            if (fromBase === toBase) {
                                edgesInternal.add(edgeId);
                            } else if (toBase === baseRamoId) {
                                edgesIn.add(edgeId);
                            } else if (fromBase === baseRamoId) {
                                edgesOut.add(edgeId);
                            } else {
                                // Flecha entre dos vecinos del ramo → la mostramos en gris tenue
                                edgesInternal.add(edgeId);
                            }
                        }
                    });
                });

                // ── Actualizar nodos
                nodes.update(nodes.get().map(function(n) {
                    if (!visibleNodes.has(n.id)) {
                        return { id: n.id, color: "rgba(80,80,80,0.12)", opacity: 0.06 };
                    }
                    var isSelected    = (n.id === selectedId);
                    var belongsToBase = (n.id === selectedId || String(n.id).startsWith(baseRamoId + "_") || n.id === baseRamoId);

                    if (isSelected) {
                        // Nodo buscado: su color original con borde blanco para destacar
                        return { id: n.id, color: originalNodeColors[n.id], opacity: 1 };
                    }
                    if (belongsToBase) {
                        // Hermanos RA del mismo ramo - naranjo suave
                        return { id: n.id, color: { background: "#e67e22", border: "#d35400" }, opacity: 1 };
                    }
                    // Nodos vecinos (prerrequisitos o dependientes): su color original
                    return { id: n.id, color: originalNodeColors[n.id], opacity: 0.9 };
                }));

                // ── Actualizar flechas con colores por dirección
                edges.update(edges.get().map(function(e) {
                    if (edgesInternal.has(e.id)) {
                        return { id: e.id, color: "#95a5a6", width: 2 }; // gris → estructural
                    }
                    if (edgesIn.has(e.id)) {
                        return { id: e.id, color: "#2ecc71", width: 4 }; // verde → entran
                    }
                    if (edgesOut.has(e.id)) {
                        return { id: e.id, color: "#e74c3c", width: 4 }; // rojo → salen
                    }
                    return { id: e.id, color: "rgba(100,100,100,0.04)", width: 1 };
                }));

                network.focus(selectedId, { scale: 0.9, animation: { duration: 500 } });
                network.selectNodes([selectedId]);
                document.getElementById("matchCount").innerText =
                    (currentIndex + 1) + " / " + currentMatches.length;
            }

            // ── Botones
            document.getElementById("btnBuscar").onclick = function() {
                var term = document.getElementById("buscadorNodos").value.toLowerCase().trim();
                if (!term) return;
                currentMatches = nodes.get().filter(function(n) {
                    return (n.id   && String(n.id).toLowerCase().includes(term)) ||
                           (n.label && String(n.label).toLowerCase().includes(term));
                });
                if (currentMatches.length > 0) { currentIndex = 0; enfocarActual(); }
                else { document.getElementById("matchCount").innerText = "Sin resultados"; }
            };

            document.getElementById("buscadorNodos").addEventListener("keydown", function(e) {
                if (e.key === "Enter") document.getElementById("btnBuscar").click();
            });

            document.getElementById("btnNext").onclick = function() {
                if (currentMatches.length) {
                    currentIndex = (currentIndex + 1) % currentMatches.length;
                    enfocarActual();
                }
            };
            document.getElementById("btnPrev").onclick = function() {
                if (currentMatches.length) {
                    currentIndex = (currentIndex - 1 + currentMatches.length) % currentMatches.length;
                    enfocarActual();
                }
            };

            document.getElementById("btnReset").onclick = function() {
                nodes.update(nodes.get().map(function(n) {
                    return { id: n.id, color: originalNodeColors[n.id], opacity: 1 };
                }));
                edges.update(edges.get().map(function(e) {
                    return { id: e.id, color: originalEdgeColors[e.id], width: originalEdgeWidths[e.id] };
                }));
                network.unselectAll();
                network.fit();
                currentMatches = [];
                currentIndex   = 0;
                document.getElementById("matchCount").innerText = "0 / 0";
                document.getElementById("buscadorNodos").value  = "";
            };

            // ── Foco por id exacto (usado por enfocarPorId y por postMessage) ──
            function enfocarPorId(nodeId) {
                var encontrado = nodes.get(nodeId);
                if (!encontrado) return false;
                currentMatches = [encontrado];
                currentIndex = 0;
                enfocarActual();
                return true;
            }

            // ── Destacar un enlace semántico específico: nodo origen, nodo  ──
            // ── destino y la arista entre ambos, atenuando todo lo demás.   ──
            function enfocarEnlace(nodoOrigenId, nodoDestinoId) {
                var origenExiste  = !!nodes.get(nodoOrigenId);
                var destinoExiste = !!nodes.get(nodoDestinoId);
                if (!origenExiste || !destinoExiste) return false;

                // Apagar todo
                nodes.update(nodes.get().map(function(n) {
                    return { id: n.id, color: "rgba(80,80,80,0.12)", opacity: 0.06 };
                }));
                edges.update(edges.get().map(function(e) {
                    return { id: e.id, color: "rgba(100,100,100,0.04)", width: 1 };
                }));

                // Encender origen y destino
                nodes.update([
                    { id: nodoOrigenId,  color: { background: "#2ecc71", border: "#1e8449" }, opacity: 1 },
                    { id: nodoDestinoId, color: { background: "#e74c3c", border: "#922b21" }, opacity: 1 }
                ]);

                // Buscar y encender la(s) arista(s) entre ambos nodos
                var edgesEntreAmbos = edges.get().filter(function(e) {
                    return (e.from === nodoOrigenId && e.to === nodoDestinoId) ||
                           (e.from === nodoDestinoId && e.to === nodoOrigenId);
                });
                edgesEntreAmbos.forEach(function(e) {
                    edges.update({ id: e.id, color: "#f1c40f", width: 5 });
                });

                network.fit({ nodes: [nodoOrigenId, nodoDestinoId], animation: { duration: 500 } });
                network.selectNodes([nodoOrigenId, nodoDestinoId]);
                document.getElementById("matchCount").innerText = "Enlace destacado";
                return true;
            }

            // ── Click directo dentro del grafo: nodo o arista
            network.on("click", function(params) {
                // Click sobre una arista (link entre dos RAs)
                if (params.edges.length > 0 && params.nodes.length === 0) {
                    var edgeId = params.edges[0];
                    var edge = edges.get(edgeId);
                    if (edge) {
                        enfocarEnlace(edge.from, edge.to);
                        // Avisamos al padre para que muestre el resumen en la tabla/panel
                        try {
                            window.parent.postMessage({
                                event: "edgeClicked",
                                fromId: String(edge.from),
                                toId: String(edge.to),
                                title: edge.title || ""
                            }, "*");
                        } catch(e) {}
                    }
                    return;
                }
                // Click sobre un nodo (ramo o RA)
                if (params.nodes.length > 0) {
                    var nodeId = params.nodes[0];
                    enfocarPorId(nodeId);
                    try {
                        window.parent.postMessage({
                            event: "nodeClicked",
                            nodeId: String(nodeId)
                        }, "*");
                    } catch(e) {}
                }
            });

            // ── Comunicación con la ventana padre (botones fuera del iframe) ──
            window.addEventListener("message", function(event) {
                var msg = event.data;
                if (!msg || typeof msg !== "object") return;

                if (msg.action === "focusNode" && msg.nodeId) {
                    enfocarPorId(msg.nodeId);
                } else if (msg.action === "focusEdge" && msg.fromId && msg.toId) {
                    enfocarEnlace(msg.fromId, msg.toId);
                } else if (msg.action === "resetGrafo") {
                    document.getElementById("btnReset").click();
                }
            });

            // Avisamos al padre que el grafo ya está listo para recibir comandos
            try { window.parent.postMessage({ event: "grafoListo" }, "*"); } catch(e) {}

        }, 1000);
    })();
    """

    script_tag = f"<script>{js_codigo}</script>"
    html_content = html_content.replace("</body>", script_tag + "</body>")

    with open(ruta_html, "w", encoding="utf-8") as f:
        f.write(html_content)

def normalizar_codigo(codigo):
    """Normaliza códigos de ramo"""
    return re.sub(r'[-\s]+', ' ', codigo).strip().upper()

def nodo_ra_id_de(codigo, texto_ra):
    """
    Genera un id único y determinístico para un nodo RA en el grafo micro.
    Antes se usaba f"{codigo}_{texto[:15]}", lo que causaba colisiones
    (y pérdida silenciosa de nodos) cuando dos RAs del mismo ramo
    compartían los primeros 15 caracteres. Usamos un hash del texto
    completo para garantizar unicidad, manteniendo la misma firma
    (codigo, texto) en todos los lugares donde se construye este id.
    """
    hash_corto = hashlib.md5((texto_ra or "").encode("utf-8")).hexdigest()[:10]
    return f"{codigo}_{hash_corto}"

def extraer_datos_syllabus(ruta_pdf):
    """Extrae datos de un syllabus en PDF de manera robusta y estructurada"""
    try:
        documento = fitz.open(ruta_pdf)
        texto_completo = "".join([p.get_text() for p in documento])
        documento.close()

        codigo_match = re.search(r"Código:\s*([A-Za-z]{3}[-\s]*\d{4})", texto_completo, re.IGNORECASE)
        if not codigo_match:
            return None

        codigo_bruto = codigo_match.group(1)
        codigo_ramo = normalizar_codigo(codigo_bruto)

        # Extraer el prefijo (ej: "ING")
        letras_codigo = re.search(r'[A-Za-z]+', codigo_bruto)
        prefijo = letras_codigo.group(0).upper() if letras_codigo else ""

        nombre_ramo = "Ramo Desconocido"
        
        # --- NUEVA LÓGICA DE EXTRACCIÓN POR LÍNEAS ---
        # Buscamos exactamente el código sin prefijos opcionales (ej: "ING 1105")
        patron_busqueda = rf"{re.escape(codigo_bruto)}"
        match_pos = re.search(patron_busqueda, texto_completo[:1000], re.IGNORECASE)
        
        if match_pos:
            # Tomamos todo lo que está antes de "ING 1105"
            texto_antes = texto_completo[:match_pos.start()].strip()
            
            # Eliminamos guiones sueltos o espacios justo antes del código (ej: "QUIMICA - " -> "QUIMICA")
            texto_antes = re.sub(r'[-\s]+$', '', texto_antes)
            
            # Separamos el texto por líneas y eliminamos las que estén vacías
            lineas = [l.strip() for l in texto_antes.split('\n') if l.strip()]
            
            # Limpiamos la "basura" común de los membretes
            basura = ["UNIVERSIDAD", "DE LOS", "ANDES", "CHILE", "CHILB", "SANDES", "FACULTAD DE INGENIERÍA", "SYLLABUS"]
            lineas_limpias = [l for l in lineas if l.upper() not in basura]
            
            if lineas_limpias:
                # Si el título estaba en 2 líneas y la segunda línea es EXACTAMENTE el prefijo (ej: "ING"),
                # significa que era el prefijo aislado de la carrera (ING-ING 4140) y lo descartamos.
                if len(lineas_limpias) > 1 and lineas_limpias[-1].upper() == prefijo:
                    lineas_limpias.pop()
                
                # Unir líneas si el título legítimo fue cortado a la mitad por el PDF
                if len(lineas_limpias) > 1 and (len(lineas_limpias[-1]) < 15 or lineas_limpias[-2].strip().lower().endswith((' de', ' la', ' el', ' a', ' en', ' e', ' y', ' o', ' del'))):
                    nombre_ramo = f"{lineas_limpias[-2]} {lineas_limpias[-1]}"
                else:
                    nombre_ramo = lineas_limpias[-1]
                
                # Formatear como Título (ej: Taller De Proyectos De Ing)
                nombre_ramo = nombre_ramo.title()
        # ---------------------------------------------

        prereqs_match = re.search(r"Requisitos.*?:\s*(.*?)(?=\n[A-Z][a-z]+|\n\d|\Z)", texto_completo[:3000], re.DOTALL | re.IGNORECASE)
        lista_prereqs = []
        if prereqs_match:
            codigos_encontrados = re.findall(r"\(([A-Za-z]{3}[-\s]*\d{4})\)", prereqs_match.group(1))
            lista_prereqs = [normalizar_codigo(c) for c in codigos_encontrados]

        texto_min = texto_completo.lower()
        indice = texto_min.find("resultados de aprendizaje")
        if indice == -1:
            indice = texto_min.find("objetivos de aprendizaje")

        resultados = []
        if indice != -1:
            texto_seccion = texto_completo[indice:indice+8000]
            idx_corte = texto_seccion.lower().find("descripción de contenidos por unidad")
            if idx_corte != -1:
                texto_seccion = texto_seccion[:idx_corte]
            texto_seccion = re.sub(r"(?i)(?:page|p[áa]gina)\s+\d+\s+(?:of|de)\s+\d+", "", texto_seccion)

            coincidencias = re.findall(r"\b((?:RA|OA|R)\s*\d+)\b(.*?)(?=\b(?:RA|OA|R)\s*\d+\b|$)", texto_seccion, re.IGNORECASE | re.DOTALL)

            for id_item, descripcion in coincidencias:
                desc_limpia = re.sub(r'\s+', ' ', descripcion).strip()
                if len(desc_limpia) > 10:
                    resultados.append((id_item.strip().upper(), desc_limpia[:597]))

        return {"codigo": codigo_ramo, "nombre": nombre_ramo, "prereqs": lista_prereqs, "resultados": resultados}
    except Exception as e:
        print(f"Error extrayendo datos: {e}")
        return None

# ==================== RUTAS API ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/estado', methods=['GET'])
def get_estado():
    return jsonify({
        "mensaje": estado_general["mensaje"],
        "porcentaje": estado_general["porcentaje"],
        "estado": estado_general["estado"],
        "malla_size": len(malla_curricular),
        "enlaces_size": len(enlaces_semanticos)
    })

@app.route('/api/procesar-carpeta', methods=['POST'])
def procesar_carpeta():
    global malla_curricular, proceso_activo
    if proceso_activo:
        return jsonify({"error": "Ya hay un proceso en ejecución"}), 400

    data = request.json
    carpeta = data.get('carpeta', '')
    if not os.path.isdir(carpeta):
        return jsonify({"error": "Carpeta no válida"}), 400

    def procesar_bg():
        global proceso_activo
        proceso_activo = True
        try:
            malla_curricular.clear()
            estado_general["estado"] = "procesando"
            archivos_pdf = [f for f in os.listdir(carpeta) if f.lower().endswith(".pdf")]
            total = len(archivos_pdf)

            for i, archivo in enumerate(archivos_pdf):
                estado_general["mensaje"] = f"Analizando ({i+1}/{total}): {archivo}"
                estado_general["porcentaje"] = int((i / total) * 100) if total > 0 else 0

                ruta = os.path.join(carpeta, archivo)
                datos = extraer_datos_syllabus(ruta)
                if datos:
                    malla_curricular[datos["codigo"]] = {
                        "archivo": archivo,
                        "nombre": datos["nombre"],
                        "prereqs": datos["prereqs"],
                        "resultados": datos["resultados"]
                    }

            estado_general["estado"] = "listo"
            estado_general["mensaje"] = f"Análisis completado: {len(malla_curricular)} ramos detectados"
            estado_general["porcentaje"] = 100
        except Exception as e:
            estado_general["estado"] = "error"
            estado_general["mensaje"] = f"Error: {str(e)}"
        finally:
            proceso_activo = False

    thread = threading.Thread(target=procesar_bg)
    thread.daemon = True
    thread.start()
    return jsonify({"exito": True, "mensaje": "Procesamiento iniciado"})

@app.route('/api/malla', methods=['GET'])
def get_malla():
    resultado = []
    for codigo, datos in malla_curricular.items():
        ra_list = [desc for (id_ra, desc) in datos.get("resultados", [])]
        resultado.append({
            "codigo": codigo,
            "nombre": datos["nombre"],
            "archivo": datos["archivo"],
            "prereqs": ", ".join(datos["prereqs"]) if datos["prereqs"] else "Ninguno",
            "total_ra": len(datos["resultados"]),
            "ra_list": ra_list
        })
    return jsonify(resultado)

@app.route('/api/ejecutar-inferencia', methods=['POST'])
def ejecutar_inferencia():
    global enlaces_semanticos, proceso_activo
    if proceso_activo: return jsonify({"error": "Ya hay un proceso en ejecución"}), 400
    if modelo_nlp is None: return jsonify({"error": "Modelo NLP no está cargado"}), 400

    def inferencia_bg():
        global proceso_activo
        proceso_activo = True
        try:
            enlaces_semanticos.clear()
            estado_general["estado"] = "inferencia"
            ramos_list = list(malla_curricular.items())
            total_ramos = len(ramos_list)

            for idx, (codigo_actual, datos_actuales) in enumerate(ramos_list):
                estado_general["mensaje"] = f"Infiriendo Ramo ({idx+1}/{total_ramos}): {codigo_actual}"
                estado_general["porcentaje"] = int((idx / total_ramos) * 100) if total_ramos > 0 else 0

                # Solo continuamos si el ramo tiene RAs (ahora no importa si no tiene prerrequisitos, porque se evaluará a sí mismo)
                if not datos_actuales["resultados"]: continue

                # --- NUEVO: Creamos una lista que incluye los prerrequisitos Y el ramo actual ---
                ramos_a_evaluar = list(datos_actuales["prereqs"])
                if codigo_actual not in ramos_a_evaluar:
                    ramos_a_evaluar.append(codigo_actual)

                for codigo_prereq in ramos_a_evaluar:
                    if codigo_prereq in malla_curricular:
                        datos_prereq = malla_curricular[codigo_prereq]
                        if not datos_prereq["resultados"]: continue

                        for ra_act_id, ra_act_desc in datos_actuales["resultados"]:
                            mejor_score, mejor_ra_pre_desc = -1.0, None

                            for ra_pre_id, ra_pre_desc in datos_prereq["resultados"]:
                                # --- NUEVO: Evitar que un RA se compare exactamente consigo mismo ---
                                if codigo_actual == codigo_prereq and ra_act_id == ra_pre_id:
                                    continue

                                inputs = tokenizer(str(ra_act_desc), str(ra_pre_desc), return_tensors="pt", truncation=True, max_length=256)
                                with torch.no_grad():
                                    probs = F.softmax(modelo_nlp(**inputs).logits, dim=-1)[0]
                                
                                score = (probs[1].item() * 33.3) + (probs[2].item() * 66.6) + (probs[3].item() * 100.0)

                                if score > mejor_score:
                                    mejor_score = score
                                    mejor_ra_pre_desc = ra_pre_desc

                            # Si después de todo no hubo con quién comparar (ej. el ramo solo tenía 1 RA), lo ignoramos
                            if mejor_ra_pre_desc is None:
                                continue

                            if mejor_score > 75.0:
                                severidad = "alto"
                            elif mejor_score > 45.0:
                                severidad = "medio"
                            elif mejor_score > 20.0:
                                severidad = "bajo"
                            else:
                                severidad = "sin_match"

                            enlaces_semanticos.append({
                                "ramo_act": codigo_actual,
                                "ra_act": ra_act_desc,
                                "ramo_pre": codigo_prereq,
                                "ra_pre": mejor_ra_pre_desc,
                                "score": mejor_score if mejor_score != -1.0 else 0.0,
                                "severidad": severidad
                            })

            estado_general["estado"] = "listo"
            estado_general["mensaje"] = "Inferencia completada"
            estado_general["porcentaje"] = 100
        except Exception as e:
            estado_general["estado"] = "error"
            estado_general["mensaje"] = f"Error: {str(e)}"
        finally:
            proceso_activo = False

    threading.Thread(target=inferencia_bg, daemon=True).start()
    return jsonify({"exito": True, "mensaje": "Inferencia iniciada"})

@app.route('/api/matches', methods=['GET'])
def get_matches():
    resultado = []
    for link in enlaces_semanticos:
        resultado.append({
            "ramo_act": link["ramo_act"],
            "ra_act": link["ra_act"],
            "ramo_pre": link["ramo_pre"],
            "ra_pre": link["ra_pre"],
            "score": round(link["score"], 1),
            "severidad": link["severidad"],
            "nodo_origen_id": nodo_ra_id_de(link["ramo_pre"], link["ra_pre"]),
            "nodo_destino_id": nodo_ra_id_de(link["ramo_act"], link["ra_act"])
        })
    return jsonify(resultado)

@app.route('/api/exportar-excel', methods=['GET'])
def exportar_excel():
    """Genera y descarga un reporte Excel consolidado de los matches semánticos detectados"""
    if not enlaces_semanticos:
        return jsonify({"error": "No hay datos de matches semánticos para exportar"}), 400

    try:
        filas_excel = []
        for link in enlaces_semanticos:
            # Cruzamos los códigos con los nombres descriptivos almacenados localmente
            datos_act = malla_curricular.get(link["ramo_act"], {})
            datos_pre = malla_curricular.get(link["ramo_pre"], {})
            
            nombre_act = datos_act.get("nombre", "Desconocido")
            nombre_pre = datos_pre.get("nombre", "Desconocido")

            # --- CÁLCULO DINÁMICO DE LOS CÓDIGOS CORRELATIVOS DE RA ---
            # Para el Ramo Actual
            num_ra_act = 1
            lista_ras_act = datos_act.get("resultados", [])
            for idx, (id_ra, desc) in enumerate(lista_ras_act):
                if desc == link["ra_act"]:
                    num_ra_act = idx + 1
                    break
            codigo_ra_act_formateado = f"{link['ramo_act']} - {num_ra_act}"

            # Para el Ramo Prerrequisito
            num_ra_pre = 1
            lista_ras_pre = datos_pre.get("resultados", [])
            for idx, (id_ra, desc) in enumerate(lista_ras_pre):
                if desc == link["ra_pre"]:
                    num_ra_pre = idx + 1
                    break
            codigo_ra_pre_formateado = f"{link['ramo_pre']} - {num_ra_pre}"
            # ---------------------------------------------------------

            # Insertamos los nuevos campos exactamente antes de la columna del RA descriptivo correspondiente
            filas_excel.append({
                "Código Ramo Actual": link["ramo_act"],
                "Nombre Ramo Actual": nombre_act,
                "Código RA Actual": codigo_ra_act_formateado, # <-- Nueva columna
                "Resultado de Aprendizaje (RA) Actual": link["ra_act"],
                "Código Ramo Prerrequisito": link["ramo_pre"],
                "Nombre Ramo Prerrequisito": nombre_pre,
                "Código RA Prerrequisito": codigo_ra_pre_formateado, # <-- Nueva columna
                "Resultado de Aprendizaje (RA) Prerrequisito": link["ra_pre"],
                "Porcentaje de Similitud": f"{round(link['score'], 1)}%",
                "Nivel de vinculación": link["severidad"].upper()
            })

        # Crear DataFrame y guardar en buffer en memoria
        # --- NUEVO: Construir la tabla de Ramos ---
        ramos_data = []
        for codigo, datos in malla_curricular.items():
            ramos_data.append({
                "Código": codigo,
                "Nombre": datos.get("nombre", "Desconocido"),
                "Prerrequisitos": ", ".join(datos.get("prereqs", [])) if datos.get("prereqs") else "Ninguno"
            })
        df_ramos = pd.DataFrame(ramos_data)
        # ------------------------------------------

        # Crear DataFrame de los matches y definir la ruta
        df_matches = pd.DataFrame(filas_excel)
        ruta_salida = os.path.join(UPLOAD_FOLDER, "Reporte_Mapeo_Curricular.xlsx")
        
        # Guardar usando ExcelWriter para crear múltiples hojas
        with pd.ExcelWriter(ruta_salida, engine="openpyxl") as writer:
            df_matches.to_excel(writer, index=False, sheet_name="Matches Semánticos")
            df_ramos.to_excel(writer, index=False, sheet_name="Ramos")

        return send_file(
            ruta_salida,
            as_attachment=True,
            download_name=f"Reporte_Mapeo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        print(f"Error generando Excel: {e}")
        return jsonify({"error": f"Error interno al generar reporte: {str(e)}"}), 500

@app.route('/api/generar-grafo-macro', methods=['GET'])
def generar_grafo_macro():
    try:
        net = Network(height='700px', width='100%', directed=True, bgcolor='#1a1a1a', font_color='white')
        
        # --- CONFIGURACIÓN JERÁRQUICA FORZADA ---
        opciones_lr = """
        var options = {
          "edges": { "smooth": { "type": "cubicBezier", "forceDirection": "horizontal", "roundness": 0.4 } },
          "layout": {
            "hierarchical": {
              "enabled": true,
              "direction": "LR",
              "levelSeparation": 300,
              "nodeSpacing": 80
            }
          },
          "physics": { "enabled": false }
        }
        """
        net.set_options(opciones_lr)

        # 1. Calcular el nivel exacto de cada ramo (Algoritmo de Camino Más Largo)
        niveles = {cod: 0 for cod in malla_curricular}
        for _ in range(20):  # Iteramos un máximo de 20 veces (semestres) para evitar loops
            cambio = False
            for cod, datos in malla_curricular.items():
                for pre in datos.get('prereqs', []):
                    if pre in niveles and niveles[cod] <= niveles[pre]:
                        niveles[cod] = niveles[pre] + 1
                        cambio = True
            if not cambio:
                break

        # 2. Agregar Nodos asignando su "level" explícitamente
        for codigo, datos in malla_curricular.items():
            label_nodo = f"{datos.get('nombre', 'Desconocido')}\n({codigo})"
            # Asignamos el level forzando su columna
            net.add_node(codigo, label=label_nodo, color="#3498db", size=25, shape="box", level=niveles[codigo])

        # 3. Agregar conexiones
        for codigo_actual, datos in malla_curricular.items():
            for prereq in datos['prereqs']:
                if prereq in malla_curricular:
                    net.add_edge(prereq, codigo_actual, color="#aaaaaa", arrows="to")

        grafo_id = str(uuid.uuid4())
        ruta_html = os.path.join(GRAPHS_FOLDER, f"grafo_macro_{grafo_id}.html")
        net.write_html(ruta_html)
        
        inyectar_buscador_grafo(ruta_html)
        
        return jsonify({"exito": True, "grafo_url": f"/static/graphs/grafo_macro_{grafo_id}.html"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/generar-grafo-micro', methods=['GET'])
def generar_grafo_micro():
    try:
        net = Network(height='700px', width='100%', directed=True, bgcolor='#1a1a1a', font_color='white')
        
        # --- CONFIGURACIÓN JERÁRQUICA FORZADA ---
        opciones_lr = """
        var options = {
          "edges": { "smooth": { "type": "cubicBezier", "forceDirection": "horizontal", "roundness": 0.4 } },
          "layout": {
            "hierarchical": {
              "enabled": true,
              "direction": "LR",
              "levelSeparation": 350,
              "nodeSpacing": 50
            }
          },
          "physics": { "enabled": false }
        }
        """
        net.set_options(opciones_lr)

        # 1. Calcular el nivel exacto de cada ramo (Semestres)
        niveles = {cod: 0 for cod in malla_curricular}
        for _ in range(20): 
            cambio = False
            for cod, datos in malla_curricular.items():
                for pre in datos.get('prereqs', []):
                    if pre in niveles and niveles[cod] <= niveles[pre]:
                        niveles[cod] = niveles[pre] + 1
                        cambio = True
            if not cambio:
                break

        # 2. Agregar los Nodos con sus columnas estrictas
        for codigo, datos in malla_curricular.items():
            label_ramo = f"{datos.get('nombre', '')}\n({codigo})"
            
            # El Ramo va en una columna par (0, 2, 4...)
            ramo_level = niveles[codigo] * 2  
            net.add_node(codigo, label=label_ramo, color="#2980b9", shape="box", font={"size": 22}, level=ramo_level)

            # Los RAs de ese ramo van en la columna impar inmediatamente siguiente (1, 3, 5...)
            for ra_id, desc in datos['resultados']:
                nodo_ra_id = nodo_ra_id_de(codigo, desc)
                desc_multilinea = "\n".join(textwrap.wrap(desc, width=45))
                tooltip_texto = f"[{ra_id}]\n{desc_multilinea}"
                
                # Nivel estricto: level = ramo_level + 1
                net.add_node(nodo_ra_id, label=ra_id, title=tooltip_texto, color="#1abc9c", size=10, shape="dot", level=ramo_level + 1)
                
                # Conexión del Ramo a su RA
                net.add_edge(codigo, nodo_ra_id, color="rgba(255,255,255,0.15)", arrows="")

        # 3. Conexiones Semánticas (Las flechas largas)
        # Conexiones semánticas entre RAs
        for link in enlaces_semanticos:
            nodo_origen = nodo_ra_id_de(link['ramo_pre'], link['ra_pre'])
            nodo_destino = nodo_ra_id_de(link['ramo_act'], link['ra_act'])
            
            if link['score'] > 40.0:
                is_internal = (link['ramo_act'] == link['ramo_pre'])
                
                # Definimos el estilo de la flecha
                # Si es interno, le damos más curvatura (roundness) y un color distinto
                color_linea = "rgba(100, 100, 100, 0.6)" if is_internal else ("#17a2b8" if link['score'] == 100.0 else "#e67e22")
                curvatura = 0.8 if is_internal else 0.4
                ancho = 2 if is_internal else 3

                net.add_edge(
                    nodo_origen, 
                    nodo_destino, 
                    color=color_linea, 
                    title=f"Match: {link['score']:.1f}%", 
                    arrows="to",
                    smooth={"type": "curvedCW", "roundness": curvatura},
                    width=ancho
                )

        grafo_id = str(uuid.uuid4())
        ruta_html = os.path.join(GRAPHS_FOLDER, f"grafo_micro_{grafo_id}.html")
        net.write_html(ruta_html)
        
        inyectar_buscador_grafo(ruta_html)
        
        return jsonify({"exito": True, "grafo_url": f"/static/graphs/grafo_micro_{grafo_id}.html"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/corregir-match', methods=['POST'])
def corregir_match():
    data = request.json
    nueva_sev = data.get('nueva_severidad')
    
    # Asignamos un score matemático en base a la severidad elegida
    if nueva_sev == "alto": 
        score = 100.0
    elif nueva_sev == "medio": 
        score = 79
    elif nueva_sev == "bajo": 
        score = 59
    elif nueva_sev == "sin_match": 
        score = 0.0
    else: 
        score = 0.0 # Casillero de seguridad

    # Buscamos el match específico en nuestra memoria
    for link in enlaces_semanticos:
        if (link["ramo_act"] == data.get('ramo_act') and 
            link["ra_act"] == data.get('ra_act') and 
            link["ramo_pre"] == data.get('ramo_pre')):
            
            # Aplicamos la corrección
            link["ra_pre"] = data.get('nuevo_ra_pre')
            link["score"] = score
            link["severidad"] = nueva_sev
            
            return jsonify({"exito": True, "mensaje": "Match actualizado correctamente"})
            
    return jsonify({"error": "No se encontró el match exacto en la memoria"}), 404

# ==================== AÑADIR AL app.py EXISTENTE ====================
# Estas rutas van junto al resto de @app.route(...) en app.py

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


def _calcular_ras_sin_conectar():
    """Devuelve (ras_conectados_set, ras_sin_conectar_list, conteo_razones_dict)"""
    def normalizar(texto):
        return re.sub(r'\s+', ' ', (texto or '')).strip().lower()

    LARGO_PREFIJO = 80

    mejor_score_hacia_atras = {}
    prefijo_score_hacia_atras = {}
    
    # Únicos sets de validación que usaremos para unificar el criterio
    ras_en_grafo_global = set()
    ras_en_grafo_global_prefijo = set()

    for link in enlaces_semanticos:
        ramo_act, ramo_pre = link["ramo_act"], link["ramo_pre"]
        ra_act_norm = normalizar(link["ra_act"])
        ra_pre_norm = normalizar(link["ra_pre"])
        
        clave_act = (ramo_act, ra_act_norm)
        clave_pre = (ramo_pre, ra_pre_norm)
        prefijo_act = (ramo_act, ra_act_norm[:LARGO_PREFIJO])
        prefijo_pre = (ramo_pre, ra_pre_norm[:LARGO_PREFIJO])
        
        score = link["score"]
        es_enlace_interno = (ramo_act == ramo_pre)

        if not es_enlace_interno:
            if score > 40.0:
                # El RA entra al grafo oficial, sin importar si es origen o destino
                ras_en_grafo_global.add(clave_act)
                ras_en_grafo_global.add(clave_pre)
                ras_en_grafo_global_prefijo.add(prefijo_act)
                ras_en_grafo_global_prefijo.add(prefijo_pre)

            # Para la razón específica de "Score bajo", seguimos evaluando solo hacia atrás
            if clave_act not in mejor_score_hacia_atras or score > mejor_score_hacia_atras[clave_act]:
                mejor_score_hacia_atras[clave_act] = score
            if prefijo_act not in prefijo_score_hacia_atras or score > prefijo_score_hacia_atras[prefijo_act]:
                prefijo_score_hacia_atras[prefijo_act] = score

    ras_sin_conectar = []
    conteo_razones = {
        "sin_prerrequisitos": 0,
        "prereq_no_encontrado": 0,
        "score_bajo": 0,
        "sin_evaluar": 0
    }

    for codigo, datos in malla_curricular.items():
        prereqs = datos.get("prereqs", [])
        prereqs_externos = [p for p in prereqs if p != codigo]
        
        # Filtra para que considere 'encontrado' solo si vino de un PDF procesado
        prereqs_con_ra = [
            p for p in prereqs_externos
            if p in malla_curricular 
            and malla_curricular[p].get("resultados") 
            and malla_curricular[p].get("archivo") != "" # <--- Validar que tenga un archivo fuente
        ]

        for ra_id, desc in datos.get("resultados", []):
            desc_norm = normalizar(desc)
            clave = (codigo, desc_norm)
            clave_prefijo = (codigo, desc_norm[:LARGO_PREFIJO])

            # AQUÍ ESTÁ EL ARREGLO:
            # Si el RA ya forma parte del grafo (conectado), saltamos. Ya NO suma a las razones de error.
            if clave in ras_en_grafo_global or clave_prefijo in ras_en_grafo_global_prefijo:
                continue

            tiene_enlace_externo = clave in mejor_score_hacia_atras or clave_prefijo in prefijo_score_hacia_atras

            # El orden correcto prioriza si ya existe un cálculo real (score)
            if tiene_enlace_externo:
                razon = "score_bajo"
            elif not prereqs_externos:
                razon = "sin_prerrequisitos"
            elif not prereqs_con_ra:
                razon = "prereq_no_encontrado"
            else:
                razon = "sin_evaluar"

            mejor_score = mejor_score_hacia_atras.get(clave)
            if mejor_score is None:
                mejor_score = prefijo_score_hacia_atras.get(clave_prefijo, 0.0)

            conteo_razones[razon] += 1
            ras_sin_conectar.append({
                "codigo_ramo": codigo,
                "nombre_ramo": datos.get("nombre", "Desconocido"),
                "ra_id": ra_id,
                "descripcion": desc,
                "razon": razon,
                "mejor_score": round(mejor_score, 1)
            })

    ras_conectados_resueltos = set()
    for codigo, datos in malla_curricular.items():
        for ra_id, desc in datos.get("resultados", []):
            desc_norm = normalizar(desc)
            clave_norm = (codigo, desc_norm)
            clave_pref = (codigo, desc_norm[:LARGO_PREFIJO])
            if clave_norm in ras_en_grafo_global or clave_pref in ras_en_grafo_global_prefijo:
                # Guardamos con desc normalizada para que todas las comparaciones sean consistentes
                ras_conectados_resueltos.add((codigo, desc_norm))

    return ras_conectados_resueltos, ras_sin_conectar, conteo_razones


# Etiquetas legibles para cada razón
RAZON_LABELS = {
    "sin_prerrequisitos": "Sin prerrequisitos",
    "prereq_no_encontrado": "Prerreq. no encontrado en malla",
    "score_bajo": "Score bajo (≤ 40%)",
    "sin_evaluar": "Sin evaluar"
}


@app.route('/api/debug-ras-sin-conectar', methods=['GET'])
def debug_ras_sin_conectar():
    """Endpoint temporal de diagnóstico: muestra los códigos de ramo presentes
    en malla_curricular vs los códigos usados en enlaces_semanticos, para
    detectar mismatches de código (no de descripción).
    """
    codigos_malla = set(malla_curricular.keys())
    codigos_enlaces = set()
    for link in enlaces_semanticos:
        codigos_enlaces.add(link["ramo_act"])
        codigos_enlaces.add(link["ramo_pre"])

    solo_en_enlaces = sorted(codigos_enlaces - codigos_malla)
    solo_en_malla_relevantes = sorted(
        c for c in (codigos_malla - codigos_enlaces)
        if malla_curricular[c].get("resultados")
    )

    # Para ING 2203 / ING 2207 específicamente (y cualquier código similar),
    # mostramos qué enlaces existen y si la clave coincide con malla_curricular
    detalle = []
    for codigo, datos in malla_curricular.items():
        for ra_id, desc in datos.get("resultados", []):
            enlaces_rel = [
                {
                    "ramo_act": l["ramo_act"], "ra_act": l["ra_act"][:60],
                    "ramo_pre": l["ramo_pre"], "ra_pre": l["ra_pre"][:60],
                    "score": l["score"], "severidad": l["severidad"]
                }
                for l in enlaces_semanticos
                if (l["ramo_act"] == codigo and l["ra_act"] == desc)
                or (l["ramo_pre"] == codigo and l["ra_pre"] == desc)
            ]
            if enlaces_rel:
                detalle.append({
                    "codigo_malla": codigo,
                    "ra_id": ra_id,
                    "descripcion": desc[:80],
                    "enlaces": enlaces_rel
                })

    return jsonify({
        "total_codigos_malla": len(codigos_malla),
        "total_codigos_en_enlaces": len(codigos_enlaces),
        "codigos_en_enlaces_pero_no_en_malla": solo_en_enlaces,
        "codigos_en_malla_con_ra_pero_sin_enlaces": solo_en_malla_relevantes,
        "detalle_ras_con_enlaces": detalle
    })


@app.route('/api/dashboard-stats', methods=['GET'])
def dashboard_stats():
    """Calcula estadísticas globales sobre ramos y RAs para el dashboard"""
    try:
        total_ramos = len(malla_curricular)

        # RAs totales en toda la malla
        total_ras = sum(len(d.get("resultados", [])) for d in malla_curricular.values())

        # Clasificación de RAs sin conectar (incluye set de conectados)
        ras_conectados, ras_sin_conectar, conteo_razones = _calcular_ras_sin_conectar()

        total_ras_conectados = len(ras_conectados)
        total_ras_sin_conectar = max(total_ras - total_ras_conectados, 0)

        # Ramos sin ningún RA conectado (de los que tienen al menos 1 RA)
        ramos_sin_conexion = []
        def _norm(t): return re.sub(r'\s+', ' ', (t or '')).strip().lower()

        ramos_con_ra = 0
        for codigo, datos in malla_curricular.items():
            resultados = datos.get("resultados", [])
            if not resultados:
                continue
            ramos_con_ra += 1
            tiene_conexion = any((codigo, _norm(desc)) in ras_conectados for (_id, desc) in resultados)
            if not tiene_conexion:
                ramos_sin_conexion.append({
                    "codigo": codigo,
                    "nombre": datos.get("nombre", "Desconocido"),
                    "total_ra": len(resultados),
                    "tiene_prereqs": len(datos.get("prereqs", [])) > 0
                })

        # Distribución de severidad de los enlaces
        conteo_severidad = {"alto": 0, "medio": 0, "bajo": 0, "sin_match": 0}
        for link in enlaces_semanticos:
            sev = link.get("severidad", "sin_match")
            if sev in conteo_severidad:
                conteo_severidad[sev] += 1
            else:
                conteo_severidad["sin_match"] += 1

        # Top ramos prerrequisito más referenciados (mayor cantidad de matches alto+medio)
        conteo_prereq = {}
        for link in enlaces_semanticos:
            
            if link["severidad"] in ("alto", "medio") and link["ramo_act"] != link["ramo_pre"]:
                clave = link["ramo_pre"]
                conteo_prereq[clave] = conteo_prereq.get(clave, 0) + 1
        top_prereqs = sorted(conteo_prereq.items(), key=lambda x: x[1], reverse=True)[:10]
        top_prereqs_list = [
            {
                "codigo": cod,
                "nombre": malla_curricular.get(cod, {}).get("nombre", "Desconocido"),
                "conexiones": cant
            }
            for cod, cant in top_prereqs
        ]

        # Score promedio global
        score_promedio = 0.0
        if enlaces_semanticos:
            score_promedio = sum(l["score"] for l in enlaces_semanticos) / len(enlaces_semanticos)
# --- NUEVO: Extraer enlaces débiles ---
        enlaces_debiles = []
        for link in enlaces_semanticos:
            if link["score"] <= 40.0:
                enlaces_debiles.append({
                    "ramo_act": link["ramo_act"],
                    "nombre_act": malla_curricular.get(link["ramo_act"], {}).get("nombre", ""),
                    "ra_act": link["ra_act"],
                    "ramo_pre": link["ramo_pre"],
                    "nombre_pre": malla_curricular.get(link["ramo_pre"], {}).get("nombre", ""),
                    "ra_pre": link["ra_pre"],
                    "score": round(link["score"], 1)
                })
        # Ordenar de menor a mayor score
        enlaces_debiles = sorted(enlaces_debiles, key=lambda x: x["score"])

        return jsonify({
            "total_ramos": total_ramos,
            "total_ras": total_ras,
            "total_ras_conectados": total_ras_conectados,
            "total_ras_sin_conectar": total_ras_sin_conectar,
            "total_enlaces": len(enlaces_semanticos),
            "ramos_con_ra": ramos_con_ra,
            "ramos_sin_conexion_count": len(ramos_sin_conexion),
            "ramos_sin_conexion": ramos_sin_conexion,
            "conteo_severidad": conteo_severidad,
            "conteo_razones_sin_conectar": conteo_razones,
            "ras_sin_conectar": ras_sin_conectar,
            "top_prereqs": top_prereqs_list,
            "score_promedio": round(score_promedio, 1),
            "porcentaje_cobertura": round((total_ras_conectados / total_ras * 100) if total_ras > 0 else 0, 1),
            "enlaces_debiles": enlaces_debiles # <--- LA NUEVA LISTA
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/exportar-dashboard-excel', methods=['GET'])
def exportar_dashboard_excel():
    """Genera un Excel multi-hoja con todas las estadísticas del dashboard"""
    try:
        # --- Hoja 1: Resumen general ---
        ras_conectados, ras_sin_conectar_raw, conteo_razones = _calcular_ras_sin_conectar()

        total_ras = sum(len(d.get("resultados", [])) for d in malla_curricular.values())
        total_ras_conectados = len(ras_conectados)
        total_ras_sin_conectar = max(total_ras - total_ras_conectados, 0)

        conteo_severidad = {"alto": 0, "medio": 0, "bajo": 0, "sin_match": 0}
        for link in enlaces_semanticos:
            sev = link.get("severidad", "sin_match")
            if sev in conteo_severidad:
                conteo_severidad[sev] += 1
            else:
                conteo_severidad["sin_match"] += 1

        score_promedio = 0.0
        if enlaces_semanticos:
            score_promedio = sum(l["score"] for l in enlaces_semanticos) / len(enlaces_semanticos)

        resumen = pd.DataFrame([
            {"Indicador": "Ramos analizados", "Valor": len(malla_curricular)},
            {"Indicador": "Total RAs detectados", "Valor": total_ras},
            {"Indicador": "RAs conectados (score > 40%)", "Valor": total_ras_conectados},
            {"Indicador": "RAs sin conectar", "Valor": total_ras_sin_conectar},
            {"Indicador": "  - Sin prerrequisitos", "Valor": conteo_razones["sin_prerrequisitos"]},
            {"Indicador": "  - Prerreq. no encontrado en malla", "Valor": conteo_razones["prereq_no_encontrado"]},
            {"Indicador": "  - Score bajo (≤ 40%)", "Valor": conteo_razones["score_bajo"]},
            {"Indicador": "  - Sin evaluar", "Valor": conteo_razones["sin_evaluar"]},
            {"Indicador": "Cobertura de RAs (%)", "Valor": round((total_ras_conectados / total_ras * 100) if total_ras > 0 else 0, 1)},
            {"Indicador": "Total enlaces semánticos", "Valor": len(enlaces_semanticos)},
            {"Indicador": "Score promedio (%)", "Valor": round(score_promedio, 1)},
            {"Indicador": "Enlaces - Alto", "Valor": conteo_severidad["alto"]},
            {"Indicador": "Enlaces - Medio", "Valor": conteo_severidad["medio"]},
            {"Indicador": "Enlaces - Bajo", "Valor": conteo_severidad["bajo"]},
            {"Indicador": "Enlaces - Sin match", "Valor": conteo_severidad["sin_match"]},
        ])

        # --- Hoja 2: Ramos sin ningún RA conectado ---
        ramos_sin_conexion = []
        def _norm_xl(t): return re.sub(r'\s+', ' ', (t or '')).strip().lower()

        for codigo, datos in malla_curricular.items():
            resultados = datos.get("resultados", [])
            if not resultados:
                continue
            tiene_conexion = any((codigo, _norm_xl(desc)) in ras_conectados for (_id, desc) in resultados)
            if not tiene_conexion:
                ramos_sin_conexion.append({
                    "Código": codigo,
                    "Nombre del Ramo": datos.get("nombre", "Desconocido"),
                    "Total RAs": len(resultados),
                    "Tiene Prerrequisitos": "Sí" if datos.get("prereqs") else "No"
                })
        df_ramos_sin_conexion = pd.DataFrame(ramos_sin_conexion) if ramos_sin_conexion else pd.DataFrame(
            columns=["Código", "Nombre del Ramo", "Total RAs", "Tiene Prerrequisitos"])

        # --- Hoja 3: RAs individuales sin conectar (con razón) ---
        ras_sin_conectar = [
            {
                "Código Ramo": ra["codigo_ramo"],
                "Nombre Ramo": ra["nombre_ramo"],
                "ID RA": ra["ra_id"],
                "Descripción RA": ra["descripcion"],
                "Razón": RAZON_LABELS.get(ra["razon"], ra["razon"]),
                "Mejor Score Visto (%)": ra["mejor_score"]
            }
            for ra in ras_sin_conectar_raw
        ]
        df_ras_sin_conectar = pd.DataFrame(ras_sin_conectar) if ras_sin_conectar else pd.DataFrame(
            columns=["Código Ramo", "Nombre Ramo", "ID RA", "Descripción RA", "Razón", "Mejor Score Visto (%)"])

        # --- Hoja 3b: Resumen de razones ---
        df_razones = pd.DataFrame([
            {"Razón": RAZON_LABELS[r], "Cantidad de RAs": conteo_razones[r]}
            for r in ["sin_prerrequisitos", "prereq_no_encontrado", "score_bajo", "sin_evaluar"]
        ])

        # --- Hoja 4: Todos los ramos (vista general) ---
        todos_ramos = []
        for codigo, datos in malla_curricular.items():
            resultados = datos.get("resultados", [])
            conectados = sum(1 for (_id, desc) in resultados if (codigo, _norm_xl(desc)) in ras_conectados)
            todos_ramos.append({
                "Código": codigo,
                "Nombre": datos.get("nombre", "Desconocido"),
                "Prerrequisitos": ", ".join(datos.get("prereqs", [])) if datos.get("prereqs") else "Ninguno",
                "Total RAs": len(resultados),
                "RAs Conectados": conectados,
                "RAs Sin Conectar": len(resultados) - conectados
            })
        df_todos_ramos = pd.DataFrame(todos_ramos)

        # --- Hoja 5: Top prerrequisitos más referenciados ---
        conteo_prereq = {}
        for link in enlaces_semanticos:
            if link["severidad"] in ("alto", "medio"):
                clave = link["ramo_pre"]
                conteo_prereq[clave] = conteo_prereq.get(clave, 0) + 1
        top_prereqs = sorted(conteo_prereq.items(), key=lambda x: x[1], reverse=True)
        df_top_prereqs = pd.DataFrame([
            {
                "Código": cod,
                "Nombre": malla_curricular.get(cod, {}).get("nombre", "Desconocido"),
                "Conexiones Alto/Medio": cant
            }
            for cod, cant in top_prereqs
        ]) if top_prereqs else pd.DataFrame(columns=["Código", "Nombre", "Conexiones Alto/Medio"])

        # --- Hoja 6: Todos los enlaces semánticos (RA -> RA, con texto completo) ---
        cols_enlaces = ["Ramo Actual", "Nombre Ramo Actual", "RA Actual",
                        "Ramo Prerrequisito", "Nombre Prerrequisito", "RA Prerrequisito",
                        "Score (%)", "Severidad"]
        enlaces_full = [
            {
                "Ramo Actual": link.get("ramo_act", ""),
                "Nombre Ramo Actual": malla_curricular.get(link.get("ramo_act"), {}).get("nombre", ""),
                "RA Actual": link.get("ra_act", ""),
                "Ramo Prerrequisito": link.get("ramo_pre", ""),
                "Nombre Prerrequisito": malla_curricular.get(link.get("ramo_pre"), {}).get("nombre", ""),
                "RA Prerrequisito": link.get("ra_pre", ""),
                "Score (%)": round(link.get("score", 0), 1),
                "Severidad": (link.get("severidad", "sin_match") or "sin_match").capitalize()
            }
            for link in sorted(enlaces_semanticos, key=lambda l: l.get("score", 0), reverse=True)
        ]
        df_enlaces = pd.DataFrame(enlaces_full) if enlaces_full else pd.DataFrame(columns=cols_enlaces)

        # --- Hoja 7: Enlaces débiles (score <= 40%, los mismos de la tabla del dashboard) ---
        enlaces_debiles = [
            {
                "Ramo Actual": link.get("ramo_act", ""),
                "Nombre Ramo Actual": malla_curricular.get(link.get("ramo_act"), {}).get("nombre", ""),
                "RA Actual": link.get("ra_act", ""),
                "Ramo Prerrequisito": link.get("ramo_pre", ""),
                "Nombre Prerrequisito": malla_curricular.get(link.get("ramo_pre"), {}).get("nombre", ""),
                "RA Prerrequisito": link.get("ra_pre", ""),
                "Score (%)": round(link.get("score", 0), 1)
            }
            for link in enlaces_semanticos if link.get("score", 0) <= 40.0
        ]
        enlaces_debiles = sorted(enlaces_debiles, key=lambda x: x["Score (%)"])
        cols_debiles = ["Ramo Actual", "Nombre Ramo Actual", "RA Actual",
                        "Ramo Prerrequisito", "Nombre Prerrequisito", "RA Prerrequisito", "Score (%)"]
        df_enlaces_debiles = pd.DataFrame(enlaces_debiles) if enlaces_debiles else pd.DataFrame(columns=cols_debiles)

        ruta_salida = os.path.join(UPLOAD_FOLDER, "Dashboard_Curricular.xlsx")
        with pd.ExcelWriter(ruta_salida, engine="openpyxl") as writer:
            resumen.to_excel(writer, index=False, sheet_name="Resumen General")
            df_todos_ramos.to_excel(writer, index=False, sheet_name="Ramos")
            df_ramos_sin_conexion.to_excel(writer, index=False, sheet_name="Ramos Sin Conexion")
            df_razones.to_excel(writer, index=False, sheet_name="RAs Sin Conectar - Resumen")
            df_ras_sin_conectar.to_excel(writer, index=False, sheet_name="RAs Sin Conectar")
            df_top_prereqs.to_excel(writer, index=False, sheet_name="Top Prerrequisitos")
            df_enlaces.to_excel(writer, index=False, sheet_name="Enlaces Semanticos")
            df_enlaces_debiles.to_excel(writer, index=False, sheet_name="Enlaces Debiles")

        return send_file(
            ruta_salida,
            as_attachment=True,
            download_name=f"Dashboard_Curricular_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        print(f"Error generando Excel del dashboard: {e}")
        return jsonify({"error": f"Error interno al generar reporte: {str(e)}"}), 500
    
@app.route('/api/cargar-inferencia', methods=['POST'])
def cargar_inferencia():
    """
    Restaura una inferencia previa a partir del Excel exportado.
    Acepta tanto el Excel básico (hoja 'Matches Semánticos') como
    el Excel del dashboard (hoja 'Enlaces Semanticos' + hoja 'Ramos').
    """
    global malla_curricular, enlaces_semanticos

    if 'archivo' not in request.files:
        return jsonify({"error": "No se recibió ningún archivo"}), 400

    archivo = request.files['archivo']
    if not archivo.filename.endswith(('.xlsx', '.xls')):
        return jsonify({"error": "El archivo debe ser un Excel (.xlsx o .xls)"}), 400

    try:
        # Leer todas las hojas disponibles
        xl = pd.ExcelFile(archivo)
        hojas = xl.sheet_names

        # ── Detectar el formato del Excel ──────────────────────────────────────
        # Formato 1 (exportar_excel): hoja "Matches Semánticos"
        # Formato 2 (exportar_dashboard_excel): hojas "Enlaces Semanticos" + "Ramos"
        tiene_matches   = "Matches Semánticos" in hojas
        tiene_enlaces   = "Enlaces Semanticos" in hojas
        tiene_ramos     = "Ramos" in hojas

        if not tiene_matches and not tiene_enlaces:
            return jsonify({
                "error": "El Excel no contiene las hojas esperadas. "
                         "Debe tener 'Matches Semánticos' (reporte básico) "
                         "o 'Enlaces Semanticos' (reporte dashboard)."
            }), 400

        nuevos_enlaces = []
        nueva_malla    = {}   # reconstrucción parcial desde el Excel

        # ── Leer malla desde hoja Ramos (si existe) ───────────────────────────
        if tiene_ramos:
            df_ramos = xl.parse("Ramos")
            for _, fila in df_ramos.iterrows():
                codigo = str(fila.get("Código", "")).strip()
                if not codigo:
                    continue
                nombre = str(fila.get("Nombre", "Desconocido")).strip()
                prereqs_raw = str(fila.get("Prerrequisitos", "")).strip()
                prereqs = [] if prereqs_raw in ("", "Ninguno", "nan") else [
                    normalizar_codigo(p.strip()) for p in prereqs_raw.split(",") if p.strip()
                ]
                nueva_malla[codigo] = {
                    "archivo": "",          # no disponible en el Excel
                    "nombre": nombre,
                    "prereqs": prereqs,
                    "resultados": []        # se reconstruirá desde los enlaces
                }

        # ── Leer enlaces según el formato detectado ───────────────────────────
        if tiene_matches:
            # Formato básico (exportar_excel)
            df = xl.parse("Matches Semánticos")

            col_map = {
                "ramo_act": ["Código Ramo Actual"],
                "nombre_act": ["Nombre Ramo Actual"],
                "id_ra_act": ["Código RA Actual"],
                "ra_act": ["Resultado de Aprendizaje (RA) Actual"],
                "ramo_pre": ["Código Ramo Prerrequisito"],
                "nombre_pre": ["Nombre Ramo Prerrequisito"],
                "id_ra_pre": ["Código RA Prerrequisito"],
                "ra_pre": ["Resultado de Aprendizaje (RA) Prerrequisito"],
                "score": ["Porcentaje de Similitud"],
                "severidad": ["Nivel de vinculación"],
            }

            def get_col(row, candidates):
                for c in candidates:
                    if c in row.index and pd.notna(row[c]):
                        return str(row[c]).strip()
                return ""

            for _, fila in df.iterrows():
                ramo_act  = get_col(fila, col_map["ramo_act"])
                nombre_act = get_col(fila, col_map["nombre_act"])
                id_ra_act_raw = get_col(fila, col_map["id_ra_act"]) # Ej: "ING 1100 - 1"
                ra_act    = get_col(fila, col_map["ra_act"])
                
                ramo_pre  = get_col(fila, col_map["ramo_pre"])
                nombre_pre = get_col(fila, col_map["nombre_pre"])
                id_ra_pre_raw = get_col(fila, col_map["id_ra_pre"]) # Ej: "ING 1201 - 3"
                ra_pre    = get_col(fila, col_map["ra_pre"])
                
                score_raw = get_col(fila, col_map["score"])
                sev_raw   = get_col(fila, col_map["severidad"])

                if not ramo_act or not ra_act:
                    continue

                # Normalizar score: puede venir como "75.3%" o "75.3"
                try:
                    score = float(str(score_raw).replace("%", "").strip())
                except (ValueError, AttributeError):
                    score = 0.0

                # Normalizar severidad
                severidad = sev_raw.lower() if sev_raw else "sin_match"
                if severidad not in ("alto", "medio", "bajo", "sin_match"):
                    if score > 75.0:   severidad = "alto"
                    elif score > 45.0: severidad = "medio"
                    elif score > 20.0: severidad = "bajo"
                    else:              severidad = "sin_match"

                nuevos_enlaces.append({
                    "ramo_act": ramo_act,
                    "ra_act": ra_act,
                    "ramo_pre": ramo_pre,
                    "ra_pre": ra_pre,
                    "score": score,
                    "severidad": severidad,
                })

                # Función auxiliar para aislar el número del formato "ING 1100 - 1"
                def extraer_numero_ra(raw_str, current_list):
                    if raw_str and "-" in raw_str:
                        return raw_str.split("-")[-1].strip()
                    return str(len(current_list) + 1)

                # Procesar Ramo Actual
                if ramo_act:
                    if ramo_act not in nueva_malla:
                        nueva_malla[ramo_act] = {"archivo": "", "nombre": nombre_act or "Desconocido", "prereqs": [], "resultados": []}
                    elif nombre_act and nueva_malla[ramo_act].get("nombre") in ("", "Desconocido"):
                        nueva_malla[ramo_act]["nombre"] = nombre_act

                    if ra_act and not any(d == ra_act for _, d in nueva_malla[ramo_act]["resultados"]):
                        num_ra = extraer_numero_ra(id_ra_act_raw, nueva_malla[ramo_act]["resultados"])
                        nueva_malla[ramo_act]["resultados"].append((f"RA {num_ra}", ra_act))

                # Procesar Ramo Prerrequisito
                if ramo_pre:
                    if ramo_pre not in nueva_malla:
                        nueva_malla[ramo_pre] = {"archivo": "", "nombre": nombre_pre or "Desconocido", "prereqs": [], "resultados": []}
                    elif nombre_pre and nueva_malla[ramo_pre].get("nombre") in ("", "Desconocido"):
                        nueva_malla[ramo_pre]["nombre"] = nombre_pre

                    if ra_pre and not any(d == ra_pre for _, d in nueva_malla[ramo_pre]["resultados"]):
                        num_ra = extraer_numero_ra(id_ra_pre_raw, nueva_malla[ramo_pre]["resultados"])
                        nueva_malla[ramo_pre]["resultados"].append((f"RA {num_ra}", ra_pre))

        elif tiene_enlaces:
            # Formato dashboard (exportar_dashboard_excel) — hoja "Enlaces Semanticos"
            df = xl.parse("Enlaces Semanticos")

            for _, fila in df.iterrows():
                ramo_act  = str(fila.get("Ramo Actual", "")).strip()
                nombre_act = str(fila.get("Nombre Ramo Actual", "")).strip()
                ra_act    = str(fila.get("RA Actual", "")).strip()
                ramo_pre  = str(fila.get("Ramo Prerrequisito", "")).strip()
                nombre_pre = str(fila.get("Nombre Prerrequisito", "")).strip()
                ra_pre    = str(fila.get("RA Prerrequisito", "")).strip()
                score_raw = fila.get("Score (%)", 0)
                sev_raw   = str(fila.get("Severidad", "")).strip().lower()

                if not ramo_act or not ra_act:
                    continue

                try:
                    score = float(score_raw)
                except (ValueError, TypeError):
                    score = 0.0

                severidad = sev_raw if sev_raw in ("alto", "medio", "bajo", "sin_match") else "sin_match"

                nuevos_enlaces.append({
                    "ramo_act": ramo_act,
                    "ra_act": ra_act,
                    "ramo_pre": ramo_pre,
                    "ra_pre": ra_pre,
                    "score": score,
                    "severidad": severidad,
                })

                for cod, nom, ra in [(ramo_act, nombre_act, ra_act), (ramo_pre, nombre_pre, ra_pre)]:
                    if not cod:
                        continue
                    if cod not in nueva_malla:
                        nueva_malla[cod] = {
                            "archivo": "",
                            "nombre": nom or "Desconocido",
                            "prereqs": [],
                            "resultados": []
                        }
                    elif nom and nueva_malla[cod].get("nombre") in ("", "Desconocido"):
                        nueva_malla[cod]["nombre"] = nom

                    if ra and not any(d == ra for _, d in nueva_malla[cod]["resultados"]):
                        nueva_malla[cod]["resultados"].append(("RA", ra))

        # ── Reconstruir prereqs desde los enlaces (si la hoja Ramos no estaba) ─
        if not tiene_ramos:
            for enlace in nuevos_enlaces:
                ramo_act = enlace["ramo_act"]
                ramo_pre = enlace["ramo_pre"]
                if ramo_act == ramo_pre:
                    continue
                if ramo_act in nueva_malla:
                    if ramo_pre not in nueva_malla[ramo_act]["prereqs"]:
                        nueva_malla[ramo_act]["prereqs"].append(ramo_pre)

        # ── Aplicar al estado global ──────────────────────────────────────────
        # Fusionamos: si ya hay datos de syllabi procesados, los preservamos
        # y solo sobreescribimos lo que el Excel trae.
        for cod, datos in nueva_malla.items():
            if cod in malla_curricular:
                # Ya existe (viene de PDFs): preservar resultados reales, actualizar nombre si faltaba
                if malla_curricular[cod].get("nombre") in ("", "Desconocido"):
                    malla_curricular[cod]["nombre"] = datos["nombre"]
            else:
                malla_curricular[cod] = datos

        enlaces_semanticos.clear()
        enlaces_semanticos.extend(nuevos_enlaces)

        estado_general["estado"] = "listo"
        estado_general["mensaje"] = f"Inferencia cargada: {len(nuevos_enlaces)} enlaces, {len(nueva_malla)} ramos"
        estado_general["porcentaje"] = 100

        return jsonify({
            "exito": True,
            "mensaje": f"Inferencia cargada correctamente",
            "enlaces_cargados": len(nuevos_enlaces),
            "ramos_reconstruidos": len(nueva_malla),
            "formato_detectado": "basico" if tiene_matches else "dashboard"
        })

    except Exception as e:
        print(f"Error cargando inferencia desde Excel: {e}")
        return jsonify({"error": f"Error al procesar el archivo: {str(e)}"}), 500


@app.route('/api/crear-match', methods=['POST'])
def crear_match():
    data = request.json
    ramo_act = data.get('ramo_act')
    ra_act = data.get('ra_act')
    ramo_pre = data.get('ramo_pre')
    ra_pre = data.get('ra_pre')
    nueva_sev = data.get('severidad')
    
    # Mapeo matemático del score
    if nueva_sev == "alto": score = 100.0
    elif nueva_sev == "medio": score = 79.0
    elif nueva_sev == "bajo": score = 59.0
    else: score = 0.0

    # Lógica UPSERT (Update o Insert)
    enlace_existente = False
    for link in enlaces_semanticos:
        # Si ya existe un enlace evaluado para este RA Actual contra este Ramo Prerrequisito
        if link["ramo_act"] == ramo_act and link["ra_act"] == ra_act and link["ramo_pre"] == ramo_pre:
            link["ra_pre"] = ra_pre
            link["score"] = score
            link["severidad"] = nueva_sev
            enlace_existente = True
            break
            
    # Si la IA nunca los cruzó (ej. no eran prerrequisitos oficiales), lo agregamos como nuevo
    if not enlace_existente:
        enlaces_semanticos.append({
            "ramo_act": ramo_act,
            "ra_act": ra_act,
            "ramo_pre": ramo_pre,
            "ra_pre": ra_pre,
            "score": score,
            "severidad": nueva_sev
        })

    return jsonify({"exito": True, "mensaje": "Enlace creado correctamente"})  

 
if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=True)