# Mejoras concretas (orden de trabajo)

## Ya listo

1. Documento formal para el encargado: `docs/documento_encargado.md` / `.docx`.
2. Detector ML sobre simulación (F1 macro 0,979 en Agrarias).
3. Pipeline híbrido: Wireshark → anonimizar → mezclar con ataques simulados → informe.
4. Artículo borrador con tabla de resultados (`paper/main_es.tex`).

## Cuando entreguen el pcap

1. Copiar a `data/real/wireshark/`.
2. Correr `bash scripts/docker/preparar_hibrido.sh`.
3. Leer `informe_hibrido.txt` y `comparacion.txt`.
4. Si el F1 híbrido se mantiene, esa es la frase fuerte del artículo.
5. Si baja, el hallazgo es que el alumno sintético no bastaba: también se publica.

## Mejoras que sí suben el aporte (después del pcap)

| # | Mejora | Por qué |
|---|--------|---------|
| 1 | 2–3 capturas Wireshark de horarios distintos | Más variedad de BENIGN real |
| 2 | Una corrida `all 120` nueva + convert | Dataset de ataque alineado con la fecha del paper |
| 3 | Escenario mixto (4 ataques a la vez) | Multiclase de verdad, no 4 archivos |
| 4 | Más ICMP (cientos de flujos) | Hoy no se puede afirmar esa clase |
| 5 | Holdout por laboratorio + holdout Wireshark (`10.6`) | Prueba que no memoriza el segmento |

## Lo que no hace falta ahora

- Cambiar a red neuronal.
- Atacar el controlador Ryu en el mismo estudio.
- Subir a 22 facultades.
- Publicar el pcap original sin anonimizar.
