/**
 * Distribuidora La Estiba (empresa ficticia): automatizacion de la planilla.
 *
 * Que hace:
 *   1. onEdit: valida el CUIT cuando la oficina edita la pestaña clientes.
 *   2. importarArchivos: importa los CSV diarios del facturador y de las
 *      procesadoras de tarjeta desde una carpeta de Drive, sin duplicar filas.
 *   3. validarTodo: revisa todos los datos (tambien lo cargado desde AppSheet,
 *      que no dispara onEdit) y deja los problemas en la pestaña "validaciones".
 *   4. enviarAlertas: mail diario a cobranzas con las facturas vencidas.
 *   5. enviarResumenSemanal: mail a la dueña con los numeros de la semana.
 *
 * La conciliacion completa (aging, DSO, liquidaciones) la hace Python.
 * Este script es la primera linea de control, dentro de Google.
 */

const CONFIG = {
  CARPETA_ENTRADA: 'La Estiba - entrada',  // carpeta de Drive con subcarpetas facturas, liquidaciones y procesados
  EMAIL_COBRANZAS: '',                     // vacio = el dueño de la planilla
  EMAIL_DUENA: '',                         // vacio = el dueño de la planilla
  DIAS_ALERTA: 30,                         // avisar facturas vencidas hace mas de N dias
  FECHA_CORTE: '2026-11-30',               // demo: fecha de corte de los datos. En produccion: null (= hoy)
  HOJA_VALIDACIONES: 'validaciones',
};

const HOJAS = {
  clientes: 'clientes',
  facturas: 'facturas',
  cobranzas: 'cobranzas',
  liquidaciones: 'liquidaciones_tarjeta',
};


// ---------------------------------------------------------------------------
// Menu y disparadores
// ---------------------------------------------------------------------------

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('La Estiba')
    .addItem('Importar archivos nuevos', 'importarArchivos')
    .addItem('Validar todos los datos', 'validarTodo')
    .addItem('Enviar alertas de vencidas', 'enviarAlertas')
    .addItem('Enviar resumen semanal', 'enviarResumenSemanal')
    .addSeparator()
    .addItem('Instalar tareas automaticas', 'instalarDisparadores')
    .addToUi();
}

/** Tarea diaria: importar, validar y avisar, en ese orden. */
function tareaDiaria() {
  importarArchivos();
  validarTodo();
  enviarAlertas();
}

/** Crea los disparadores: todos los dias a las 7 y los lunes a las 8. */
function instalarDisparadores() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('tareaDiaria').timeBased().everyDays(1).atHour(7).create();
  ScriptApp.newTrigger('enviarResumenSemanal').timeBased()
    .onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(8).create();
  aviso_('Tareas automaticas instaladas: diaria a las 7 h y resumen los lunes a las 8 h.');
}


// ---------------------------------------------------------------------------
// 1. Validacion al editar (solo ediciones hechas a mano en la planilla)
// ---------------------------------------------------------------------------

function onEdit(e) {
  const hoja = e.range.getSheet();
  if (hoja.getName() !== HOJAS.clientes || e.range.getRow() === 1) return;

  const encabezado = hoja.getRange(1, 1, 1, hoja.getLastColumn()).getValues()[0];
  const colCuit = encabezado.indexOf('cuit') + 1;
  if (colCuit === 0) return;

  for (let fila = e.range.getRow(); fila <= e.range.getLastRow(); fila++) {
    const celda = hoja.getRange(fila, colCuit);
    const valor = celda.getValue();
    if (valor === '' || cuitValido_(valor)) {
      celda.setBackground(null).setNote('');
    } else {
      celda.setBackground('#f4c7c3').setNote('CUIT invalido: el digito verificador no coincide.');
    }
  }
}


// ---------------------------------------------------------------------------
// 2. Importacion de los CSV diarios
// ---------------------------------------------------------------------------

function importarArchivos() {
  const raiz = carpeta_(DriveApp, CONFIG.CARPETA_ENTRADA);
  const procesados = carpeta_(raiz, 'procesados');
  const resultado = [
    importarCarpeta_(carpeta_(raiz, 'facturas'), HOJAS.facturas, 'factura_id', procesados),
    importarCarpeta_(carpeta_(raiz, 'liquidaciones'), HOJAS.liquidaciones, 'liquidacion_id', procesados),
  ];
  const texto = resultado.join('\n');
  Logger.log(texto);
  aviso_(texto);
}

