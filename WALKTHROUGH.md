# WALKTHROUGH — Recorrido completo del proyecto

> Guía en español, en lenguaje simple y detallado, que explica **cómo funciona todo el flujo de operación** y **cómo ejecutar los notebooks** paso a paso. Complementa al [`README.md`](README.md) (en inglés, orientado a reclutadores).

---

## 0. La idea en una frase

Bajo datos económicos **reales y públicos** (precios de metales, energía y tipo de cambio), los uso para **fabricar cotizaciones de proveedores creíbles** (porque las reales son secretas), y con eso **predigo precios** y **califico proveedores** para terminar en una **decisión de compra concreta**.

Regla de oro: **datos reales primero, datos sintéticos después y siempre amarrados a los reales.**

---

## 1. El mapa: cómo fluyen los datos

Los datos viajan por carpetas, de izquierda a derecha. Cada etapa lee de una y escribe en la siguiente:

```
                (FRED, internet)                 (simulación)            (limpieza)
 data/external/  ───────────────►  data/raw/  ───────────►  data/processed/  ──┐
   índices reales                  cotizaciones              dataset limpio     │
   + tabla países                  + maestro proveedores                        │
                                                                                ▼
                                                            ┌──────────  reports/  ──────────┐
                                                            │  modelo de precios (métricas)   │
                                                            │  supplier_scorecard.csv         │
                                                            │  figures/ (10 gráficos)         │
                                                            └─────────────────────────────────┘
```

Carpetas:
- **`data/external/`** → datos **reales** (FRED) + tabla de **referencia** de países.
- **`data/raw/`** → datos **sintéticos** (cotizaciones), calibrados con los reales.
- **`data/processed/`** → dataset **limpio y enriquecido** (el que usan modelo y scorecard).
- **`reports/`** → resultados: scorecard, métricas, figuras, resumen ejecutivo.

---

## 2. El flujo de operación (el pipeline), etapa por etapa

Son **6 etapas en cadena**. Cada una es un archivo en `src/` y se puede correr sola.

### Etapa 1 — Conseguir los datos reales · `src/data_acquisition.py`
- **Qué hace:** descarga de **FRED** (base de datos pública de la Reserva Federal de EE.UU., sin contraseña) 5 series reales: aluminio, cobre, mineral de hierro (proxy del acero), índice de energía y tipo de cambio EUR/USD.
- Recorta todo a **36 meses (2022–2024)** y normaliza a **base 100 en enero-2022** (así un valor de 156 = "56% más caro que al inicio").
- Junta los 3 metales en **un solo índice de materia prima** (45% aluminio, 30% cobre, 25% acero).
- Arma una **tabla de países** (región, distancia a Alemania, riesgo, moneda).
- Guarda un archivo de **procedencia** (`_acquisition_metadata.json`): de dónde salió cada dato, cuándo, cuántas filas.
- **Red de seguridad:** si no hay internet, genera series de respaldo realistas y las marca como `fallback` (nunca lo oculta).
- **Entrada:** internet (FRED). **Salida:** 4 CSV en `data/external/`.
- **Correr sola:** `python -m src.data_acquisition`

### Etapa 2 — Fabricar las cotizaciones · `src/data_generation.py`
- **Qué hace:** crea **60 proveedores** (cada uno con país, nombre, qué componentes vende y una *personalidad* oculta: barato-riesgoso, caro-confiable, equilibrado, estratégico, mediocre).
- Para cada proveedor × componente × mes genera una cotización, le pega los **índices reales de ese mes**, y **calcula el precio con una fórmula** que multiplica factores: precio base × efecto materia prima × efecto energía × escasez × tipo de cambio × descuento por volumen × distancia × tipo de contrato × personalidad × algo de azar.
- También simula calidad, puntualidad, defectos, tiempo de entrega, riesgo y sostenibilidad.
- **Entrada:** `data/external/`. **Salida:** `data/raw/supplier_quotes.csv` (tabla de hechos) y `supplier_master.csv` (directorio de proveedores, con la personalidad secreta para validar después).
- **Correr sola:** `python -m src.data_generation`

