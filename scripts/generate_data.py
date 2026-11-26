"""Genera los datos de prueba de Distribuidora La Estiba (empresa ficticia).

4 meses (1/8/2026 al 30/11/2026), corte el 30/11/2026. Escribe en data/generated/
un CSV por pestaña del Google Sheets, mas una "hoja de respuestas" con cada error
sembrado (_errores_sembrados.csv), que despues usan los tests para verificar que
la conciliacion los encuentra todos.

Montos en pesos argentinos con punto decimal. Semilla fija: siempre da lo mismo.
Ver docs/caso.md para el caso y docs/supuestos.md para los valores ilustrativos.

Uso (desde la raiz del repo, con el entorno activado):
    python scripts/generate_data.py
"""
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "generated"
RNG = np.random.default_rng(42)

START = date(2026, 8, 1)
END = date(2026, 11, 30)          # ultimo dia con datos y fecha de corte
N_CLIENTES = 80
PEDIDOS_POR_DIA = 20              # promedio por dia habil

ERRORES = []                      # hoja de respuestas


def error(tipo, tabla, registro_id, detalle=""):
    ERRORES.append({"tipo_error": tipo, "tabla": tabla,
                    "registro_id": registro_id, "detalle": detalle})


# --- Utilidades -------------------------------------------------------------

def dias_habiles(desde, hasta):
    """Lunes a viernes. No se cargan feriados (simplificacion documentada)."""
    d, out = desde, []
    while d <= hasta:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def sumar_habiles(d, n):
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def cuit_valido(prefijo, dni):
    """CUIT con digito verificador calculado (modulo 11)."""
    base = f"{prefijo}{dni:08d}"
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    resto = sum(int(c) * p for c, p in zip(base, pesos)) % 11
    dv = 0 if resto == 0 else 11 - resto
    if dv == 10:               # caso que en la practica obliga a cambiar el prefijo
        return None
    return f"{prefijo}-{dni:08d}-{dv}"


def money(x):
    return round(float(x), 2)


# --- Vendedores -------------------------------------------------------------

vendedores = pd.DataFrame([
    {"vendedor_id": "V01", "nombre": "Lucas Ferreyra", "email": "lucas@laestiba.example"},
    {"vendedor_id": "V02", "nombre": "Sofia Aguirre", "email": "sofia@laestiba.example"},
    {"vendedor_id": "V03", "nombre": "Martin Ibarra", "email": "martin@laestiba.example"},
])


# --- Clientes ---------------------------------------------------------------

TIPOS = ["Almacen", "Autoservicio", "Kiosco", "Despensa", "Restaurante", "Minimercado"]
NOMBRES = ["Don Pepe", "La Esquina", "El Faro", "San Martin", "Los Pinos", "La Rueda",
           "El Puerto", "Doña Rosa", "La Estacion", "El Molino", "Las Heras", "Del Centro",
           "La Plaza", "El Trebol", "Villa Mitre", "La Loma", "El Sol", "Patagonia",
           "Del Sur", "La Bahia", "El Palomar", "Tres Hermanos", "La Union", "El Ancla"]
LOCALIDADES = (["Bahia Blanca"] * 12 + ["Punta Alta"] * 3 +
               ["Ingeniero White"] * 2 + ["Monte Hermoso", "General Cerri"])

clientes = []
usados = set()
for i in range(1, N_CLIENTES + 1):
    while True:
        nombre = f"{RNG.choice(TIPOS)} {RNG.choice(NOMBRES)}"
        if nombre not in usados:
            usados.add(nombre)
            break
    ri = RNG.random() < 0.40
    while True:
        cuit = cuit_valido("30" if ri else "20", int(RNG.integers(10_000_000, 45_000_000)))
        if cuit:
            break
    clientes.append({
        "cliente_id": f"C{i:03d}",
        "razon_social": nombre,
        "cuit": cuit,
        "condicion_iva": "RI" if ri else "monotributo",
        "condicion_pago": RNG.choice(["contado", "cc15", "cc30"], p=[0.30, 0.35, 0.35]),
        "vendedor_id": f"V0{(i - 1) % 3 + 1}",
        "limite_credito": int(RNG.choice([500_000, 1_000_000, 2_000_000, 3_000_000])),
        "localidad": RNG.choice(LOCALIDADES),
    })