function importarCarpeta_(carpeta, nombreHoja, columnaId, procesados) {
  const hoja = hoja_(nombreHoja);
  const encabezado = hoja.getRange(1, 1, 1, hoja.getLastColumn()).getValues()[0];
  const idx = encabezado.indexOf(columnaId);
  const existentes = new Set(
    hoja.getLastRow() > 1
      ? hoja.getRange(2, idx + 1, hoja.getLastRow() - 1, 1).getValues().map(r => String(r[0]))
      : []
  );

  let archivos = 0, nuevas = 0, repetidas = 0;
  const it = carpeta.getFilesByType(MimeType.CSV);
  while (it.hasNext()) {
    const archivo = it.next();
    const filas = Utilities.parseCsv(archivo.getBlob().getDataAsString('UTF-8'));
    const columnas = filas.shift();
    if (columnas.join(',') !== encabezado.join(',')) {
      throw new Error(`${archivo.getName()}: las columnas no coinciden con la pestaña ${nombreHoja}.`);
    }
    const aAgregar = [];
    filas.filter(f => f.join('') !== '').forEach(f => {
      if (existentes.has(String(f[idx]))) { repetidas++; return; }
      existentes.add(String(f[idx]));
      aAgregar.push(f.map(convertir_));
    });
    if (aAgregar.length) {
      hoja.getRange(hoja.getLastRow() + 1, 1, aAgregar.length, encabezado.length).setValues(aAgregar);
    }
    archivo.moveTo(procesados);
    archivos++;
    nuevas += aAgregar.length;
  }
  return `${nombreHoja}: ${archivos} archivo(s), ${nuevas} fila(s) nuevas, ${repetidas} repetida(s) omitida(s).`;
}

/** Convierte textos del CSV a numero, booleano o fecha; deja el resto como texto. */
function convertir_(valor) {
  if (valor === '') return '';
  if (valor === 'True' || valor === 'TRUE') return true;
  if (valor === 'False' || valor === 'FALSE') return false;
  if (/^\d{4}-\d{2}-\d{2}$/.test(valor)) {
    const [a, m, d] = valor.split('-').map(Number);
    return new Date(a, m - 1, d);
  }
  if (/^-?\d+(\.\d+)?$/.test(valor) && !/^0\d/.test(valor)) return Number(valor);
  return valor;
}


// ---------------------------------------------------------------------------
// 3. Validacion de todos los datos
// ---------------------------------------------------------------------------

function validarTodo() {
  const clientes = leer_(HOJAS.clientes);
  const facturas = leer_(HOJAS.facturas);
  const cobranzas = leer_(HOJAS.cobranzas);
  const problemas = [];
  const anotar = (tabla, id, problema) => problemas.push([new Date(), tabla, id, problema]);

  // Clientes: CUIT
  clientes.forEach(c => {
    if (!cuitValido_(c.cuit)) anotar('clientes', c.cliente_id, `CUIT invalido: ${c.cuit}`);
  });

  // Facturas: mas de una factura para el mismo pedido
  const porPedido = agrupar_(facturas, f => f.pedido_id);
  Object.keys(porPedido).forEach(p => {
    if (p && porPedido[p].length > 1) {
      porPedido[p].slice(1).forEach(f =>
        anotar('facturas', f.factura_id, `Posible duplicada: el pedido ${p} tiene ${porPedido[p].length} facturas`));
    }
  });

  // Cobranzas
  const facturaPorId = indexar_(facturas, f => f.factura_id);
  const cupones = agrupar_(cobranzas.filter(c => c.medio === 'tarjeta'), c => String(c.cupon_nro));
  cobranzas.forEach(c => {
    const id = c.cobranza_id;
    if (!c.factura_id) {
      anotar('cobranzas', id, 'Pago sin factura asignada');
    } else {
      const f = facturaPorId[c.factura_id];
      if (!f) anotar('cobranzas', id, `La factura ${c.factura_id} no existe`);
      else {
        if (f.cliente_id !== c.cliente_id) anotar('cobranzas', id, `La factura ${c.factura_id} es de otro cliente`);
        if (Number(c.importe) > Number(f.importe_total) + 0.01) {
          anotar('cobranzas', id, `Importe ${c.importe} mayor que la factura (${f.importe_total}): posible error de tipeo`);
        }
      }
    }
    if (c.medio === 'tarjeta') {
      if (c.tarjeta_tipo === 'debito' && Number(c.cuotas) > 1) anotar('cobranzas', id, 'Debito cargado en cuotas');
      if (cupones[String(c.cupon_nro)].length > 1 && cupones[String(c.cupon_nro)][0].cobranza_id !== id) {
        anotar('cobranzas', id, `Cupon ${c.cupon_nro} cargado mas de una vez`);
      }
    }
    if (c.medio === 'cheque' && c.cheque_estado === 'rechazado') {
      anotar('cobranzas', id, `Cheque ${c.cheque_numero} rechazado: la factura ${c.factura_id} vuelve a estar impaga`);
    }
  });

  // Escribir la pestaña de validaciones (se rehace completa cada vez)
  const hoja = hojaOCrear_(CONFIG.HOJA_VALIDACIONES);
  hoja.clearContents();
  hoja.getRange(1, 1, 1, 4).setValues([['revisado', 'tabla', 'registro_id', 'problema']]);
  if (problemas.length) hoja.getRange(2, 1, problemas.length, 4).setValues(problemas);
  hoja.setFrozenRows(1);
  Logger.log(`Validacion: ${problemas.length} problema(s).`);
  return problemas.length;
}