### Etapa 3 — Limpiar y preparar · `src/preprocessing.py`
- **Qué hace:** controla calidad (tipos correctos, sin duplicados, sin valores imposibles, sin huecos) y agrega columnas útiles: fecha, valor total del pedido, **precio comparado con la mediana del mismo componente** (para comparar justo baterías caras vs cables baratos), costo puesto en planta, banderas de zona euro / ultramar.
- **Entrada:** `data/raw/`. **Salida:** `data/processed/supplier_quotes_processed.csv`.
- **Correr sola:** `python -m src.preprocessing`

### Etapa 4 — Predecir el precio · `src/price_model.py`
- **Qué hace:** entrena 3 modelos para estimar `unit_price`: **Regresión Lineal** (base), **Random Forest** y **Gradient Boosting**. Separa 80% entrenamiento / 20% prueba y mide 4 errores: **MAE, RMSE, R², MAPE**.
- **Resultado típico:** los modelos de árbol ganan (R² ≈ 0.98, error ≈ 11%) frente al lineal (≈ 40%), porque el precio se forma multiplicando, no sumando.
- **Entrada:** `data/processed/`. **Salida:** `reports/model_comparison.csv` + artefactos para los gráficos.
- **Correr sola:** `python -m src.price_model`

### Etapa 5 — Calificar proveedores · `src/supplier_scoring.py`
- **Qué hace:** resume todo a **una fila por proveedor** y calcula 5 sub-puntajes 0–100 (costo, entrega, calidad, riesgo, sostenibilidad), los combina con **pesos configurables** (30/25/20/15/10) → **puntaje final 0–100**, asigna **categoría** y **acción recomendada**.
- Valida los resultados contra la personalidad oculta (recupera ~70% de los arquetipos).
- **Entrada:** `data/processed/`. **Salida:** `reports/supplier_scorecard.csv`.
- **Correr sola:** `python -m src.supplier_scoring`

### Etapa 6 — Graficar · `src/visualization.py`
- **Qué hace:** genera las **10 figuras** (`reports/figures/01_*.png` … `10_*.png`): tendencia de índices reales, precio por componente, materia prima vs precio, volumen vs precio, barato vs confiable, top-10 proveedores, riesgo vs puntaje, real vs predicho, importancia de variables y mapa de calor por categoría.
- **Entrada:** `data/processed/` + `reports/`. **Salida:** `reports/figures/`.
- **Correr sola:** `python -m src.visualization`

---

## 3. Cómo correr TODO el pipeline (un solo comando)

```bash
pip install -r requirements.txt     # 1. instalar dependencias
python run_pipeline.py              # 2. correr las 6 etapas en orden (~30 s)
```

`run_pipeline.py` ejecuta las etapas 1→6 en secuencia y deja todos los archivos listos. Como usa una **semilla fija** y una **ventana de fechas fija**, el resultado es **idéntico cada vez** (reproducible).

---

## 4. Los notebooks: qué cuentan y CÓMO ejecutarlos

Los **5 notebooks** (`notebooks/`) son la versión narrada del pipeline: el mismo análisis, pero contado con texto, tablas y gráficos. **Se entregan ya ejecutados** (verás las salidas directo en GitHub), y se pueden volver a correr.

### 4.1. Qué hace cada notebook

| Notebook | Equivale a la etapa | Qué muestra |
|----------|---------------------|-------------|
| **01_data_acquisition_macro_drivers** | Etapa 1 | Carga los índices reales de FRED, su procedencia y grafica la historia económica (la crisis energética de 2022, el euro debilitándose). |
| **02_generate_supplier_quotes** | Etapa 2 | Inspecciona las cotizaciones sintéticas y **comprueba** que las relaciones exigidas se cumplen (materia prima↔precio, volatilidad por contrato, economías de escala). |
| **03_procurement_eda** | Etapa 3 | Análisis exploratorio: precio por componente y país, co-movimiento con los índices reales, riesgo por región, entrega vs defectos. |
| **04_price_forecasting_model** | Etapa 4 | Entrena y compara los 3 modelos, grafica real-vs-predicho, residuales e importancia de variables. |
| **05_supplier_scorecard** | Etapa 5 | Construye el scorecard, lo grafica como mapa de calor, **valida contra los arquetipos** y lista mejores y peores proveedores con su acción. |