clientes = pd.DataFrame(clientes)

# Perfil de pago (no va a la planilla: define el comportamiento simulado)
perfil = RNG.choice(["puntual", "demora"], size=N_CLIENTES, p=[0.65, 0.35]).astype(object)
morosos = RNG.choice(clientes.index[clientes["condicion_pago"] == "cc15"], 5, replace=False)
perfil[morosos] = "moroso"
clientes["_perfil"] = perfil
for idx in morosos:
    error("deuda_mayor_90_dias", "clientes", clientes.at[idx, "cliente_id"],
          "deja de pagar facturas desde agosto")

# Error: 3 CUIT con digito verificador invalido
for idx in RNG.choice(clientes.index, 3, replace=False):
    cuit = clientes.at[idx, "cuit"]
    dv_malo = (int(cuit[-1]) + int(RNG.integers(1, 9))) % 10
    clientes.at[idx, "cuit"] = cuit[:-1] + str(dv_malo)
    error("cuit_invalido", "clientes", clientes.at[idx, "cliente_id"], clientes.at[idx, "cuit"])


# --- Pedidos ----------------------------------------------------------------

habiles = dias_habiles(START, END)
peso_cliente = RNG.gamma(2.0, 1.0, N_CLIENTES)
peso_cliente /= peso_cliente.sum()

pedidos = []
n = 0
for d in habiles:
    for idx in RNG.choice(N_CLIENTES, RNG.poisson(PEDIDOS_POR_DIA), p=peso_cliente):
        n += 1
        c = clientes.iloc[idx]
        importe = money(np.clip(RNG.lognormal(np.log(150_000), 0.6), 25_000, 1_500_000))
        entrega = sumar_habiles(d, 1)
        if entrega > END:
            estado, entrega = "pendiente", None
        else:
            estado = RNG.choice(["entregado", "anulado"], p=[0.98, 0.02])
            if estado == "anulado":
                entrega = None
        pedidos.append({
            "pedido_id": f"P{n:05d}", "fecha_pedido": d, "cliente_id": c["cliente_id"],
            "vendedor_id": c["vendedor_id"], "importe_total": importe,
            "estado": estado, "fecha_entrega": entrega,
        })
# Cada moroso tiene un pedido la primera semana: su deuda llega a mas de 90 dias al corte
for idx in morosos:
    n += 1
    c = clientes.iloc[idx]
    pedidos.append({
        "pedido_id": f"P{n:05d}", "fecha_pedido": habiles[0], "cliente_id": c["cliente_id"],
        "vendedor_id": c["vendedor_id"],
        "importe_total": money(RNG.lognormal(np.log(150_000), 0.4)),
        "estado": "entregado", "fecha_entrega": sumar_habiles(habiles[0], 1),
    })
pedidos = pd.DataFrame(pedidos).sort_values(["fecha_pedido", "pedido_id"], ignore_index=True)


# --- Facturas ---------------------------------------------------------------

DIAS_VTO = {"contado": 0, "cc15": 15, "cc30": 30}
numeros = {"A": 0, "B": 0}
facturas = []
cli = clientes.set_index("cliente_id")

for p in pedidos[pedidos["estado"] == "entregado"].itertuples():
    if RNG.random() < 0.02:                       # error: entregado sin facturar
        error("pedido_sin_factura", "pedidos", p.pedido_id)
        continue
    c = cli.loc[p.cliente_id]
    emision = sumar_habiles(p.fecha_entrega, int(RNG.choice([0, 0, 1, 1, 2, 3])))
    if emision > END:
        emision = END
    tipo = "A" if c["condicion_iva"] == "RI" else "B"
    copias = 2 if RNG.random() < 0.005 else 1     # error: factura duplicada
    for k in range(copias):
        numeros[tipo] += 1
        fid = f"{tipo}-0003-{numeros[tipo]:08d}"
        neto = money(p.importe_total / 1.21)
        facturas.append({
            "factura_id": fid, "tipo": tipo, "punto_venta": 3, "numero": numeros[tipo],
            "fecha_emision": emision, "cliente_id": p.cliente_id, "cuit": c["cuit"],
            "pedido_id": p.pedido_id, "importe_neto": neto,
            "iva": money(p.importe_total - neto), "importe_total": p.importe_total,
            "fecha_vencimiento": emision + timedelta(days=DIAS_VTO[c["condicion_pago"]]),
            "_duplicada": k == 1,
        })
        if k == 1:
            error("factura_duplicada", "facturas", fid, f"duplica el pedido {p.pedido_id}")