// ---------------------------------------------------------------------------
// 4 y 5. Saldos y mails
// ---------------------------------------------------------------------------

/** Saldo de cada factura: total menos cobros validos (sin cheques rechazados ni contracargos). */
function calcularSaldos_() {
  const facturas = leer_(HOJAS.facturas);
  const cobranzas = leer_(HOJAS.cobranzas);
  const liquidaciones = leer_(HOJAS.liquidaciones);
  const contracargos = new Set(liquidaciones.filter(l => l.es_contracargo === true).map(l => String(l.cupon_nro)));

  const cobrado = {};
  cobranzas.forEach(c => {
    if (!c.factura_id) return;
    if (c.medio === 'cheque' && c.cheque_estado === 'rechazado') return;
    if (c.medio === 'tarjeta' && contracargos.has(String(c.cupon_nro))) return;
    cobrado[c.factura_id] = (cobrado[c.factura_id] || 0) + Number(c.importe);
  });

  const corte = fechaCorte_();
  return facturas.map(f => {
    const saldo = Number(f.importe_total) - (cobrado[f.factura_id] || 0);
    const dias = Math.floor((corte - new Date(f.fecha_vencimiento)) / 86400000);
    return { factura: f, saldo: saldo, diasVencida: dias };
  }).filter(x => x.saldo > 1);
}

function enviarAlertas() {
  const clientes = indexar_(leer_(HOJAS.clientes), c => c.cliente_id);
  const vencidas = calcularSaldos_().filter(x => x.diasVencida > CONFIG.DIAS_ALERTA);
  if (!vencidas.length) { Logger.log('Sin facturas vencidas para avisar.'); return; }

  const porCliente = agrupar_(vencidas, x => x.factura.cliente_id);
  const filas = Object.keys(porCliente).map(id => {
    const items = porCliente[id];
    return {
      cliente: clientes[id] ? clientes[id].razon_social : id,
      vendedor: clientes[id] ? clientes[id].vendedor_id : '',
      facturas: items.length,
      saldo: items.reduce((s, x) => s + x.saldo, 0),
      maxDias: Math.max(...items.map(x => x.diasVencida)),
    };
  }).sort((a, b) => b.maxDias - a.maxDias);

  const total = filas.reduce((s, f) => s + f.saldo, 0);
  const html =
    `<p>Hay <b>${filas.length} clientes</b> con facturas vencidas hace más de ${CONFIG.DIAS_ALERTA} días, ` +
    `por un total de <b>${pesos_(total)}</b>. Ordenados por antigüedad:</p>` +
    tablaHtml_(['Cliente', 'Vendedor', 'Facturas', 'Saldo', 'Días de atraso'],
      filas.map(f => [f.cliente, f.vendedor, f.facturas, pesos_(f.saldo), f.maxDias])) +
    `<p style="color:#666">Corte: ${fechaTexto_(fechaCorte_())}. Saldos sin cheques rechazados ni contracargos.</p>`;

  MailApp.sendEmail({
    to: CONFIG.EMAIL_COBRANZAS || Session.getEffectiveUser().getEmail(),
    subject: `La Estiba · ${filas.length} clientes para llamar hoy (${pesos_(total)} vencido)`,
    htmlBody: html,
  });
}

