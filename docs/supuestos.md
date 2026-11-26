# Supuestos de los datos de prueba

Los datos de Distribuidora La Estiba son ficticios y se generan con `python scripts/generate_data.py` (semilla fija 42: siempre dan lo mismo). Los valores están elegidos para que el caso sea realista, no para reflejar una empresa ni una normativa puntual.

## Período y volumen

| Supuesto | Valor |
| --- | --- |
| Período | 1/8/2026 al 30/11/2026 |
| Fecha de corte (deuda y aging) | 30/11/2026 |
| Días con actividad | Lunes a viernes. No se cargan feriados |
| Pedidos | Promedio de 20 por día hábil, con clientes que compran más que otros |
| Importe de un pedido | Mediana de ARS 150.000, entre 25.000 y 1.500.000 |
| Entrega | Día hábil siguiente al pedido |
| Facturación | Entre 0 y 3 días hábiles después de la entrega |
| IVA | 21% sobre el neto. Factura A para responsables inscriptos, B para monotributistas |
| Vencimiento | Contado: el mismo día. Cuenta corriente: 15 o 30 días desde la emisión |

## Comportamiento de pago

| Perfil | Proporción | Cuándo paga |
| --- | --- | --- |
| Puntual | 65% | Entre 3 días antes y 5 días después del vencimiento |
| Con demora | 35% | Entre 8 y 45 días después del vencimiento |
| Moroso | 5 clientes | No paga lo facturado en agosto; el resto, entre 20 y 60 días tarde |

Los pagos del mismo cliente, el mismo día y con el mismo medio se agrupan en un recibo. Los cobros con tarjeta van siempre de a una factura por cupón.

## Tarjetas

Valores **ilustrativos**: las comisiones, costos financieros, alícuotas y plazos reales cambian según la procesadora, el plan y la normativa vigente. Están en `planes_tarjeta.csv` para poder reemplazarlos.

| Concepto | Valor |
| --- | --- |
| Comisión débito | 0,8% (Payway), 0,9% (Fiserv), 1,2% (Mercado Pago) |
| Comisión crédito | 1,8% (Payway), 1,9% (Fiserv), 2,2% (Mercado Pago) |
| Costo financiero de cuotas sin interés | 3 cuotas 5,5%; 6 cuotas 10%; 12 cuotas 19% |
| IVA sobre comisión y costo financiero | 21% |
| Retenciones sobre el bruto | IIBB 1,5%; IVA 1%; Ganancias 0,5% |
| Acreditación | Débito: 1 o 2 días hábiles. Crédito, en cualquier cantidad de cuotas: 10 días hábiles |

**Simplificación:** las ventas en cuotas se liquidan en un solo pago (cobro anticipado), no cuota por cuota.

## Hoja de respuestas

`data/generated/_errores_sembrados.csv` lista cada error sembrado con su tipo y el registro afectado. Los tests de la conciliación la usan para comprobar que se detectan todos.
