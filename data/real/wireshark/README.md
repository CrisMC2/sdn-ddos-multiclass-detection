# Capturas Wireshark del encargado

Deja aquí los archivos `.pcap` o `.pcapng` de tráfico **normal** de estudiantes
(el escaneo / captura autorizada).

Forma más fácil, desde la raíz del repo:

```bash
bash usar_datos_reales.sh ~/Descargas/alumnos.pcapng
```

O copia el archivo a esta carpeta y corre:

```bash
bash usar_datos_reales.sh
```

Eso anonimiza, mezcla con los ataques de la simulación, entrena el modelo
y escribe `notebooks/resultados/informe_hibrido.txt`.

No pongas aquí ataques reales. El ataque del proyecto solo corre dentro de Docker.
