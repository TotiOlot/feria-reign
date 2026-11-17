# Agenda de feria sincronizada con Outlook

- `agenda.json` (raíz) es lo que lee el dashboard cada 5 min. Lo regenera una tarea programada de Claude que lee el calendario de Outlook y hace push aquí; Vercel publica solo.
- `agenda/config.json`: nombre y fechas de la feria activa. Para otra feria, cambia solo esto.
- `agenda/mapa.json`: qué reunión abre qué ficha de cliente/proveedor.
- `agenda/build_agenda.py eventos.json`: convierte los eventos de Outlook (UTC) a hora local de la feria. Escribe solo si hay cambios.
- Si `agenda.json` no carga, el dashboard usa la agenda embebida en `index.html`.