facturas = pd.DataFrame(facturas)


# --- Planes de tarjeta (supuestos ilustrativos) -----------------------------

planes = []
for proc, ajuste, dias_deb in [("Payway", 0.0, 2), ("Fiserv", 0.001, 2), ("Mercado Pago", 0.004, 1)]:
    planes.append({"procesadora": proc, "tarjeta_tipo": "debito", "cuotas": 1,
                   "comision_pct": round(0.008 + ajuste, 4), "costo_financiero_pct": 0.0,
                   "dias_acreditacion": dias_deb})
    for cuotas, cf in [(1, 0.0), (3, 0.055), (6, 0.10), (12, 0.19)]:
        planes.append({"procesadora": proc, "tarjeta_tipo": "credito", "cuotas": cuotas,
                       "comision_pct": round(0.018 + ajuste, 4), "costo_financiero_pct": cf,
                       "dias_acreditacion": 10})
planes = pd.DataFrame(planes)
plan_idx = planes.set_index(["procesadora", "tarjeta_tipo", "cuotas"])

RET_IIBB, RET_IVA, RET_GAN, IVA = 0.015, 0.01, 0.005, 0.21


# --- Cobranzas --------------------------------------------------------------

BANCOS = ["Banco Nacion", "Banco Provincia", "Banco Galicia", "Banco Santander", "BBVA", "Banco Credicoop"]
MEDIOS = {
    "contado": (["efectivo", "transferencia", "mercado_pago", "tarjeta"], [0.25, 0.25, 0.15, 0.35]),
    "cc": (["transferencia", "cheque", "tarjeta", "efectivo"], [0.40, 0.25, 0.20, 0.15]),
}

eventos = []      # un evento = un pago (total o parcial) de una factura
for f in facturas[~facturas["_duplicada"]].itertuples():
    c = cli.loc[f.cliente_id]
    if c["_perfil"] == "puntual":
        atraso = int(RNG.integers(-3, 6))
    elif c["_perfil"] == "demora":
        atraso = int(RNG.integers(8, 45))
    else:  # moroso: no paga lo de agosto, paga tarde el resto
        atraso = 999 if f.fecha_emision.month == 8 else int(RNG.integers(20, 60))
    fecha_pago = max(f.fecha_vencimiento + timedelta(days=atraso), f.fecha_emision)
    if fecha_pago > END:
        continue                                  # factura abierta al corte

    grupo = "contado" if c["condicion_pago"] == "contado" else "cc"
    opciones, probs = MEDIOS[grupo]
    medio = RNG.choice(opciones, p=probs)
    if RNG.random() < 0.10:                       # error: pago parcial
        parte = money(f.importe_total * RNG.uniform(0.4, 0.8))
        eventos.append((f, fecha_pago, medio, parte))
        segunda = fecha_pago + timedelta(days=int(RNG.integers(10, 40)))
        if RNG.random() < 0.5 and segunda <= END:
            eventos.append((f, segunda, medio, money(f.importe_total - parte)))
        else:
            error("pago_parcial", "facturas", f.factura_id, "queda saldo abierto")
    else:
        eventos.append((f, fecha_pago, medio, f.importe_total))

