const pptxgen = require("pptxgenjs");
const { applyTheme } = require("/Users/alessandro/.claude/skills/synced/b57436ce-4092-4e34-8bd7-20e8a94e2d39_cc6fbbe2-58be-4eb7-af25-a57077e346f2/pptx/scripts/apply_theme.js");

const IMG = "/Users/alessandro/Project/UNCP/sdn-ddos-multiclass-detection/expo/img";
const TOPO = "/Users/alessandro/Project/UNCP/sdn-ddos-multiclass-detection/paper/figures/topologia-campus-uncp.png";
const OUT = "/Users/alessandro/Project/UNCP/sdn-ddos-multiclass-detection/expo/expo-fis-campus-ddos.pptx";

const THEME = {
  name: "UNCP FIS",
  headFontFace: "Arial",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "12261C",
    lt1: "FFFFFF",
    dk2: "135539",
    lt2: "E7F0EA",
    accent1: "135539",
    accent2: "C6A15B",
    accent3: "1B4D38",
    accent4: "8C2F2F",
    accent5: "3E5C4C",
    accent6: "F4F7F5",
    hlink: "135539",
    folHlink: "0E3324",
  },
};

async function main() {
  const pres = new pptxgen();
  pres.defineLayout({ name: "WIDE", width: 13.333, height: 7.5 });
  pres.layout = "WIDE";
  pres.title = "De un solo ataque a un campus";
  pres.author = "Facultad de Ingenieria de Sistemas, UNCP";
  pres.subject = "Exposicion del banco de pruebas Campus-DDoS-SDN";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };

  const C = pres.SchemeColor;

  function ph(name, type, opts) {
    return {
      placeholder: {
        text: " ",
        options: Object.assign({ name: name, type: type, margin: 0 }, opts),
      },
    };
  }

  pres.defineSlideMaster({
    title: "portada",
    background: { color: "12261C" },
    objects: [
      ph("title", "title", {
        x: 0.55, y: 4.55, w: 12.2, h: 0.85,
        fontFace: "Arial", fontSize: 34, bold: true, color: "FFFFFF", align: "left",
      }),
      ph("body", "body", {
        x: 0.55, y: 5.55, w: 10.2, h: 1.15,
        fontFace: "Calibri", fontSize: 18, color: "E7F0EA",
      }),
    ],
  });

  pres.defineSlideMaster({
    title: "contenido",
    background: { color: "FFFFFF" },
    slideNumber: { x: 12.35, y: 7.08, w: 0.5, h: 0.28, color: "5C6B62", fontFace: "Calibri", fontSize: 12 },
    objects: [
      {
        text: {
          text: "Universidad Nacional del Centro del Perú  |  Facultad de Ingeniería de Sistemas",
          options: {
            x: 0.55, y: 7.08, w: 8.5, h: 0.28,
            fontFace: "Calibri", fontSize: 12, color: "5C6B62", margin: 0,
          },
        },
      },
      {
        image: {
          x: 11.95, y: 0.18, w: 0.72, h: 0.61,
          path: IMG + "/escudo-uncp.png",
        },
      },
      ph("title", "title", {
        x: 0.55, y: 0.3, w: 11.1, h: 0.7,
        fontFace: "Arial", fontSize: 29, bold: true, color: "135539", align: "left",
      }),
    ],
  });

  pres.defineSlideMaster({
    title: "foto",
    background: { color: "FFFFFF" },
    objects: [
      ph("title", "title", {
        x: 7.05, y: 0.7, w: 5.7, h: 1.45,
        fontFace: "Arial", fontSize: 29, bold: true, color: "135539", align: "left",
      }),
      ph("body", "body", {
        x: 7.05, y: 2.4, w: 5.7, h: 4.2,
        fontFace: "Calibri", fontSize: 18, color: "12261C",
      }),
    ],
  });

  pres.defineSlideMaster({
    title: "cierre",
    background: { color: "12261C" },
    objects: [
      ph("title", "title", {
        x: 0.6, y: 4.45, w: 12.0, h: 0.85,
        fontFace: "Arial", fontSize: 32, bold: true, color: "FFFFFF", align: "left",
      }),
      ph("body", "body", {
        x: 0.6, y: 5.45, w: 11.2, h: 1.2,
        fontFace: "Calibri", fontSize: 18, color: "E7F0EA",
      }),
    ],
  });


  function tx(slide, text, x, y, w, h, extra) {
    slide.addText(text, Object.assign({
      x: x, y: y, w: w, h: h,
      fontSize: 18, color: C.dk1, margin: 0, isTextBox: true,
    }, extra || {}));
  }

  pres.addSection({ title: "El camino" });

  const s1 = pres.addSlide({ masterName: "portada", sectionTitle: "El camino" });
  s1.addImage({ path: IMG + "/escudo-uncp.png", x: 0.55, y: 0.45, w: 0.95, h: 0.81 });
  s1.addText("Campus-DDoS-SDN", { placeholder: "title" });
  s1.addText("Diseño y evaluación de un banco de pruebas para detección DDoS multiclase\nFacultad de Ingeniería de Sistemas", { placeholder: "body" });
  s1.addNotes("Abrir diciendo que esta vez no vamos a mostrar el campus: vamos a mostrar cómo se hizo. Seis pasos, con las tablas y los gráficos de la corrida de 120 segundos.");

  const sProblema = pres.addSlide({ masterName: "contenido", sectionTitle: "El camino" });
  sProblema.addText("Problema de investigación", { placeholder: "title" });
  tx(sProblema, "Un F1 alto con un solo ataque y archivos separados no demuestra que el detector encuentre al atacante mientras el alumno sigue usando el mismo portal.", 0.55, 1.3, 12.2, 1.15, { fontFace: "Arial", fontSize: 23, bold: true });
  tx(sProblema, "Vacíos identificados", 0.55, 2.85, 5.7, 0.45, { fontFace: "Arial", fontSize: 20, bold: true, color: C.accent1 });
  tx(sProblema, "01  Más de un vector DDoS\n02  Tráfico benigno dentro del ataque\n03  Una corrida que pueda repetirse\n04  Medir si el portal realmente se cae", 0.55, 3.45, 5.7, 2.4, { fontSize: 19 });
  tx(sProblema, "Pregunta de investigación", 7.0, 2.85, 5.7, 0.45, { fontFace: "Arial", fontSize: 20, bold: true, color: C.accent1 });
  tx(sProblema, "¿Las estadísticas del flujo, sin IP, puertos ni hora, separan tráfico benigno y cuatro ataques en un laboratorio que el modelo no vio?", 7.0, 3.45, 5.7, 2.2, { fontSize: 21 });
  sProblema.addNotes("Esta es la motivación. No decir que el artículo inicial está mal; decir que resuelve un caso más pequeño. Nuestra pregunta agrega mezcla, reproducibilidad y prueba en otro laboratorio.");

  const sObjetivo = pres.addSlide({ masterName: "contenido", sectionTitle: "El camino" });
  sObjetivo.addText("Objetivos e hipótesis", { placeholder: "title" });
  tx(sObjetivo, "Objetivo general", 0.55, 1.25, 5.8, 0.42, { fontFace: "Arial", fontSize: 20, bold: true, color: C.accent1 });
  tx(sObjetivo, "Implementar y evaluar en Docker un banco SDN reproducible para detectar cuatro ataques contra un portal de campus.", 0.55, 1.8, 5.8, 1.5, { fontSize: 19 });
  tx(sObjetivo, "Objetivos específicos", 0.55, 3.55, 5.8, 0.42, { fontFace: "Arial", fontSize: 20, bold: true, color: C.accent1 });
  tx(sObjetivo, "Modelar la red · capturar tráfico mixto · etiquetar por emisor · medir el portal y Docker · probar fuera del entrenamiento.", 0.55, 4.1, 5.8, 1.7, { fontSize: 19 });
  tx(sObjetivo, "Hipótesis de trabajo", 7.0, 1.25, 5.7, 0.42, { fontFace: "Arial", fontSize: 20, bold: true, color: C.accent1 });
  tx(sObjetivo, "Las características de tamaño, duración y tasa del flujo permiten superar 0,90 de F1 macro en el laboratorio retenido.", 7.0, 1.8, 5.7, 1.7, { fontFace: "Arial", fontSize: 22, bold: true });
  tx(sObjetivo, "Alcance", 7.0, 4.0, 5.7, 0.42, { fontFace: "Arial", fontSize: 20, bold: true, color: C.accent1 });
  tx(sObjetivo, "Primero se contrasta en casa. La captura real de la UNCP es la fase propuesta y requiere autorización.", 7.0, 4.55, 5.7, 1.4, { fontSize: 19 });
  sObjetivo.addNotes("Separar hipótesis y alcance. El valor 0,90 se fijó como umbral de trabajo. La corrida de casa da 0,979. El campus todavía no se ha medido.");

  const sAntecedente = pres.addSlide({ masterName: "contenido", sectionTitle: "El camino" });
  sAntecedente.addText("Del artículo inicial a esta propuesta", { placeholder: "title" });
  const hComp = { fill: { color: "135539" }, color: "FFFFFF", bold: true, align: "left", valign: "middle", margin: [8, 10, 8, 12] };
  const cOld = { fill: { color: "F4F7F5" }, color: "3E5C4C", align: "left", valign: "middle", margin: [8, 10, 8, 12] };
  const cNew = { fill: { color: "E7F0EA" }, color: "12261C", align: "left", valign: "middle", margin: [8, 10, 8, 12] };
  sAntecedente.addTable([
    [{ text: "ICMP-Flood-SDN", options: hComp }, { text: "Campus-DDoS-SDN", options: hComp }],
    [{ text: "Un ataque: ICMP", options: cOld }, { text: "SYN, HTTP, Slowloris e ICMP", options: cNew }],
    [{ text: "Navegación real, depende de internet", options: cOld }, { text: "Portal interno, corrida repetible", options: cNew }],
    [{ text: "Capturas benignas y de ataque separadas", options: cOld }, { text: "Alumno y atacante dentro del mismo pcap", options: cNew }],
    [{ text: "Evaluación del clasificador", options: cOld }, { text: "Clasificador + sonda HTTP + recursos Docker", options: cNew }],
    [{ text: "≈99,9 % en su conjunto", options: cOld }, { text: "0,979 F1 macro en un laboratorio retenido", options: cNew }],
  ], {
    x: 0.55, y: 1.35, w: 12.2, h: 5.15, colW: [5.7, 6.5],
    border: [{ pt: 0, color: "FFFFFF" }, { pt: 0, color: "FFFFFF" }, { pt: 0, color: "FFFFFF" }, { pt: 0, color: "FFFFFF" }],
    fontFace: "Calibri", fontSize: 16, rowH: 0.76,
  });
  sAntecedente.addNotes("El 99,9 por ciento del antecedente no se compara directamente con 0,979. Cambian las clases, la mezcla y la partición. La mejora principal no es un número mayor: es una prueba más reproducible y más exigente.");

  const sAlcance = pres.addSlide({ masterName: "contenido", sectionTitle: "El camino" });
  sAlcance.addText("Qué está hecho y qué se propone", { placeholder: "title" });
  tx(sAlcance, "TRABAJO REALIZADO", 0.55, 1.35, 5.8, 0.5, { fontFace: "Arial", fontSize: 20, bold: true, color: C.accent1 });
  tx(sAlcance, "Topología Docker\nCinco escenarios de 120 s\n40.877 flujos etiquetados\nBosque probado en Agrarias\nF1 macro 0,979", 0.55, 2.0, 5.8, 3.2, { fontSize: 21 });
  tx(sAlcance, "FASE PROPUESTA", 7.0, 1.35, 5.7, 0.5, { fontFace: "Arial", fontSize: 20, bold: true, color: "8C2F2F" });
  tx(sAlcance, "Captura Wireshark autorizada\nSolo tráfico benigno real\nAnonimización de direcciones\nDataset híbrido\nComparación casa vs campus", 7.0, 2.0, 5.7, 3.2, { fontSize: 21 });
  tx(sAlcance, "Los ataques permanecen dentro de Docker. No se atacará la red de la UNCP.", 0.55, 5.75, 12.2, 0.55, { fontSize: 18, bold: true, color: "8C2F2F", align: "center" });
  sAlcance.addNotes("Esta diapositiva evita confusiones. La columna izquierda son resultados. La derecha es la propuesta que se presentará al encargado. No prometer un escaneo que todavía no ocurrió.");

  const s2 = pres.addSlide({ masterName: "contenido", sectionTitle: "El camino" });
  s2.addText("Metodología general", { placeholder: "title" });
  const pasos = [
    ["1", "Docker", "Un comando levanta la red, el ataque y la captura."],
    ["2", "Sonda", "Cada segundo se anota si el portal abre y cuánto tarda."],
    ["3", "Flujos", "El pcap se vuelve CSV. TCP con CICFlowMeter, ICMP aparte."],
    ["4", "Etiqueta", "La IP de origen dice si el flujo es alumno o ataque."],
    ["5", "Limpieza", "Se botan IP, puertos y hora, para que el modelo no memorice."],
    ["6", "Prueba", "Agrarias no entra al entrenamiento. Ahí se mide el F1."],
  ];
  pasos.forEach((row, i) => {
    const col = i < 3 ? 0 : 1;
    const fila = i % 3;
    const x = 0.55 + col * 6.35;
    const y = 1.35 + fila * 1.75;
    tx(s2, row[0], x, y, 0.7, 0.55, { fontFace: "Arial", fontSize: 25, bold: true, color: C.accent1 });
    tx(s2, row[1], x + 0.85, y, 5.1, 0.45, { fontFace: "Arial", fontSize: 20, bold: true });
    tx(s2, row[2], x + 0.85, y + 0.5, 5.1, 0.85, { fontSize: 16, color: "3E5C4C" });
  });
  s2.addNotes("Recorrer los seis números. Decir que el resto de la exposición es uno por diapositiva, con lo que salió de la corrida, no con un esquema inventado.");

  pres.addSection({ title: "La captura" });

  const s3 = pres.addSlide({ masterName: "contenido", sectionTitle: "La captura" });
  s3.addText("Entorno de experimentación", { placeholder: "title" });
  s3.addShape(pres.shapes.RECTANGLE, {
    x: 0.55, y: 1.3, w: 12.2, h: 2.15,
    fill: { color: "F4F7F5" }, line: { color: "D5E0D9", pt: 1 },
  });
  tx(s3, "bash scripts/docker/run_scenario.sh all 120", 0.8, 1.5, 11.7, 0.45, {
    fontFace: "Courier New", fontSize: 19, color: "12261C",
  });
  tx(s3, "bash scripts/docker/run_scenario.sh convert", 0.8, 2.05, 11.7, 0.4, {
    fontFace: "Courier New", fontSize: 19, color: "12261C",
  });
  tx(s3, "python notebooks/analisis_completo.py", 0.8, 2.55, 11.7, 0.4, {
    fontFace: "Courier New", fontSize: 19, color: "135539", bold: true,
  });
  tx(s3, "La imagen se llama ataque-sdn. Es Ubuntu 24.04, privilegiada, con 6 CPU y 8 GB. Adentro arrancan Open vSwitch en userspace, Ryu 4.34 y Mininet. El ataque no tiene ruta hacia la red de la universidad.", 0.55, 3.7, 12.2, 1.15, { fontSize: 18 });
  tx(s3, "Cada escenario deja el pcap, la sonda del alumno y un CSV de docker stats: CPU, memoria y red del contenedor, cada dos segundos.", 0.55, 5.0, 12.2, 1.1, { fontSize: 18 });
  s3.addNotes("Mostrar los tres comandos. El tercero es el que entrena. Aclarar que docker stats es la foto del contenedor: no hace falta abrir Docker Desktop para ver el costo, quedó guardado en data/metrics.");

  const s4 = pres.addSlide({ masterName: "contenido", sectionTitle: "La captura" });
  s4.addText("Uso de recursos del contenedor", { placeholder: "title" });
  s4.addImage({ path: IMG + "/cpu-docker.png", x: 0.4, y: 1.2, w: 8.3, h: 5.35 });
  tx(s4, "100 % es un núcleo. El contenedor tiene seis.", 8.85, 1.6, 3.9, 1.3, { fontSize: 18 });
  tx(s4, "Slowloris sostuvo unos cinco núcleos. Mantiene conexiones abiertas y el emulador se queda trabajando.", 8.85, 3.15, 3.9, 1.7, { fontSize: 18 });
  tx(s4, "SYN, ICMP y el baseline andan cerca de un núcleo. El costo grande no es el flood: es Slowloris.", 8.85, 5.05, 3.9, 1.5, { fontSize: 18 });
  s4.addNotes("Este gráfico sale de los CSV de docker stats de la corrida. Slowloris promedió 523 por ciento. Los otros escenarios se quedan entre 23 y 50. Sirve para decir que el banco cabe en una PC de 8 núcleos, y que el caso caro es el de conexiones abiertas.");

  const s5 = pres.addSlide({ masterName: "contenido", sectionTitle: "La captura" });
  s5.addText("Disponibilidad y latencia del portal", { placeholder: "title" });
  tx(s5, "Un alumno de Salud pide el portal una vez por segundo, durante 120 segundos. Esto no es el modelo: es si la página abre.", 0.55, 1.15, 12.2, 0.7, { fontSize: 16, color: "3E5C4C" });
  const head = { fill: { color: "135539" }, color: "FFFFFF", bold: true, align: "center", valign: "middle", margin: 6 };
  const cell = { fill: { color: "F4F7F5" }, color: "12261C", align: "center", valign: "middle", margin: 6 };
  const cellL = { fill: { color: "FFFFFF" }, color: "12261C", align: "left", valign: "middle", margin: [6, 8, 6, 10] };
  s5.addTable([
    [
      { text: "Escenario", options: head },
      { text: "Abre", options: head },
      { text: "Falla", options: head },
      { text: "Latencia", options: head },
      { text: "Paquetes/s", options: head },
      { text: "Qué se siente", options: head },
    ],
    [
      { text: "Baseline", options: cellL },
      { text: "120", options: cell },
      { text: "0", options: cell },
      { text: "407 ms", options: cell },
      { text: "111", options: cell },
      { text: "La página normal", options: cellL },
    ],
    [
      { text: "SYN", options: cellL },
      { text: "120", options: cell },
      { text: "0", options: cell },
      { text: "404 ms", options: cell },
      { text: "466", options: cell },
      { text: "Más ruido, la página sigue", options: cellL },
    ],
    [
      { text: "HTTP flood", options: cellL },
      { text: "120", options: cell },
      { text: "0", options: cell },
      { text: "564 ms", options: cell },
      { text: "386", options: cell },
      { text: "Tarda más", options: cellL },
    ],
    [
      { text: "Slowloris", options: cellL },
      { text: "1", options: cell },
      { text: "117", options: cell },
      { text: "403 ms", options: cell },
      { text: "86", options: cell },
      { text: "Deja de abrir", options: cellL },
    ],
    [
      { text: "ICMP", options: cellL },
      { text: "120", options: cell },
      { text: "0", options: cell },
      { text: "404 ms", options: cell },
      { text: "271", options: cell },
      { text: "Más ruido, la página sigue", options: cellL },
    ],
  ], {
    x: 0.55, y: 2.05, w: 12.2, h: 4.5,
    colW: [2.1, 1.3, 1.3, 1.7, 1.8, 4.0],
    border: [
      { pt: 0, color: "FFFFFF" },
      { pt: 0, color: "FFFFFF" },
      { pt: 0, color: "FFFFFF" },
      { pt: 0, color: "FFFFFF" },
    ],
    fontFace: "Calibri", fontSize: 15, rowH: 0.62,
  });
  s5.addNotes("Leer la fila de Slowloris despacio: un solo éxito de 118 intentos, y casi no suben los paquetes. SYN es el que más paquetes mete y la página sigue en 404 milisegundos. La latencia de Slowloris es la del único intento que sí abrió.");

  const s6 = pres.addSlide({ masterName: "contenido", sectionTitle: "La captura" });
  s6.addText("Topología del banco de pruebas", { placeholder: "title" });
  s6.addImage({ path: TOPO, x: 0.35, y: 1.15, w: 8.9, h: 5.0 });
  tx(s6, "Cinco laboratorios. En cada uno, 4 alumnos y 2 PCs infectadas.", 9.45, 1.5, 3.4, 1.5, { fontSize: 16 });
  tx(s6, "El C2 está fuera del campus y solo da la orden. Quien ataca es la PC infectada.", 9.45, 3.2, 3.4, 1.5, { fontSize: 16 });
  tx(s6, "La víctima es el portal, 10.0.0.10. No el controlador.", 9.45, 4.9, 3.4, 1.3, { fontSize: 16 });
  s6.addNotes("Una sola pasada por el dibujo. Azul alumno, rojo infectado. Agrarias es la de la derecha: esa no se usa para entrenar.");

  pres.addSection({ title: "Los datos" });

  const s7 = pres.addSlide({ masterName: "contenido", sectionTitle: "Los datos" });
  s7.addText("Construcción del conjunto de datos", { placeholder: "title" });
  s7.addImage({ path: IMG + "/flujos.png", x: 0.35, y: 1.2, w: 7.6, h: 5.2 });
  tx(s7, "40.877 flujos en total", 8.15, 1.45, 4.6, 0.45, { fontFace: "Arial", fontSize: 20, bold: true });
  tx(s7, "TCP y UDP los cuenta CICFlowMeter. ICMP no pasa ese filtro.", 8.15, 2.15, 4.6, 1.15, { fontSize: 16 });
  tx(s7, "El agrupador ICMP cierra el flujo a los 10 segundos. Si no, cada infectada dejaría una sola fila.", 8.15, 3.45, 4.6, 1.4, { fontSize: 16 });
  tx(s7, "Aun así ICMP queda chico: 120 flujos en todo el conjunto. SYN se lleva 23.539.", 8.15, 5.05, 4.6, 1.3, { fontSize: 16 });
  s7.addNotes("Señalar la barra verde de SYN: por eso después hay que pesar las clases. La franja gris de cada barra es el alumno, que sigue dentro del mismo archivo. En ICMP la franja de ataque casi no se ve.");

  const s8 = pres.addSlide({ masterName: "contenido", sectionTitle: "Los datos" });
  s8.addText("Estrategia de etiquetado", { placeholder: "title" });
  tx(s8, "Alumno y ataque viajan en el mismo pcap. Si se etiquetara el archivo entero, el alumno quedaría marcado como ataque.", 0.55, 1.2, 12.2, 0.9, { fontSize: 18 });
  const reglaH = { fill: { color: "135539" }, color: "FFFFFF", bold: true, align: "left", valign: "middle", margin: [8, 10, 8, 12] };
  const reglaA = { fill: { color: "F4F7F5" }, color: "12261C", align: "left", valign: "middle", margin: [8, 10, 8, 12] };
  const reglaB = { fill: { color: "E7F0EA" }, color: "12261C", align: "left", valign: "middle", margin: [8, 10, 8, 12] };
  s8.addTable([
    [
      { text: "Quién envía", options: reglaH },
      { text: "Escenario", options: reglaH },
      { text: "Etiqueta", options: reglaH },
    ],
    [
      { text: "Alumno, portal o cualquier otra IP", options: reglaA },
      { text: "Cualquiera", options: reglaA },
      { text: "BENIGN", options: reglaB },
    ],
    [
      { text: "PC infectada", options: reglaA },
      { text: "Baseline", options: reglaA },
      { text: "BENIGN  (todavía navega)", options: reglaB },
    ],
    [
      { text: "PC infectada", options: reglaA },
      { text: "SYN, HTTP, Slowloris o ICMP", options: reglaA },
      { text: "El nombre del ataque", options: reglaB },
    ],
  ], {
    x: 0.55, y: 2.3, w: 12.2, h: 3.4,
    colW: [5.2, 3.8, 3.2],
    border: [
      { pt: 0, color: "FFFFFF" },
      { pt: 0, color: "FFFFFF" },
      { pt: 0, color: "FFFFFF" },
      { pt: 0, color: "FFFFFF" },
    ],
    fontFace: "Calibri", fontSize: 16, rowH: 0.78,
  });
  tx(s8, "La lista de infectadas está en el JSON que se guarda junto al pcap.", 0.55, 5.95, 12.2, 0.5, { fontSize: 16, color: "3E5C4C" });
  s8.addNotes("Poner un ejemplo oral: 10.1.0.20 es infectada de Salud. En el baseline su flujo es BENIGN. En synflood, el mismo host pasa a synflood. 10.1.0.10, el alumno de al lado, sigue BENIGN en los dos archivos.");

  const s9 = pres.addSlide({ masterName: "contenido", sectionTitle: "Los datos" });
  s9.addText("Preprocesamiento y control de fuga de información", { placeholder: "title" });
  const fuera = [
    ["IP de origen y de destino", "Si se quedan, el bosque aprende la dirección de la infectada, no el flujo."],
    ["Puerto de origen y de destino", "El portal siempre es el puerto 80. Eso no distingue un ataque."],
    ["Marca de tiempo", "El orden de la captura no es un rasgo del tráfico."],
    ["Infinitos, vacíos y columnas quietas", "Pasan a cero, o se quitan si en el entrenamiento no cambian."],
  ];
  fuera.forEach((row, i) => {
    const y = 1.3 + i * 1.3;
    tx(s9, row[0], 0.55, y, 12.2, 0.42, { fontFace: "Arial", fontSize: 20, bold: true });
    tx(s9, row[1], 0.55, y + 0.46, 12.2, 0.55, { fontSize: 18, color: "3E5C4C" });
  });
  s9.addNotes("Esta es la diapositiva de la limpieza. Repetir: el modelo no ve direcciones. Lo que ve son tamaños, ritmos y duraciones del flujo. Si alguien pregunta por qué el F1 es alto, la respuesta empieza aquí: no es porque memorizó las IP.");

  pres.addSection({ title: "El modelo" });

  const s10 = pres.addSlide({ masterName: "contenido", sectionTitle: "El modelo" });
  s10.addText("Separación de entrenamiento y prueba", { placeholder: "title" });
  tx(s10, "32.784", 0.55, 1.6, 5.5, 1.15, { fontFace: "Arial", fontSize: 50, bold: true, color: C.accent1 });
  tx(s10, "flujos para entrenar\nSalud, Ingenierías, Empresariales, Sociales", 0.55, 2.85, 5.8, 1.1, { fontSize: 18 });
  tx(s10, "8.091", 7.1, 1.6, 5.5, 1.15, { fontFace: "Arial", fontSize: 50, bold: true, color: C.accent1 });
  tx(s10, "flujos para probar\nsolo Ciencias Agrarias, prefijo 10.5", 7.1, 2.85, 5.5, 1.1, { fontSize: 18 });
  tx(s10, "Un corte al azar metería flujos del mismo laboratorio en los dos lados. El número saldría más alto y no diría si el modelo viaja a otra área.", 0.55, 4.4, 12.2, 1.1, { fontSize: 18 });
  tx(s10, "Bosque aleatorio, 200 árboles, peso por clase. SYN es enorme: sin ese peso, el modelo se inclinaría a llamarlo todo SYN.", 0.55, 5.6, 12.2, 1.0, { fontSize: 18 });
  s10.addNotes("Escribir en la pizarra, si hace falta, 10.1 a 10.4 entrenan y 10.5 prueba. El peso por clase se llama balanced_subsample. No hace falta el nombre en inglés salvo que pregunten.");

  const s11 = pres.addSlide({ masterName: "contenido", sectionTitle: "El modelo" });
  s11.addText("Desempeño por clase", { placeholder: "title" });
  tx(s11, "F1 macro 0,979 en Agrarias. Binario, benigno contra ataque, 0,970.", 0.55, 1.15, 12.2, 0.5, { fontSize: 18, color: "3E5C4C" });
  const rh = { fill: { color: "135539" }, color: "FFFFFF", bold: true, align: "center", valign: "middle", margin: 6 };
  const rc = { fill: { color: "F4F7F5" }, color: "12261C", align: "center", valign: "middle", margin: 6 };
  const rl = { fill: { color: "FFFFFF" }, color: "12261C", align: "left", valign: "middle", margin: [6, 8, 6, 10] };
  s11.addTable([
    [
      { text: "Clase", options: rh },
      { text: "Precisión", options: rh },
      { text: "Recall", options: rh },
      { text: "F1", options: rh },
      { text: "Flujos en la prueba", options: rh },
      { text: "Lectura", options: rh },
    ],
    [
      { text: "BENIGN", options: rl },
      { text: "0,956", options: rc },
      { text: "0,949", options: rc },
      { text: "0,953", options: rc },
      { text: "1.775", options: rc },
      { text: "Se distingue", options: rl },
    ],
    [
      { text: "HTTP flood", options: rl },
      { text: "0,939", options: rc },
      { text: "0,947", options: rc },
      { text: "0,943", options: rc },
      { text: "1.458", options: rc },
      { text: "Se distingue", options: rl },
    ],
    [
      { text: "Slowloris", options: rl },
      { text: "1,000", options: rc },
      { text: "1,000", options: rc },
      { text: "1,000", options: rc },
      { text: "126", options: rc },
      { text: "Se distingue", options: rl },
    ],
    [
      { text: "SYN flood", options: rl },
      { text: "1,000", options: rc },
      { text: "1,000", options: rc },
      { text: "1,000", options: rc },
      { text: "4.708", options: rc },
      { text: "Se distingue", options: rl },
    ],
    [
      { text: "ICMP", options: rl },
      { text: "1,000", options: rc },
      { text: "1,000", options: rc },
      { text: "1,000", options: rc },
      { text: "24", options: rc },
      { text: "No se afirma", options: rl },
    ],
  ], {
    x: 0.55, y: 1.8, w: 12.2, h: 4.6,
    colW: [2.2, 1.7, 1.6, 1.5, 2.5, 2.7],
    border: [
      { pt: 0, color: "FFFFFF" },
      { pt: 0, color: "FFFFFF" },
      { pt: 0, color: "FFFFFF" },
      { pt: 0, color: "FFFFFF" },
    ],
    fontFace: "Calibri", fontSize: 15, rowH: 0.64,
  });
  s11.addNotes("ICMP va al final a propósito. El 1,000 con 24 flujos no se dice como logro. Las otras cuatro clases sí se pueden defender: tienen muestras y la página cuenta una historia distinta en cada una.");

  const s12 = pres.addSlide({ masterName: "contenido", sectionTitle: "El modelo" });
  s12.addText("Importancia de características", { placeholder: "title" });
  s12.addImage({ path: IMG + "/importancia.png", x: 0.4, y: 1.15, w: 7.8, h: 5.4 });
  tx(s12, "No mira direcciones. Mira el tamaño de lo que va hacia el portal.", 8.4, 1.5, 4.4, 1.4, { fontSize: 18 });
  tx(s12, "La primera columna es el tamaño medio del segmento de ida. Después vienen la media y el máximo del paquete de ida.", 8.4, 3.15, 4.4, 1.7, { fontSize: 18 });
  tx(s12, "Tiene sentido: un SYN casi no lleva datos. Un GET del alumno sí. Slowloris mantiene poco y lento.", 8.4, 5.05, 4.4, 1.5, { fontSize: 18 });
  s12.addNotes("Traducir los nombres si el público no los usa. fwd es hacia el portal. El modelo separa por forma del flujo, que es lo que queríamos después de quitar la IP.");

  pres.addSection({ title: "Resultados" });

  const s13 = pres.addSlide({ masterName: "contenido", sectionTitle: "Resultados" });
  s13.addText("Resultados preliminares", { placeholder: "title" });
  tx(s13, "0,979", 0.55, 1.25, 5.4, 1.15, { fontFace: "Arial", fontSize: 54, bold: true, color: C.accent1 });
  tx(s13, "F1 macro. Es la base que ya está medida.\nTodavía no es el escaneo del campus.", 0.55, 2.5, 5.6, 1.15, { fontSize: 18 });
  const hechosCasa = [
    ["La página", "Solo Slowloris la tumba: 1 de 118 abre. HTTP la pasa de 407 ms a 564 ms."],
    ["El modelo", "BENIGN, HTTP, Slowloris y SYN se separan en Agrarias, sin usar la IP."],
    ["La mezcla", "El alumno sigue dentro del mismo archivo. 40.877 flujos, 120 segundos por escenario."],
  ];
  hechosCasa.forEach((row, i) => {
    const y = 1.35 + i * 1.7;
    tx(s13, row[0], 6.5, y, 6.2, 0.42, { fontFace: "Arial", fontSize: 20, bold: true });
    tx(s13, row[1], 6.5, y + 0.48, 6.2, 0.95, { fontSize: 16, color: "3E5C4C" });
  });
  s13.addNotes("Decir en voz alta que esto salió de la corrida en casa, con Docker, no de la red de la UNCP. Es la base con la que se va a proponer el permiso. El 0,979 ya está medido. El escaneo real viene después.");

  pres.addSection({ title: "Limitaciones" });

  const s14 = pres.addSlide({ masterName: "contenido", sectionTitle: "Limitaciones" });
  s14.addText("Limitaciones", { placeholder: "title" });
  const limites = [
    ["Es una prueba en casa", "Los alumnos están emulados. Sirve para proponer el trabajo. No reemplaza el escaneo que se pedirá."],
    ["ICMP no se afirma", "En Agrarias hay 24 flujos. El F1 de 1,000 de esa clase no se presenta como resultado."],
    ["No corre en vivo", "El bosque lee flujos ya capturados. No está dentro de Ryu ni corta el ataque."],
    ["Falta el fondo real", "El pipeline híbrido está escrito. Entra cuando el encargado entregue los pcap autorizados."],
  ];
  limites.forEach((row, i) => {
    const y = 1.25 + i * 1.4;
    tx(s14, row[0], 0.55, y, 12.2, 0.42, { fontFace: "Arial", fontSize: 20, bold: true, color: C.accent1 });
    tx(s14, row[1], 0.55, y + 0.46, 12.2, 0.7, { fontSize: 18 });
  });
  s14.addNotes("No esconder que falta el campus. Esa es la razón de la propuesta. La limitación principal es el alcance: casa ahora, red autorizada después. ICMP y el clasificador fuera de Ryu se dicen igual.");

  pres.addSection({ title: "Propuesta" });

  const sPropuesta = pres.addSlide({ masterName: "contenido", sectionTitle: "Propuesta" });
  sPropuesta.addText("Fase 2: validación autorizada", { placeholder: "title" });
  const propuesta = [
    ["01", "Capturar", "Uno a tres pcap benignos, de 10 a 30 minutos, en un segmento que defina el encargado."],
    ["02", "Anonimizar", "Cambiar las direcciones antes de entrenar. No publicar usuarios ni contenido."],
    ["03", "Mezclar", "Unir ese fondo benigno con ataques que siguen ejecutándose solo dentro de Docker."],
    ["04", "Comparar", "Repetir el holdout y reportar cuánto cambia el F1 respecto de la prueba en casa."],
  ];
  propuesta.forEach((row, i) => {
    const y = 1.25 + i * 1.35;
    tx(sPropuesta, row[0], 0.55, y, 0.8, 0.48, { fontFace: "Arial", fontSize: 23, bold: true, color: C.accent1 });
    tx(sPropuesta, row[1], 1.55, y, 2.2, 0.45, { fontFace: "Arial", fontSize: 19, bold: true });
    tx(sPropuesta, row[2], 3.9, y, 8.8, 0.85, { fontSize: 18 });
  });
  tx(sPropuesta, "Restricción: ninguna inundación se ejecuta contra la red real.", 0.55, 6.35, 12.2, 0.45, { fontSize: 18, bold: true, color: "8C2F2F", align: "center" });
  sPropuesta.addNotes("Esta es la solicitud concreta. El encargado entrega tráfico benigno, no recibe ataques. El equipo anonimiza, mezcla offline con los ataques Docker y compara contra el resultado 0,979.");

  pres.addSection({ title: "Conclusiones" });

  const s15 = pres.addSlide({ masterName: "contenido", sectionTitle: "Conclusiones" });
  s15.addText("Conclusiones", { placeholder: "title" });
  const conclusiones = [
    ["1", "La prueba en casa ya distingue alumno y ataque en la misma captura, sin memorizar la IP."],
    ["2", "El portal solo se cae con Slowloris. SYN e ICMP suben paquetes y la página sigue."],
    ["3", "El F1 de 0,979 en Agrarias es la cifra con la que se propone el siguiente paso."],
    ["4", "Ese paso es el escaneo autorizado. El ataque de la simulación no sale del contenedor."],
  ];
  conclusiones.forEach((row, i) => {
    const y = 1.3 + i * 1.35;
    tx(s15, row[0], 0.55, y, 0.7, 0.55, { fontFace: "Arial", fontSize: 25, bold: true, color: C.accent1 });
    tx(s15, row[1], 1.45, y + 0.05, 11.2, 0.9, { fontSize: 20 });
  });
  s15.addNotes("Cerrar las cuatro frases sin agregar un número nuevo. La uno y la dos son lo que ya se vio en casa. La tres es la cifra de la propuesta. La cuatro es el compromiso: se pide permiso para el fondo real, y el ataque sigue dentro de Docker.");

  const sReferencias = pres.addSlide({ masterName: "contenido", sectionTitle: "Conclusiones" });
  sReferencias.addText("Fuentes principales", { placeholder: "title" });
  tx(sReferencias, "Kumar, S.; Gupta, S. (2026)", 0.55, 1.3, 12.2, 0.42, { fontFace: "Arial", fontSize: 19, bold: true, color: C.accent1 });
  tx(sReferencias, "ICMP-Flood-SDN: A Python based machine learning application for ICMP flood DDoS attack detection in software defined networks. Software Impacts 27, 100819.", 0.55, 1.8, 12.2, 0.95, { fontSize: 17 });
  tx(sReferencias, "Sharafaldin, I.; Lashkari, A.; Ghorbani, A. (2018)", 0.55, 3.0, 12.2, 0.42, { fontFace: "Arial", fontSize: 19, bold: true, color: C.accent1 });
  tx(sReferencias, "Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization. ICISSP. Referencia de CICFlowMeter.", 0.55, 3.5, 12.2, 0.85, { fontSize: 17 });
  tx(sReferencias, "Kreutz, D. et al. (2015)", 0.55, 4.7, 12.2, 0.42, { fontFace: "Arial", fontSize: 19, bold: true, color: C.accent1 });
  tx(sReferencias, "Software-Defined Networking: A Comprehensive Survey. Proceedings of the IEEE 103(1), 14–76.", 0.55, 5.2, 12.2, 0.75, { fontSize: 17 });
  tx(sReferencias, "Código, protocolo y resultados: repositorio Campus-DDoS-SDN.", 0.55, 6.25, 12.2, 0.4, { fontSize: 16, color: "3E5C4C" });
  sReferencias.addNotes("No leer las referencias completas. Señalar que la primera es el antecedente directo, la segunda sustenta la extracción de flujos y la tercera el contexto SDN.");

  const s16 = pres.addSlide({ masterName: "cierre", sectionTitle: "Conclusiones" });
  s16.addImage({ path: IMG + "/escudo-uncp.png", x: 0.6, y: 0.45, w: 0.9, h: 0.77 });
  s16.addText("Resultados preliminares y siguiente fase", { placeholder: "title" });
  s16.addText("Prueba en casa hecha. Escaneo del campus, por autorizar.\nCalderón  ·  Llanos  ·  Martínez  ·  Poves", { placeholder: "body" });
  s16.addNotes("Agradecer a la facultad y abrir preguntas. Si preguntan cuándo se escanea, la respuesta es: después de que el encargado autorice. Hasta entonces el número que se defiende es el de la casa.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log(OUT);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
