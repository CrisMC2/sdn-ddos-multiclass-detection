# Documentos LaTeX del proyecto

## Cuál es cada archivo

| Archivo | Para quién | Qué es |
|---------|------------|--------|
| **`main_es.tex`** | Asesor / UNCP | Artículo en español (clase `cas-dc`) |
| **`main.tex`** | Software Impacts | Artículo en inglés (el que se envía a la revista) |
| `numeros.tex` | ambos | F1 macro (`\Fmacro`, `\FmacroEs`) |
| `tabla_resultados.tex` | español | Tabla de detección |
| `tabla_resultados_en.tex` | inglés | Misma tabla |
| `frase_es.tex` / `frase_en.tex` | abstract | Efecto en el portal |
| `references.bib` | ambos | Bibliografía |
| `../docs/protocolo_encargado.tex` | Encargado de redes | Fuente del protocolo Wireshark |
| `../docs/protocolo_encargado.pdf` | Encargado de redes | Protocolo listo para enviar |
| `../docs/documento_encargado.md` | Equipo | Versión larga y editable |

Los PDF `main_es.pdf` y `main.pdf` se regeneran al compilar. Si están viejos, vuelve a compilar.

## Compilar

Ya está instalado `tectonic` en este Mac. Desde la raíz:

```bash
bash paper/compilar.sh both   # español + inglés + protocolo del encargado
bash paper/compilar.sh es     # solo main_es.pdf
bash paper/compilar.sh en     # solo main.pdf
```

Los PDF quedan en:

- `paper/main_es.pdf` — artículo español
- `paper/main.pdf` — artículo inglés
- `docs/protocolo_encargado.pdf` — para el encargado

Hace falta la carpeta `paper/thumbnails/` (iconos de la plantilla Elsevier).
Ya está en el repo.

## Estado del contenido

- Abstract, descripción, impacto, tabla ML (F1 0,979) y limitaciones: **completos**.
- Pipeline Wireshark / híbrido: descrito en el texto; el informe híbrido aparece cuando haya pcap en `data/real/wireshark/`.
- Pendiente humano: URL del repositorio (C2) al publicar.
