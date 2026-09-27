# Escrito del proyecto (LaTeX)

`main.tex` usa la clase real que exige Software Impacts: **`cas-dc`**
(doble columna), del paquete oficial de Elsevier `els-cas-templates`
-- no `elsarticle` (esa es la clase generica de Elsevier, pero no la
que pide esta revista en particular).

La estructura de contenido sigue al pie de la letra la plantilla
oficial de la revista ("Software Impacts article template Version 2",
descargable desde su [Guide for
Authors](https://www.sciencedirect.com/journal/software-impacts/publish/guide-for-authors)):
Title, Authors, Abstract (~100 palabras), Keywords (maximo 6), tabla
de **Code metadata** con exactamente los campos `C1`-`C9` que pide la
plantilla, cuerpo del articulo de hasta 3 paginas (funcionalidad de
alto nivel, seccion de **Impact overview**, limitaciones/trabajo
futuro, publicaciones habilitadas), Acknowledgements (opcional) y
References. El `main.tex` anterior (basado en `elsarticle`, con
secciones tipo "Introduction/Workflow/Results/Conclusion" al estilo
de un paper de investigacion comun) **no** era el formato correcto de
esta revista -- quedo reemplazado por este.

El contenido de cada seccion es propio de este proyecto (no una copia
del paper de referencia), con `TODO`s marcados donde falta completar
con los resultados reales de la Fase 5 (entrenamiento de modelos).

## Como compilarlo

`cas-dc.cls` es un paquete estandar de CTAN (`els-cas-templates`),
disponible en cualquier distribucion de TeX Live/MiKTeX actualizada y
en Overleaf -- no hace falta descargar nada aparte.

**Opcion mas facil: Overleaf** (no requiere instalar nada) —
[overleaf.com](https://www.overleaf.com), crear un proyecto nuevo,
subir `main.tex` y `references.bib`, compilar con pdfLaTeX.

**Local**, si tenes una distribucion de LaTeX instalada
(TeX Live / MiKTeX):

```bash
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

(se corre `pdflatex` dos veces mas al final para que las referencias
cruzadas y la bibliografia queden bien enlazadas)

Ya se probo que compila sin errores (instalado y verificado con
TeX Live dentro de WSL en esta sesion).

## Pendientes marcados como TODO en `main.tex`

- Nombre real de los autores y afiliacion
- Resumen (abstract, ~100 palabras) y las secciones de contenido
  (Introduction, Impact overview, etc.), una vez esten los resultados
  de la Fase 5
- Campos `C2`, `C4`, `C9` de la tabla de Code metadata (URL del repo,
  licencia, email de contacto)
- Numeros de version exactos de `hping3` y `slowhttptest` en la tabla
  de requisitos
- Las 3 citas en `references.bib` marcadas "TODO: verificar" son de
  memoria (Mininet, CICFlowMeter/CICIDS2017, scikit-learn) — confirmar
  autores/volumen/paginas exactos contra la fuente antes de entregar.
  La cita del paper de referencia (Kumar & Gupta) si esta verificada
  contra el PDF real.