function enviarResumenSemanal() {
  const saldos = calcularSaldos_();
  const sumar = arr => arr.reduce((s, x) => s + x.saldo, 0);
  const tramos = [
    ['A vencer', saldos.filter(x => x.diasVencida <= 0)],
    ['Vencido 1 a 30 días', saldos.filter(x => x.diasVencida >= 1 && x.diasVencida <= 30)],
    ['Vencido 31 a 60 días', saldos.filter(x => x.diasVencida >= 31 && x.diasVencida <= 60)],
    ['Vencido 61 a 90 días', saldos.filter(x => x.diasVencida >= 61 && x.diasVencida <= 90)],
    ['Vencido más de 90 días', saldos.filter(x => x.diasVencida > 90)],
  ];

  // Cobros con tarjeta todavia no liquidados (plata en transito)
  const liquidados = new Set(leer_(HOJAS.liquidaciones).map(l => String(l.cupon_nro)));
  const enTransito = leer_(HOJAS.cobranzas)
    .filter(c => c.medio === 'tarjeta' && !liquidados.has(String(c.cupon_nro)))
    .reduce((s, c) => s + Number(c.importe), 0);

  const hojaVal = SpreadsheetApp.getActive().getSheetByName(CONFIG.HOJA_VALIDACIONES);
  const problemas = hojaVal ? Math.max(hojaVal.getLastRow() - 1, 0) : 0;

  const html =
    `<p>Total por cobrar: <b>${pesos_(sumar(saldos))}</b></p>` +
    tablaHtml_(['Tramo', 'Facturas', 'Saldo'], tramos.map(([n, arr]) => [n, arr.length, pesos_(sumar(arr))])) +
    `<p>Cobros con tarjeta en tránsito (sin liquidar): <b>${pesos_(enTransito)}</b></p>` +
    `<p>Problemas de datos pendientes de revisar: <b>${problemas}</b> (pestaña "${CONFIG.HOJA_VALIDACIONES}")</p>` +
    `<p style="color:#666">Corte: ${fechaTexto_(fechaCorte_())}.</p>`;

  MailApp.sendEmail({
    to: CONFIG.EMAIL_DUENA || Session.getEffectiveUser().getEmail(),
    subject: `La Estiba · Resumen semanal de cobranzas`,
    htmlBody: html,
  });
}


// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------

/** CUIT valido: 11 digitos y digito verificador correcto (modulo 11). */
function cuitValido_(cuit) {
  const d = String(cuit).replace(/\D/g, '');
  if (d.length !== 11) return false;
  const pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];
  const resto = pesos.reduce((s, p, i) => s + p * Number(d[i]), 0) % 11;
  const dv = resto === 0 ? 0 : 11 - resto;
  return dv !== 10 && dv === Number(d[10]);
}

function hoja_(nombre) {
  const h = SpreadsheetApp.getActive().getSheetByName(nombre);
  if (!h) throw new Error(`No existe la pestaña "${nombre}".`);
  return h;
}

function hojaOCrear_(nombre) {
  const ss = SpreadsheetApp.getActive();
  return ss.getSheetByName(nombre) || ss.insertSheet(nombre);
}

/** Lee una pestaña como lista de objetos {columna: valor}. */
function leer_(nombre) {
  const valores = hoja_(nombre).getDataRange().getValues();
  const encabezado = valores.shift();
  return valores
    .filter(f => f.join('') !== '')
    .map(f => Object.fromEntries(encabezado.map((c, i) => [c, f[i]])));
}

function agrupar_(lista, clave) {
  return lista.reduce((acc, x) => { (acc[clave(x)] = acc[clave(x)] || []).push(x); return acc; }, {});
}

function indexar_(lista, clave) {
  return lista.reduce((acc, x) => { acc[clave(x)] = x; return acc; }, {});
}

function carpeta_(padre, nombre) {
  const it = padre.getFoldersByName(nombre);
  if (!it.hasNext()) throw new Error(`No existe la carpeta "${nombre}" en Drive.`);
  return it.next();
}

function fechaCorte_() {
  if (!CONFIG.FECHA_CORTE) {
    const h = new Date();
    return new Date(h.getFullYear(), h.getMonth(), h.getDate());
  }
  const [a, m, d] = CONFIG.FECHA_CORTE.split('-').map(Number);
  return new Date(a, m - 1, d);
}

function pesos_(n) {
  return '$ ' + Number(n).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fechaTexto_(d) {
  return Utilities.formatDate(d, Session.getScriptTimeZone(), 'dd/MM/yyyy');
}

function tablaHtml_(encabezado, filas) {
  const th = encabezado.map(h => `<th style="text-align:left;padding:4px 10px;border-bottom:1px solid #ccc">${h}</th>`).join('');
  const tr = filas.map(f => '<tr>' + f.map(v => `<td style="padding:4px 10px">${v}</td>`).join('') + '</tr>').join('');
  return `<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px"><tr>${th}</tr>${tr}</table>`;
}

/** Muestra un aviso si hay alguien mirando la planilla; si corre por disparador, solo registra. */
function aviso_(texto) {
  try { SpreadsheetApp.getUi().alert(texto); } catch (e) { Logger.log(texto); }
}
