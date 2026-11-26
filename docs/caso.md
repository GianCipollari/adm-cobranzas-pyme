# Caso: Distribuidora La Estiba

> Empresa y personas ficticias. El caso está armado para que los problemas sean los que aparecen en una pyme distribuidora real.

## La empresa

**Distribuidora La Estiba** vende alimentos secos, bebidas y artículos de limpieza a comercios de Bahía Blanca y la zona.

| Dato | Valor |
| --- | --- |
| Clientes activos | 80: almacenes, kioscos, autoservicios y restaurantes |
| Equipo comercial | 3 vendedores (preventistas): toman pedidos, visitan clientes y cobran |
| Volumen | Unos 20 pedidos por día hábil, alrededor de 400 por mes |
| Condición de pago | Contado, cuenta corriente a 15 días o a 30 días, según el cliente |
| Medios de pago | Efectivo, transferencia, Mercado Pago, cheques (al día y diferidos) y tarjetas de débito y crédito en 1, 3, 6 o 12 cuotas |
| Facturación | Un sistema facturador emite las facturas A y B ante ARCA y exporta un CSV por día |
| Tarjetas | Los vendedores cobran con posnet o Mercado Pago Point. Las procesadoras liquidan días después y envían un detalle de cada liquidación |
| Administración | Una persona administrativa y la dueña, Marcela, que revisa los números a fin de mes |

## Cómo trabajan hoy

1. El vendedor toma el pedido en la visita y lo anota en una planilla compartida de Google Sheets.
2. Administración factura en el facturador al día siguiente, a veces con varios días de atraso.
3. Cuando el vendedor cobra, avisa por WhatsApp con una foto del comprobante o del cheque.
4. La administrativa carga las cobranzas en otra planilla cuando puede, normalmente una vez por semana.
5. A fin de mes, Marcela cruza en Excel ventas, facturas y cobranzas para saber cuánto le deben.

## El problema

Marcela no sabe con certeza **quién le debe, cuánto ni desde cuándo** hasta que cierra el mes. Para entonces, algunas deudas ya tienen más de 60 días.

Lo que sale mal, en concreto:

- **Cobranzas que llegan tarde o mal cargadas.** Se pierden mensajes de WhatsApp, se tipean mal los montos (un cero de más o de menos) o se cargan a otro cliente.
- **Pagos que no se pueden imputar.** Un cliente paga una parte de una factura, o un solo pago cubre varias facturas, y nadie sabe qué factura quedó abierta.
- **Ventas entregadas que nunca se facturaron**, y algunas facturas emitidas dos veces.
- **Cheques diferidos que rebotan** y siguen figurando como cobrados.
- **Tarjetas que nadie controla.** Marcela da por cobrado lo que se pagó con tarjeta, pero la plata llega días después y con descuentos (comisión, costo de las cuotas, IVA y retenciones). No sabe cuánto tiene en tránsito, si cada cupón se liquidó ni cuánto le cuesta ofrecer cuotas.
- **Datos de clientes con errores**, como CUIT mal escritos, que traban la facturación.

## Lo que necesita: las 7 preguntas que responde la solución

> **Este es el centro del proyecto y del servicio que ofrezco:** que el dueño de una pyme pueda contestar estas preguntas todos los días, sin armar un Excel. El README las muestra primero y los gigs de Workana y Fiverr se arman a partir de ellas.

Marcela quiere poder contestar, todos los días y sin armar un Excel:

1. ¿Cuánto me deben en total y quién me debe más?
2. ¿Qué deudas están vencidas y hace cuánto (0–30, 31–60, 61–90, más de 90 días)?
3. ¿A quién tiene que llamar hoy cobranzas?
4. ¿Qué vendí y entregué que todavía no facturé?
5. ¿Cuántos días tardan en promedio mis clientes en pagarme (DSO)?
6. ¿Cuánta plata tengo en tránsito con las procesadoras de tarjeta y cuándo entra?
7. ¿Cuánto me cuesta cobrar con tarjeta y me conviene ofrecer 12 cuotas?

**Restricción importante:** el equipo no va a cambiar de herramientas. Los vendedores usan el celular y la oficina usa Google Sheets. La solución tiene que vivir ahí.

## La solución

