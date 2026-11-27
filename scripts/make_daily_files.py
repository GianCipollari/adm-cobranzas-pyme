"""Genera los archivos de un dia nuevo (1/12/2026) para probar la importacion de Apps Script.

- facturas_20261201.csv: factura los pedidos que quedaron pendientes al 30/11.
- liquidaciones_20261201.csv: liquida los cupones de tarjeta que estaban en transito,
  salvo los que en los datos de prueba nunca se liquidan (error sembrado).

Lee los CSV de data/generated (hay que correr antes generate_data.py) y escribe en
data/generated/entrada/. Las columnas quedan en el mismo orden que las pestañas.

Uso: python scripts/make_daily_files.py
"""
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "data" / "generated"
OUT = GEN / "entrada"
DIA = date(2026, 12, 1)
DIAS_VTO = {"contado": 0, "cc15": 15, "cc30": 30}
RET_IIBB, RET_IVA, RET_GAN, IVA = 0.015, 0.01, 0.005, 0.21


def leer(nombre):
    return pd.read_csv(GEN / f"{nombre}.csv", dtype={"cupon_nro": str})


def facturas_del_dia():
    pedidos, clientes, facturas = leer("pedidos"), leer("clientes"), leer("facturas")
    cli = clientes.set_index("cliente_id")
    pendientes = pedidos[pedidos["estado"] == "pendiente"]
    ultimo = facturas.groupby("tipo")["numero"].max().to_dict()

    filas = []
    for p in pendientes.itertuples():
        c = cli.loc[p.cliente_id]
        tipo = "A" if c["condicion_iva"] == "RI" else "B"
        ultimo[tipo] = ultimo.get(tipo, 0) + 1
        neto = round(p.importe_total / 1.21, 2)
        filas.append({
            "factura_id": f"{tipo}-0003-{ultimo[tipo]:08d}", "tipo": tipo, "punto_venta": 3,
            "numero": ultimo[tipo], "fecha_emision": DIA, "cliente_id": p.cliente_id,
            "cuit": c["cuit"], "pedido_id": p.pedido_id, "importe_neto": neto,
            "iva": round(p.importe_total - neto, 2), "importe_total": p.importe_total,
            "fecha_vencimiento": DIA + timedelta(days=DIAS_VTO[c["condicion_pago"]]),
        })
    return pd.DataFrame(filas, columns=facturas.columns)


def liquidaciones_del_dia():
    cobranzas, liqs, planes = leer("cobranzas"), leer("liquidaciones_tarjeta"), leer("planes_tarjeta")
    errores = pd.read_csv(GEN / "_errores_sembrados.csv", dtype=str)
    nunca = set(errores.loc[errores["tipo_error"] == "cupon_no_liquidado", "detalle"])
    liquidados = set(liqs["cupon_nro"])

    tarjetas = cobranzas[cobranzas["medio"] == "tarjeta"].drop_duplicates("cupon_nro")
    en_transito = tarjetas[~tarjetas["cupon_nro"].isin(liquidados | nunca)]
    plan = planes.set_index(["procesadora", "tarjeta_tipo", "cuotas"])
    n = int(liqs["liquidacion_id"].str[4:].astype(int).max())

    filas = []
    for t in en_transito.itertuples():
        p = plan.loc[(t.procesadora, t.tarjeta_tipo, int(t.cuotas))]
        bruto = t.importe
        comision = round(bruto * p["comision_pct"], 2)
        costo_fin = round(bruto * p["costo_financiero_pct"], 2)
        iva = round((comision + costo_fin) * IVA, 2)
        rets = [round(bruto * r, 2) for r in (RET_IIBB, RET_IVA, RET_GAN)]
        n += 1
        filas.append({
            "liquidacion_id": f"LIQ-{n:05d}", "procesadora": t.procesadora, "fecha_pago": DIA,
            "cupon_nro": t.cupon_nro, "fecha_operacion": t.fecha, "cuotas": int(t.cuotas),
            "importe_bruto": bruto, "comision": comision, "costo_financiero": costo_fin,
            "iva": iva, "ret_iibb": rets[0], "ret_iva": rets[1], "ret_ganancias": rets[2],
            "importe_neto": round(bruto - comision - costo_fin - iva - sum(rets), 2),
            "es_contracargo": False,
        })
    return pd.DataFrame(filas, columns=liqs.columns)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fac, liq = facturas_del_dia(), liquidaciones_del_dia()
    fac.to_csv(OUT / "facturas_20261201.csv", index=False)
    liq.to_csv(OUT / "liquidaciones_20261201.csv", index=False)
    print(f"facturas_20261201.csv       {len(fac):>4} filas")
    print(f"liquidaciones_20261201.csv  {len(liq):>4} filas")


if __name__ == "__main__":
    main()
