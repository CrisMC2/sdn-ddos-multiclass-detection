---
title: "Solicitud y protocolo de uso de tráfico de red de estudiantes para investigación"
subtitle: "Mezcla controlada de capturas Wireshark con ataques DDoS solo en simulación SDN"
author: "Equipo Campus-DDoS-SDN — Universidad Nacional del Centro del Perú"
date: "2026"
---

# 1. Objeto del documento

Este documento describe, para el encargado de redes / seguridad informática / autoridad académica competente, el uso autorizado de capturas de tráfico de estudiantes obtenidas con Wireshark, y la forma en que ese tráfico se mezcla con ataques DDoS **únicamente dentro de un laboratorio simulado** (Mininet + Ryu + Docker).

El objetivo de la investigación es construir un dataset y un detector multiclase de DDoS en un campus SDN emulado, comparando tráfico benigno real (estudiantes) con tráfico de ataque generado solo en simulación.

# 2. Alcance de lo autorizado

## 2.1 Qué sí se hace

1. Capturar, con Wireshark u otra herramienta equivalente, tráfico **benigno** de estudiantes en un segmento, horario y condiciones acordados con el encargado.
2. Guardar el archivo `.pcap` (o `.pcapng`) en un repositorio de trabajo del proyecto, bajo control del equipo de investigación.
3. Anonimizar el archivo antes del análisis: se remapean direcciones IP a rangos de laboratorio y no se usa el contenido de la aplicación (cuerpo HTTP, contraseñas, textos) para entrenar el modelo.
4. Convertir el pcap a flujos estadísticos (CICFlowMeter) y etiquetarlos como `BENIGN`.
5. Mezclar esos flujos benignos con flujos de ataque generados **solo** dentro del contenedor Docker del campus emulado (`synflood`, `httpflood`, `slowloris`, `icmpflood`).
6. Entrenar y evaluar un clasificador de aprendizaje automático (bosque aleatorio) sin usar la dirección IP como característica.

## 2.2 Qué no se hace

1. **No** se lanza ningún ataque DDoS contra la red real de la universidad, contra servidores institucionales ni contra equipos de estudiantes.
2. **No** se reenvía el ataque simulado hacia Internet.
3. **No** se publican capturas con datos personales identificables (nombres de usuario, cookies, contraseñas, correos, payloads).
4. **No** se usa el tráfico real para atacar, escanear o saturar servicios de producción.
5. **No** se modifica la política de firewall ni se exige acceso privilegiado a switches de producción más allá de lo que el encargado autorice para la captura pasiva.

# 3. Justificación técnica

Los datasets públicos de DDoS (p. ej. CICIDS2017, CICDDoS2019) no fueron capturados en un entorno SDN con OpenFlow. Trabajos recientes en Mininet/Ryu suelen usar un solo vector de ataque o tráfico normal tomado de Internet en vivo, lo que dificulta repetir el experimento.

Este proyecto:

- emula un campus reducido (modem, core, DMZ, laboratorios por área académica);
- genera cuatro vectores de ataque contra un portal web de prueba;
- mantiene alumnos emulados navegando durante el ataque;
- etiqueta cada flujo por IP de origen;
- y ahora incorpora tráfico benigno real de estudiantes, capturado con Wireshark, para que el detector no dependa solo de páginas sintéticas.

La novedad que se busca defender es: **el patrón de ataque se reconoce aunque el fondo benigno sea tráfico real de estudiantes, sin atacar la red real**.

# 4. Procedimiento operativo acordado

## 4.1 Captura (cargo del encargado / operador autorizado)

| Paso | Responsable | Acción |
|------|-------------|--------|
| 1 | Encargado | Define segmento, puerto espejo o punto de captura, fecha y duración. |
| 2 | Operador autorizado | Captura con Wireshark solo tráfico de navegación / uso normal (sin inducir ataques). |
| 3 | Operador | Entrega el archivo `.pcap` / `.pcapng` al equipo de investigación por canal seguro. |
| 4 | Equipo | Confirma recepción y registra hash y fecha del archivo. |

**Recomendación de captura (orientativa):**

- Duración: 10 a 30 minutos de tráfico normal de estudiantes.
- Formato: `.pcap` o `.pcapng`.
- Filtro preferible: tráfico hacia/desde el servicio web o el laboratorio autorizado (no es obligatorio si el encargado indica otro alcance).
- Evitar capturar redes ajenas al permiso.

## 4.2 Tratamiento en el laboratorio de investigación

Los archivos se colocan en:

```text
data/real/wireshark/
```

Luego se ejecuta, desde la raíz del repositorio:

```bash
bash scripts/docker/preparar_hibrido.sh
```

Ese comando:

1. Anonimiza los pcap reales → `data/real/anonimizado/`.
2. Extrae flujos y los etiqueta `BENIGN`.
3. Los une a los flujos de ataque ya capturados en simulación → `data/processed/hibrido/`.
4. Entrena el modelo y escribe el informe en `notebooks/resultados/informe_hibrido.txt`.