### 4.2. Requisito previo

Los notebooks **leen los archivos ya generados** (`data/` y `reports/`, que vienen en el repo), así que **corren tal cual**. Si quieres datos frescos, corre antes `python run_pipeline.py`.

### 4.3. Tres formas de ejecutarlos

**Opción A — Jupyter Lab / Notebook (recomendada):**
```bash
pip install -r requirements.txt
jupyter lab            # o:  jupyter notebook
```
Abre la carpeta `notebooks/`, entra a cada notebook **en orden (01 → 05)** y usa el menú **Run → Run All Cells** (ejecutar todas las celdas de arriba hacia abajo).

**Opción B — VS Code:**
Abre el archivo `.ipynb`, arriba a la derecha selecciona el **kernel de Python** (tu intérprete con las dependencias instaladas) y pulsa **Run All**.

**Opción C — Línea de comandos (sin abrir nada):**
```bash
jupyter nbconvert --to notebook --execute --inplace notebooks/01_data_acquisition_macro_drivers.ipynb
# ...repite para 02, 03, 04 y 05
```
> Nota: la Opción C necesita un kernel de Jupyter funcionando. Si tu entorno tiene problemas con el kernel, usa la Opción A o B (son las más fiables).

### 4.4. Orden y dependencias

- **Ejecuta siempre de arriba hacia abajo** dentro de cada notebook (la primera celda prepara las rutas e importa todo).
- Entre notebooks, el orden natural es **01 → 02 → 03 → 04 → 05**, pero como cada uno carga los archivos del repo, también puedes abrir uno solo de forma independiente.

### 4.5. Qué verás al ejecutarlos

- Tablas (DataFrames) con cabeceras y datos.
- Gráficos embebidos (líneas de tendencia, dispersión, mapa de calor).
- Mensajes de texto con cifras clave (correlaciones, métricas, conteos por categoría).

---

## 5. Reproducibilidad

- **Semilla fija** (`RANDOM_SEED`) → la simulación da siempre los mismos números.
- **Ventana fija** (`WINDOW_START`/`WINDOW_END`) → siempre los mismos 36 meses.
- Re-ejecutar el pipeline **regenera datos idénticos**.

---

## 6. Dónde tocar para cambiar cosas · `src/config.py`

Es el "tablero de control" único del proyecto:
- **Rutas** de todas las carpetas y archivos.
- **Ventana de análisis** y series de FRED a descargar.
- **Pesos del scorecard** (`SCORECARD_WEIGHTS`) — cámbialos y el ranking cambia.
- **Coeficientes de la simulación** (precios base, sensibilidades, arquetipos).

Cambia algo aquí y vuelve a correr `python run_pipeline.py`.

---

## 7. Mapa de archivos de salida

| Archivo | Qué es |
|---------|--------|
| `data/external/*.csv` | índices reales (FRED) + tabla de países |
| `data/external/_acquisition_metadata.json` | procedencia (fuente, URLs, fecha) |
| `data/raw/supplier_quotes.csv` | cotizaciones sintéticas (tabla de hechos) |
| `data/raw/supplier_master.csv` | directorio de proveedores (+ arquetipo) |
| `data/processed/supplier_quotes_processed.csv` | dataset limpio y enriquecido |
| `reports/model_comparison.csv` | métricas de los 3 modelos |
| `reports/supplier_scorecard.csv` | **el entregable principal**: ranking + categoría + acción |
| `reports/figures/01..10_*.png` | las 10 figuras |
| `reports/executive_summary.md` | resumen ejecutivo de 1 página |