# Agrupar en recibos: mismo cliente, misma fecha y mismo medio = un recibo
# (las tarjetas van siempre de a una factura por cupon)
cobranzas, recibos, n_cob, n_rec, n_cupon = [], {}, 0, 0, 0
for f, fecha_pago, medio, importe in sorted(eventos, key=lambda e: (e[1], e[0].cliente_id)):
    c = cli.loc[f.cliente_id]
    clave = (f.cliente_id, fecha_pago, medio) if medio != "tarjeta" else None
    if clave and clave in recibos:
        recibo = recibos[clave]
    else:
        n_rec += 1
        recibo = f"R-{n_rec:06d}"
        if clave:
            recibos[clave] = recibo
    n_cob += 1
    fila = {
        "cobranza_id": f"COB-{n_cob:05d}", "recibo_nro": recibo, "fecha": fecha_pago,
        "cliente_id": f.cliente_id, "vendedor_id": c["vendedor_id"],
        "medio": medio, "importe": importe, "factura_id": f.factura_id,
        "cheque_numero": None, "cheque_banco": None, "cheque_fecha_pago": None,
        "cheque_estado": None, "tarjeta_tipo": None, "cuotas": None,
        "procesadora": None, "cupon_nro": None,
    }
    if medio == "cheque":
        fpago = fecha_pago + timedelta(days=int(RNG.choice([0, 30, 60], p=[0.4, 0.4, 0.2])))
        estado = "en_cartera" if fpago > END else "acreditado"
        if estado == "acreditado" and RNG.random() < 0.05:   # error: cheque rechazado
            estado = "rechazado"
            error("cheque_rechazado", "cobranzas", fila["cobranza_id"], f.factura_id)
        fila.update(cheque_numero=str(int(RNG.integers(10_000_000, 99_999_999))),
                    cheque_banco=RNG.choice(BANCOS), cheque_fecha_pago=fpago,
                    cheque_estado=estado)
    if medio == "tarjeta":
        n_cupon += 1
        tipo_t = RNG.choice(["debito", "credito"], p=[0.40, 0.60])
        cuotas = 1 if tipo_t == "debito" else int(RNG.choice([1, 3, 6, 12], p=[0.40, 0.30, 0.20, 0.10]))
        fila.update(tarjeta_tipo=tipo_t, cuotas=cuotas,
                    procesadora=RNG.choice(["Payway", "Fiserv", "Mercado Pago"], p=[0.45, 0.25, 0.30]),
                    cupon_nro=f"{int(RNG.integers(100_000, 999_999))}{n_cupon:03d}")
    cobranzas.append(fila)
cobranzas = pd.DataFrame(cobranzas)

# Error: pago sin factura asignada (5%, sin tocar tarjetas ni cheques)
simples = cobranzas.index[cobranzas["medio"].isin(["efectivo", "transferencia", "mercado_pago"])]
for idx in RNG.choice(simples, int(len(cobranzas) * 0.05), replace=False):
    error("pago_sin_imputar", "cobranzas", cobranzas.at[idx, "cobranza_id"],
          f"deberia imputarse a {cobranzas.at[idx, 'factura_id']}")
    cobranzas.at[idx, "factura_id"] = None

# Error: monto mal tipeado (1%): un cero de mas o de menos
candidatas = cobranzas.index[cobranzas["factura_id"].notna() & (cobranzas["medio"] != "tarjeta")]
for idx in RNG.choice(candidatas, max(1, int(len(cobranzas) * 0.01)), replace=False):
    original = cobranzas.at[idx, "importe"]
    factor = RNG.choice([10, 0.1])
    cobranzas.at[idx, "importe"] = money(original * factor)
    error("monto_mal_tipeado", "cobranzas", cobranzas.at[idx, "cobranza_id"],
          f"cargado {cobranzas.at[idx, 'importe']} en lugar de {original}")


# --- Liquidaciones de tarjeta ----------------------------------------------