## 4.3 Separación estricta ataque / red real

```text
[Estudiantes / Wireshark]  --->  solo tráfico BENIGN (archivo pcap)
                                      |
                                      v
                         anonimización + flujos CSV
                                      |
                                      v
[Docker / Mininet campus]  --->  ataques solo al portal emulado 10.0.0.10
                                      |
                                      v
                         dataset híbrido + modelo ML
```

El ataque (`hping3`, `slowhttptest`, HTTP flood) corre **dentro** del contenedor Docker y apunta al portal de prueba `10.0.0.10`. No tiene ruta hacia la red de producción.

# 5. Anonimización y protección de datos

1. Las IP de origen reales se remapean a direcciones de laboratorio del campus emulado (prefijos `10.x.0.0/16` de prueba).
2. El modelo **no** se entrena con IP, MAC ni puertos de origen/destino como características predictivas.
3. No se publica el pcap original con identidad de estudiantes.
4. En reportes y artículo solo se publican métricas agregadas (precision, recall, F1, matrices de confusión) y, si hace falta, muestras de flujos ya anonimizados.
5. El equipo conserva el pcap original solo el tiempo necesario para la tesis / artículo, o el que indique el encargado; pasado ese plazo se elimina o se archiva según indicación institucional.

# 6. Qué se entrega al encargado

| Entregable | Ubicación / forma |
|------------|-------------------|
| Este protocolo | `docs/documento_encargado.md` y versión `.docx` |
| Código del banco de pruebas | repositorio del proyecto Campus-DDoS-SDN |
| Informe de detección (simulación) | `notebooks/resultados/informe.txt` |
| Informe híbrido (real + ataque) | `notebooks/resultados/informe_hibrido.txt` (tras procesar los pcap) |
| Artículo (borrador) | `paper/main_es.tex` / `paper/main.tex` |

# 7. Resultados ya obtenidos (solo simulación)

Con los datos ya capturados en el campus emulado (sin pcap Wireshark aún en el entrenamiento):

- Modelo: bosque aleatorio, clases equilibradas.
- Entrena: laboratorios Salud, Ingenierías, Administración, Sociales.
- Prueba: Ciencias Agrarias (laboratorio no visto).
- **F1 macro: 0,979**.
- `BENIGN`, `httpflood`, `slowloris` y `synflood` se separan bien.
- `icmpflood` **no se afirma**: hay muy pocos flujos en la prueba.
- En la sonda del portal: Slowloris deja de abrir la página; HTTP flood la ralentiza; SYN/ICMP suben paquetes y la página puede seguir respondiendo.

Cuando el encargado entregue los pcap Wireshark, se repetirá la misma evaluación sobre el **dataset híbrido** y se actualizará el informe.

# 8. Mejoras previstas (con el permiso otorgado)

1. Incorporar 1–3 capturas Wireshark de estudiantes (10–30 min c/u) como fondo `BENIGN`.
2. Comparar dos entrenamientos: solo sintético vs híbrido (real + ataque simulado).
3. Capturar una corrida mixta en simulación (varios vectores a la vez) y re-evaluar.
4. Aumentar muestras ICMP (hoy insuficientes).
5. Mantener la exclusión de un laboratorio entero en la prueba, para no inflar el resultado.
6. No cambiar a deep learning hasta que el dataset híbrido sea estable: con este volumen el bosque aleatorio es el modelo adecuado y explicable.

# 9. Responsables

| Rol | Nombre / unidad | Contacto |
|-----|-----------------|----------|
| Autor de correspondencia | Cristhian Emilio Martínez Casas | cristhianmartinezcasas@gmail.com |
| Equipo de investigación | Calderón Leiva; Llanos Lozano; Martínez Casas; Poves Martínez | UNCP — Huancayo |
| Encargado que autoriza la captura | *(completar)* | *(completar)* |
| Unidad / oficina | *(completar)* | *(completar)* |

# 10. Declaración de conformidad

El equipo de investigación declara que:

1. Usará las capturas Wireshark **solo** con fines académicos del proyecto Campus-DDoS-SDN.
2. No ejecutará ataques contra la infraestructura real.
3. Aplicará anonimización antes de publicar resultados.
4. Respetará el segmento, horario y duración que indique el encargado.
5. Eliminará o devolverá los pcap originales si así se solicita.

Espacio para firma / conformidad:

| | Nombre y firma | Fecha |
|--|----------------|-------|
| Encargado | | |
| Responsable del equipo | | |

# 11. Instrucción breve para el encargado

1. Leer este documento.
2. Completar la sección 9 (nombre y unidad).
3. Autorizar por escrito (firma o correo) la captura en el segmento indicado.
4. Entregar al equipo uno o más archivos `.pcap` / `.pcapng` de tráfico normal de estudiantes.
5. El equipo procesará los archivos con `bash scripts/docker/preparar_hibrido.sh` y devolverá el informe `notebooks/resultados/informe_hibrido.txt`.

---

*Documento generado para el proyecto Campus-DDoS-SDN. Versión de trabajo 1.0.*