| Necesidad | Pieza | Herramienta |
| --- | --- | --- |
| Que las cobranzas se carguen en el momento y bien | App móvil de carga de ventas y cobranzas, con foto del comprobante y validaciones | AppSheet |
| Una sola fuente de datos que la oficina entienda | Planilla con clientes, ventas, facturas, cobranzas, liquidaciones de tarjeta y reporte | Google Sheets |
| Detectar errores apenas se cargan y avisar vencimientos | Validación al editar, importación diaria de los CSV de facturación y de liquidaciones, y mails de alerta | Apps Script |
| Cruzar todo y calcular deuda, aging y DSO | Conciliación ventas → facturas → cobros → liquidaciones de tarjeta, con tests | Python + DuckDB, corrido a diario con GitHub Actions |
| Ver la situación de un vistazo | Una página para la dueña y otra para cobranzas | Power BI o Looker Studio |

## Cómo se tratan los cobros con tarjeta

Con tarjeta, el cobro y la llegada de la plata son dos momentos distintos:

1. **El cliente paga** con débito o crédito, en 1, 3, 6 o 12 cuotas. La factura queda cancelada: el cliente ya no debe.
2. **La deuda pasa a la procesadora** (tarjetas a cobrar) hasta que liquida.
3. **La procesadora liquida** después del plazo de acreditación del plan, y descuenta:

| Concepto | Detalle |
| --- | --- |
| Comisión | Menor en débito que en crédito |
| Costo financiero | Solo en cuotas sin interés para el cliente: lo absorbe la distribuidora y crece con la cantidad de cuotas |
| IVA sobre la comisión y el costo financiero | Se descuenta en la liquidación |
| Retenciones de IIBB, IVA y Ganancias | Se descuentan en la liquidación y se computan después como pago a cuenta |

**Simplificación:** las ventas en cuotas se liquidan en un solo pago (el comercio cobra el total anticipado y absorbe el costo financiero), no cuota por cuota.

Las comisiones, costos financieros, alícuotas y plazos cambian según la procesadora, el plan y la normativa vigente. Por eso son **supuestos ilustrativos** guardados en un archivo de configuración (`planes_tarjeta.csv`), fáciles de reemplazar por los de un cliente real.

## Indicadores

| Indicador | Definición |
| --- | --- |
| Saldo por cobrar | Facturado − cobrado imputado, por cliente |
| Aging | Saldo vencido según días desde el vencimiento: 0–30, 31–60, 61–90, más de 90 |
| DSO | Saldo por cobrar ÷ ventas facturadas del período × días del período |
| Ventas sin facturar | Pedidos entregados sin factura asociada |
| Cobranzas sin imputar | Pagos que no se pudieron asignar a una factura |
| % de ventas conciliadas | Pedidos entregados con factura y cobro que cierran |
| Plata en tránsito | Cobros con tarjeta todavía no liquidados, por procesadora y fecha estimada de acreditación |
| Costo de cobrar con tarjeta | (Comisión + costo financiero + IVA) ÷ monto cobrado, por plan |
| Cupones sin liquidar | Cupones que superaron su plazo de acreditación sin liquidación |

## Datos de prueba

**Período:** 4 meses, del 1 de agosto al 30 de noviembre de 2026. **Fecha de corte** para calcular deuda y aging: 30 de noviembre de 2026.

Volumen aproximado: 80 clientes, 1.600 pedidos, 1.600 facturas, 1.350 cobranzas, de las cuales unas 330 son con tarjeta, y sus liquidaciones.

## Errores sembrados en los datos de prueba

Los datos se generan con Python y traen errores a propósito, para que la solución demuestre que los encuentra:

| Error | Frecuencia aproximada | Quién lo detecta |
| --- | --- | --- |
| CUIT con dígito verificador inválido | 3 de los 80 clientes | Apps Script al editar |
| Pedido entregado sin factura | 2% de los pedidos | Conciliación |
| Factura duplicada | 0,5% de las facturas | Conciliación |
| Pago parcial | 10% de las cobranzas | Conciliación (saldo abierto) |
| Pago sin factura asignada | 5% de las cobranzas | Conciliación (sin imputar) |
| Monto mal tipeado (un cero de más o de menos) | 1% de las cobranzas | Apps Script y conciliación |
| Cheque rechazado | 5% de los cheques acreditados | Conciliación |
| Clientes con deuda de más de 90 días | 5 clientes | Aging y alertas |
| Cupón de tarjeta nunca liquidado | 2% de los cupones | Conciliación de tarjetas |
| Comisión liquidada distinta de la pactada | 3% de las liquidaciones | Conciliación contra los planes |
| Contracargo (el cliente desconoce el pago) | 2,5% de los cupones liquidados | La factura vuelve a quedar abierta |
| Cupón duplicado | 0,5% de los cupones | Conciliación de tarjetas |