tarjetas = cobranzas[cobranzas["medio"] == "tarjeta"]
liquidaciones, n_liq = [], 0
for t in tarjetas.itertuples():
    plan = plan_idx.loc[(t.procesadora, t.tarjeta_tipo, t.cuotas)]
    fecha_liq = sumar_habiles(t.fecha, int(plan["dias_acreditacion"]))
    if fecha_liq > END:
        continue                                  # en transito al corte
    if RNG.random() < 0.02:                       # error: cupon nunca liquidado
        error("cupon_no_liquidado", "cobranzas", t.cobranza_id, t.cupon_nro)
        continue
    comision_pct = plan["comision_pct"]
    if RNG.random() < 0.03:                       # error: comision distinta de la pactada
        comision_pct = round(comision_pct + 0.005, 4)
        error("comision_distinta", "liquidaciones_tarjeta", t.cupon_nro,
              f"{comision_pct} en lugar de {plan['comision_pct']}")
    bruto = t.importe
    comision = money(bruto * comision_pct)
    costo_fin = money(bruto * plan["costo_financiero_pct"])
    iva = money((comision + costo_fin) * IVA)
    rets = [money(bruto * r) for r in (RET_IIBB, RET_IVA, RET_GAN)]
    n_liq += 1
    liquidaciones.append({
        "liquidacion_id": f"LIQ-{n_liq:05d}", "procesadora": t.procesadora,
        "fecha_pago": fecha_liq, "cupon_nro": t.cupon_nro, "fecha_operacion": t.fecha,
        "cuotas": t.cuotas, "importe_bruto": bruto, "comision": comision,
        "costo_financiero": costo_fin, "iva": iva, "ret_iibb": rets[0],
        "ret_iva": rets[1], "ret_ganancias": rets[2],
        "importe_neto": money(bruto - comision - costo_fin - iva - sum(rets)),
        "es_contracargo": False,
    })
    if RNG.random() < 0.025:                      # error: contracargo
        fecha_cc = sumar_habiles(fecha_liq, int(RNG.integers(5, 20)))
        if fecha_cc <= END:
            n_liq += 1
            liquidaciones.append({
                "liquidacion_id": f"LIQ-{n_liq:05d}", "procesadora": t.procesadora,
                "fecha_pago": fecha_cc, "cupon_nro": t.cupon_nro, "fecha_operacion": t.fecha,
                "cuotas": t.cuotas, "importe_bruto": -bruto, "comision": 0.0,
                "costo_financiero": 0.0, "iva": 0.0, "ret_iibb": 0.0, "ret_iva": 0.0,
                "ret_ganancias": 0.0, "importe_neto": -bruto, "es_contracargo": True,
            })
            error("contracargo", "liquidaciones_tarjeta", t.cupon_nro, t.factura_id)
liquidaciones = pd.DataFrame(liquidaciones)

# Error: cupon duplicado (0,5%): el vendedor cargo dos veces el mismo cobro
dup_idx = RNG.choice(tarjetas.index, max(1, int(len(tarjetas) * 0.005)), replace=False)
duplicados = cobranzas.loc[dup_idx].copy()
for k, idx in enumerate(duplicados.index):
    n_cob += 1
    duplicados.at[idx, "cobranza_id"] = f"COB-{n_cob:05d}"
    error("cupon_duplicado", "cobranzas", f"COB-{n_cob:05d}",
          f"repite el cupon {duplicados.at[idx, 'cupon_nro']}")
cobranzas = pd.concat([cobranzas, duplicados], ignore_index=True)


# --- Escribir ---------------------------------------------------------------

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    salidas = {
        "vendedores": vendedores,
        "clientes": clientes.drop(columns="_perfil"),
        "pedidos": pedidos,
        "facturas": facturas.drop(columns="_duplicada"),
        "cobranzas": cobranzas.astype({"cuotas": "Int64"}),
        "liquidaciones_tarjeta": liquidaciones.astype({"cuotas": "Int64"}),
        "planes_tarjeta": planes,
        "_errores_sembrados": pd.DataFrame(ERRORES),
    }
    for nombre, df in salidas.items():
        df.to_csv(OUT / f"{nombre}.csv", index=False)
        print(f"{nombre + '.csv':<28} {len(df):>6} filas")
    print("\nErrores sembrados por tipo:")
    print(pd.DataFrame(ERRORES)["tipo_error"].value_counts().to_string())


if __name__ == "__main__":
    main()
