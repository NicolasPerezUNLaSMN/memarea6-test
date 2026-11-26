"""meMareaVI — Boletín meteorológico para navegantes METAREA VI.

Flujo principal: el pronosticador escribe (o arrastra) su borrador en texto
claro, se interpreta a datos estructurados (por reglas, o con IA si se configura)
y el código arma los dos
.txt (WWST01 castellano, WWST02 inglés) con reglas fijas del catálogo.
La pestaña «Ajuste fino» permite corregir los datos interpretados a mano.
"""
import copy
import datetime as dt
import json
import re
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import almacen, catalogo, estadisticas, ia, interpretar, modelo, registro, render, validar  # noqa: E402

ESTATICO = Path(__file__).resolve().parent / "static"
st.set_page_config(page_title="meMareaVI", page_icon=str(ESTATICO / "favicon.png"), layout="wide")
CAT = catalogo.cargar()
ZONAS = {z["id"]: z for z in catalogo.todas_las_zonas(CAT)}
DIRS = CAT["viento"]["direcciones"]
FEN = CAT["fenomenos"]
VIS = CAT["visibilidad"]["valores"]

# ======================================================================
# Estado
# ======================================================================
ss = st.session_state
if "b" not in ss:
    ss.b = modelo.nuevo_boletin(CAT)
    ss.ver = 0            # al cambiar, los widgets de datos se recargan desde ss.b
    ss.tver = 0           # ídem para el cuadro de texto claro
    ss.texto = interpretar.PLANTILLA
    ss.salida = None
    ss.foto = None        # datos con los que se generó la salida
    ss.dudas = []
    ss.gen = 0
    ss.archivo_id = None
    ss.json_importado = None
B = ss.b


def K(*partes) -> str:
    return f"v{ss.ver}:" + ":".join(map(str, partes))


def foto(b) -> str:
    return json.dumps(b, sort_keys=True, ensure_ascii=False)


def generar_salida():
    registro.numerar(CAT, ss.b)                     # números nuevos, olas y ceses sugeridos
    ss.salida = render.generar_todo(CAT, ss.b)
    ss.foto = foto(ss.b)
    ss.guardado = almacen.guardar(ss.b, ss.salida, ss.get("autor", ""))
    if not validar.validar(CAT, ss.b)[0]:           # registro y estadísticas: solo boletines sin errores
        registro.registrar(CAT, ss.b, autor=ss.get("autor", ""))
        estadisticas.exportar(CAT, ss.b, autor=ss.get("autor", ""))
    ss.gen += 1


def recargar(nuevo: dict | None = None):
    if nuevo is not None:
        ss.b = modelo.completar(nuevo, CAT)
        ss.texto = ss.b.get("texto_claro") or interpretar.PLANTILLA
        ss.tver += 1
        ss.dudas = []
    ss.ver += 1
    ss.salida = None
    st.rerun()


# ---------------------------------------------------------------- widgets
def t_in(label, obj, campo, key, **kw):
    obj[campo] = st.text_input(label, value=obj.get(campo, ""), key=key, **kw)


def sel(label, opciones, obj, campo, key, fmt=None, **kw):
    actual = obj.get(campo, opciones[0])
    idx = opciones.index(actual) if actual in opciones else 0
    obj[campo] = st.selectbox(label, opciones, index=idx, key=key,
                              format_func=fmt or (lambda x: x if x else "—"), **kw)


def chk(label, obj, campo, key, **kw):
    obj[campo] = st.checkbox(label, value=bool(obj.get(campo)), key=key, **kw)


def multi(label, opciones, obj, campo, key, fmt=None, **kw):
    kw.setdefault("placeholder", "Elegí…")
    obj[campo] = st.multiselect(label, opciones, default=[x for x in obj.get(campo, []) if x in opciones],
                                key=key, format_func=fmt or str, **kw)


def fmt_dic(dic, vacio="—"):
    return lambda k: dic[k]["es"] if k and dic[k]["es"] else vacio


def vista_previa(fn):
    try:
        es, en = fn("es"), fn("en")
    except Exception:  # datos incompletos: no mostrar nada
        return
    st.code(f"{es}\n{en}", language=None, wrap_lines=True)


# ======================================================================
# Barra lateral
# ======================================================================
with st.sidebar:
    st.header("Boletín")
    fecha = st.date_input("Fecha de inicio del pronóstico", value=dt.date.fromisoformat(B["fecha"]),
                          key=K("fecha"), format="DD/MM/YYYY")
    B["fecha"] = fecha.isoformat()
    sel("Corrida", ["00", "12"], B, "corrida", K("corrida"), fmt=lambda x: f"{x} UTC")
    t = render.tiempos(B)
    st.caption(f"Encabezado **WWST01 SABM {t['id']}** · válido hasta "
               f"{t['fin']:%d/%m} {t['fin_hora']} UTC · sinopsis de las {t['sinop']} UTC")
    ss.autor = st.text_input("Pronosticador/a", value=ss.get("autor", ""), key="autor_in")

    st.divider()
    st.subheader("Historial")
    guardados = almacen.listar()
    if guardados:
        if st.button("Partir del último boletín", use_container_width=True,
                     help=f"Trae el texto y los datos de {guardados[0]} y avanza a la corrida siguiente."):
            recargar(modelo.siguiente_desde(almacen.cargar(guardados[0])))
        elegido = st.selectbox("Boletines guardados", guardados)
        if st.button("Abrir tal cual", use_container_width=True):
            recargar(almacen.cargar(elegido))
    else:
        st.caption("Todavía no hay boletines guardados.")
    if st.button("Empezar en blanco", use_container_width=True):
        recargar(modelo.nuevo_boletin(CAT))

    with st.expander("Numeración de avisos"):
        res = registro.resumen()
        st.caption(f"Último aviso de temporal: **{res['ultimo_viento']}** · último de olas: **{res['ultimo_olas']}**  \n"
                   f"Vigentes de temporal: {', '.join(map(str, res['vigentes_viento'])) or 'ninguno'}  \n"
                   f"Vigentes de olas: {', '.join(f'{n} ({a})' for n, a in res['vigentes_olas'].items()) or 'ninguno'}")
        st.caption("Para empezar (una sola vez): el último número usado en el sistema anterior y los avisos vigentes.")
        reg_actual = registro.cargar()
        arr = reg_actual["arranque"]
        c1, c2 = st.columns(2)
        anio = c1.number_input("Año", value=int(arr.get("anio") or dt.date.today().year), step=1, key="arr_anio")
        ult_v = c2.number_input("Último de temporal", value=int(arr.get("viento") or 0), step=1, min_value=0, key="arr_v")
        ult_o = c1.number_input("Último de olas", value=int(arr.get("olas") or 0), step=1, min_value=0, key="arr_o")
        vig_txt = c2.text_input("Vigentes de temporal", value=", ".join(map(str, arr.get("vigentes_viento", []))),
                                key="arr_vig", placeholder="483, 484")
        if st.button("Guardar punto de partida", use_container_width=True):
            reg_actual["arranque"] = {"anio": int(anio), "viento": int(ult_v), "olas": int(ult_o),
                                      "vigentes_viento": [int(x) for x in re.findall(r"\d+", vig_txt)]}
            registro.guardar(reg_actual)
            st.success("Guardado.")

    with st.expander("Datos para estadísticas"):
        st.caption("Avisos y pronósticos de cada boletín generado sin errores, en CSV (se abren con Excel).")
        for ruta in estadisticas.archivos():
            st.download_button(f"⬇ {ruta.name}", ruta.read_bytes(), file_name=ruta.name, mime="text/csv",
                               use_container_width=True, key=f"csv_{ruta.name}")
        if not estadisticas.archivos():
            st.caption("Todavía no hay datos.")

    with st.expander("Importar / exportar datos"):
        st.download_button("Descargar datos (.json)", json.dumps(B, ensure_ascii=False, indent=1),
                           file_name=f"boletin_{B['fecha']}_{B['corrida']}Z.json", use_container_width=True)
        subido = st.file_uploader("Abrir datos .json", type="json")
        if subido is not None and ss.json_importado != subido.file_id:
            ss.json_importado = subido.file_id
            recargar(json.load(subido))

LOGO = re.sub(r"<!--.*?-->|\s*\n\s*", "", (ESTATICO / "logo.svg").read_text(encoding="utf-8"))
LOGO = LOGO.replace("<svg ", '<svg width="58" height="58" ', 1)
st.markdown(
    '<div style="display:flex;align-items:center;gap:14px;margin:-1.2rem 0 .6rem">' + LOGO + "<div>"
    '<div style="font-size:2.2rem;font-weight:800;line-height:1.05;letter-spacing:-.01em">'
    '<span style="font-weight:400">me</span>Marea<span style="color:#E0563A">VI</span></div>'
    '<div style="font-size:.95rem;opacity:.72">Boletín meteorológico para navegantes · METAREA VI</div>'
    "</div></div>",
    unsafe_allow_html=True,
)
tab_bol, tab_fino = st.tabs(["Boletín", "Ajuste fino"])

# ======================================================================
# BOLETÍN: texto claro → resultado
# ======================================================================
with tab_bol:
    izq, der = st.columns([1, 1.15], gap="large")

    with izq:
        st.subheader("Texto del pronóstico")
        archivo = st.file_uploader("Arrastrá el Word, PDF o .txt, o escribí directamente abajo",
                                   type=["docx", "pdf", "txt"], key="archivo")
        if archivo is not None and archivo.file_id != ss.archivo_id:
            ss.archivo_id = archivo.file_id
            ss.texto = interpretar.leer_archivo(archivo.getvalue(), archivo.name)
            ss.tver += 1
            st.rerun()
        ss.texto = st.text_area("Texto claro", value=ss.texto, height=560, key=f"texto_{ss.tver}",
                                label_visibility="collapsed")
        st.markdown("**Información de hielos**")
        arch_h = st.file_uploader("Adjuntá el archivo de hielos (NAVAREA) o pegá el texto abajo",
                                  type=["txt"], key="archivo_hielos")
        if arch_h is not None and arch_h.file_id != ss.get("hielos_id"):
            ss.hielos_id = arch_h.file_id
            B["hielos"] = interpretar.leer_archivo(arch_h.getvalue(), arch_h.name)
            ss.ver += 1
            st.rerun()
        B["hielos"] = st.text_area("Hielos", value=B.get("hielos", ""), key=K("hielos"), height=110,
                                   label_visibility="collapsed",
                                   placeholder="SEA ICE AND ICEBERGS REPORT 221400 UTC … / INFORME DE HIELOS MARINOS …")
        if B["hielos"].strip():
            with st.expander("Cómo queda en el boletín"):
                st.code(f"{render.hielos(CAT, B['hielos'], 'es')}\n\n{render.hielos(CAT, B['hielos'], 'en')}",
                        language=None, wrap_lines=True)
        st.markdown("**Avisos de olas**")
        arch_o = st.file_uploader("Adjuntá el archivo de olas (BOL_METAREA_VI_ING) o pegá el texto abajo",
                                  type=["txt"], key="archivo_olas")
        if arch_o is not None and arch_o.file_id != ss.get("olas_id"):
            ss.olas_id = arch_o.file_id
            B["olas"] = interpretar.leer_archivo(arch_o.getvalue(), arch_o.name)
            B["olas_excluir"], B["olas_incluir"] = [], []
            ss.ver += 1
            st.rerun()
        B["olas"] = st.text_area("Olas", value=B.get("olas", ""), key=K("olas"), height=90,
                                 label_visibility="collapsed",
                                 placeholder="PRONOSTICO VALIDO DESDE … / AREA DRAKE / 150900 - 152100 UTC / WARNING: …")
        if B["olas"].strip():
            from core import olas as olas_mod
            datos_olas = olas_mod.leer(B["olas"])
            if not datos_olas["avisos"]:
                st.caption("El archivo no trae avisos de olas (líneas «WARNING»).")
            else:
                with st.expander(f"Avisos de olas encontrados ({len(datos_olas['avisos'])}) — destildá los que no van",
                                 expanded=True):
                    excluir, incluir = set(B.get("olas_excluir", [])), set(B.get("olas_incluir", []))
                    for a in datos_olas["avisos"]:
                        txt = olas_mod.linea(CAT, ZONAS, a, "es") or a["original"]
                        fuera = olas_mod.fuera_del_boletin(CAT, a["area"])
                        if fuera:
                            txt += "  (subárea antártica, fuera del boletín)"
                        marcado = st.checkbox(txt, value=olas_mod.incluido(CAT, B, a), key=K("ola", a["clave"]))
                        excluir.discard(a["clave"])
                        incluir.discard(a["clave"])
                        if fuera and marcado:
                            incluir.add(a["clave"])
                        elif not fuera and not marcado:
                            excluir.add(a["clave"])
                    B["olas_excluir"], B["olas_incluir"] = sorted(excluir), sorted(incluir)

        if st.button("Interpretar y generar", type="primary", use_container_width=True,
                     disabled=not ss.texto.strip()):
            with st.spinner("Leyendo el pronóstico…"):
                try:
                    datos = interpretar.interpretar_texto(CAT, ss.texto)
                except Exception as e:  # noqa: BLE001
                    st.error(f"No se pudo interpretar el texto: {e}")
                    st.stop()
            base = {"fecha": B["fecha"], "corrida": B["corrida"], "hielos": B["hielos"], "olas": B.get("olas", ""),
                    "olas_excluir": B.get("olas_excluir", []), "olas_incluir": B.get("olas_incluir", []),
                    "texto_claro": ss.texto}
            ss.b, ss.dudas = interpretar.a_boletin(CAT, datos, base)
            ss.ver += 1
            generar_salida()
            st.rerun()

    with der:
        st.subheader("Resultado")
        if ss.salida is None:
            st.info("Cuando toques «Interpretar y generar», acá aparecen los dos textos y lo que haya que revisar.")
        else:
            errores, advertencias = validar.validar(CAT, B)
            if foto(B) != ss.foto:
                st.warning("Cambiaste datos en «Ajuste fino» después de generar. Tocá «Regenerar» allí.")
            sin_mencionar = (B.get("registro_info") or {}).get("vigentes_sin_mencionar", [])
            if sin_mencionar:
                lista = ", ".join(map(str, sin_mencionar))
                st.warning(f"**Avisos vigentes que no aparecen en el borrador:** {lista}. ¿Cesaron?")
                if st.button(f"Agregar el cese de {lista} y regenerar"):
                    for n in sin_mencionar:
                        nuevo = modelo.nuevo_aviso()
                        nuevo.update(numero=str(n), estado="cese", navtex=True)
                        B["avisos"].append(nuevo)
                    ss.ver += 1
                    generar_salida()
                    st.rerun()
            if ss.dudas:
                st.warning("**Revisá estas interpretaciones:**\n\n" + "\n".join(
                    f"- **{d.get('donde', '')}**: {d.get('motivo', '')}" for d in ss.dudas))
            if errores:
                st.error("**Falta o está mal (corregilo en el texto y volvé a interpretar, o en «Ajuste fino»):**\n\n"
                         + "\n".join(f"- {e}" for e in errores))
            if advertencias:
                with st.expander(f"Otras advertencias ({len(advertencias)})", expanded=not errores):
                    st.markdown("\n".join(f"- {a}" for a in advertencias))

            nombres = render.nombre_archivos(B)
            t_es, t_en, t_nav, t_mapa = st.tabs(["WWST01 · castellano", "WWST02 · inglés", "WWST03 · NAVTEX", "Mapa"])
            es = t_es.text_area("castellano", ss.salida["es"], height=520, key=f"out_es_{ss.gen}",
                                label_visibility="collapsed")
            en = t_en.text_area("inglés", ss.salida["en"], height=520, key=f"out_en_{ss.gen}",
                                label_visibility="collapsed")
            with t_nav:
                with st.expander("Qué va al NAVTEX", expanded=not any(a.get("navtex") for a in B["avisos"])
                                 and not any(x.get("navtex") for x in B["sinopsis"])):
                    if not B["avisos"] and not B["sinopsis"]:
                        st.caption("No hay avisos ni sistemas en este boletín.")
                    for a in B["avisos"]:
                        a["navtex"] = st.checkbox(f"Aviso {a['numero'] or '(sin número)'}: "
                                                  + render.linea_aviso(CAT, B, a, "es")[:110],
                                                  value=bool(a.get("navtex")), key=K("nav", a["id"]))
                    for x in B["sinopsis"]:
                        x["navtex"] = st.checkbox(render.linea_sistema(CAT, x, "es")[:120],
                                                  value=bool(x.get("navtex")), key=K("nav", x["id"]))
                texto_nav = render.generar_navtex(CAT, B)
                nav = st.text_area("NAVTEX", texto_nav, height=430, key=f"out_nav_{hash(texto_nav)}",
                                   label_visibility="collapsed")
            with t_mapa:
                from core import mapa
                dibujo = mapa.svg(CAT, B)
                st.markdown(dibujo, unsafe_allow_html=True)
                st.download_button("⬇ Mapa (.svg)", dibujo.encode("utf-8"), file_name=f"mapa_avisos_{nombres['es'][13:19]}.svg",
                                   mime="image/svg+xml")
            st.caption("Se puede retocar el texto antes de descargar; un cambio en un idioma no pasa al otro.")
            sep = CAT["encabezado"]["separador_combinado"]
            c = st.columns(4)
            c[0].download_button("⬇ Castellano", almacen.a_bytes(es), file_name=nombres["es"], mime="text/plain",
                                 use_container_width=True, disabled=bool(errores))
            c[1].download_button("⬇ Inglés", almacen.a_bytes(en), file_name=nombres["en"], mime="text/plain",
                                 use_container_width=True, disabled=bool(errores))
            c[2].download_button("⬇ Ambos", almacen.a_bytes(f"{es}{sep}\n\n{en}"), file_name=nombres["comb"],
                                 mime="text/plain", use_container_width=True, disabled=bool(errores))
            c[3].download_button("⬇ NAVTEX", almacen.a_bytes(nav), file_name=nombres["navtex"], mime="text/plain",
                                 use_container_width=True, disabled=bool(errores))

# ======================================================================
# AJUSTE FINO: datos estructurados
# ======================================================================
def ui_avisos():
    ac = CAT["avisos"]
    if not B["avisos"]:
        st.info("Sin avisos: el boletín dirá «NO HAY AVISOS».")
    for i, a in enumerate(B["avisos"]):
        aid = a["id"]
        with st.container(border=True):
            c = st.columns([0.8, 1.3, 2, 2.6, 1.2, 0.4])
            with c[0]:
                t_in("N.º", a, "numero", K(aid, "n"), help="Se asigna solo si es nuevo y queda vacío")
                if a.get("numero_auto"):
                    st.caption("asignado")
            with c[1]:
                sel("Estado", list(ac["estados"]), a, "estado", K(aid, "estado"), fmt=lambda k: ac["estados"][k]["ui"])
            if a.get("estado") in ("cese", "fuera_area"):
                with c[5]:
                    st.write("")
                    if st.button("🗑", key=K(aid, "del"), help="Eliminar aviso"):
                        B["avisos"].pop(i)
                        st.rerun()
                vista_previa(lambda lang: render.linea_aviso(CAT, B, a, lang))
                continue
            with c[2]:
                sel("Causa", list(ac["causas"]), a, "causa", K(aid, "causa"), fmt=lambda k: ac["causas"][k]["ui"])
            with c[3]:
                ayuda = {"GRADIENTE": "Opcional, ej. MOV E", "DEPRESION": "Presión y posición, ej. 990HPA 45S 60W",
                         "OTRA": "Texto libre en castellano"}.get(a["causa"], "Posición, ej. 49S 66W 43S 65W")
                t_in("Detalle de la causa", a, "detalle", K(aid, "det"), placeholder=ayuda)
            with c[4]:
                sel("Verbo", list(ac["verbo"]), a, "verbo", K(aid, "verbo"), fmt=lambda k: ac["verbo"][k]["ui"])
            with c[5]:
                st.write("")
                if st.button("🗑", key=K(aid, "del"), help="Eliminar aviso"):
                    B["avisos"].pop(i)
                    st.rerun()
            c = st.columns([1, 1.5, 1, 1.2, 1.2])
            with c[0]:
                sel("Fuerza", ["8", "9", "10", "11", "12"], a, "fuerza", K(aid, "f"))
            with c[1]:
                sel("Dirección", [""] + DIRS, a, "dir", K(aid, "dir"))
            with c[2]:
                st.write("")
                chk("Con ráfagas", a, "rafagas", K(aid, "raf"))
            with c[3]:
                t_in("A partir del (DD/HHMM)", a, "desde", K(aid, "desde"), placeholder="24/1800")
            with c[4]:
                t_in("Hasta el (DD/HHMM)", a, "hasta", K(aid, "hasta"), placeholder="25/0900")
            c = st.columns([3, 2])
            with c[0]:
                multi("Zonas afectadas", list(ZONAS), a, "zonas", K(aid, "zonas"),
                      fmt=lambda k: ZONAS[k].get("aviso_es", ZONAS[k]["es"]))
            with c[1]:
                t_in("…y/o entre coordenadas", a, "coords", K(aid, "coords"), placeholder="40S-50S 50W-60W")
            vista_previa(lambda lang: render.linea_aviso(CAT, B, a, lang))
    if st.button("➕ Agregar aviso"):
        nuevo = modelo.nuevo_aviso()
        nums = [int(x["numero"]) for x in B["avisos"] if x["numero"].strip().isdigit()]
        nuevo["numero"] = str(max(nums) + 1) if nums else ""
        B["avisos"].insert(0, nuevo)
        st.rerun()


def ui_sinopsis():
    sc = CAT["sinopsis"]
    for i, s in enumerate(B["sinopsis"]):
        sid = s["id"]
        tipo = sc["tipos"][s["tipo"]]
        with st.container(border=True):
            c = st.columns([1.6, 1, 2.6, 1.2, 2, 0.4, 0.4])
            with c[0]:
                sel("Tipo", list(sc["tipos"]), s, "tipo", K(sid, "tipo"), fmt=lambda k: sc["tipos"][k]["ui"])
            with c[1]:
                t_in("Presión (hPa)", s, "presion", K(sid, "p"), disabled=not tipo.get("presion"), placeholder="993")
            with c[2]:
                t_in("Posición (opcional)", s, "pos", K(sid, "pos"), placeholder="47S 55W  (o línea: 51S 53W 39S 62W)")
            with c[3]:
                sel("Movimiento", sc["movimientos"], s, "mov", K(sid, "mov"))
            with c[4]:
                multi("Evolución", sc["evoluciones"], s, "evol", K(sid, "evol"))
            with c[5]:
                st.write("")
                if i > 0 and st.button("↑", key=K(sid, "up"), help="Subir"):
                    B["sinopsis"][i - 1], B["sinopsis"][i] = B["sinopsis"][i], B["sinopsis"][i - 1]
                    st.rerun()
            with c[6]:
                st.write("")
                if st.button("🗑", key=K(sid, "del"), help="Eliminar"):
                    B["sinopsis"].pop(i)
                    st.rerun()
            with st.expander("Posición final y frente asociado", expanded=bool(s["exp_pos"] or s["ext_tipo"])):
                c = st.columns([2, 1, 1, 2.4, 1])
                with c[0]:
                    t_in("Posición final (EXP)", s, "exp_pos", K(sid, "ep"), placeholder="56S 27W")
                with c[1]:
                    t_in("El (DD/HHMM)", s, "exp_hora", K(sid, "eh"), placeholder="24/1200")
                with c[2]:
                    sel("Extiende", [""] + list(sc["frentes_extiende"]), s, "ext_tipo", K(sid, "et"),
                        fmt=lambda k: sc["frentes_extiende"][k]["es"] if k else "—")
                with c[3]:
                    t_in("Posición del frente", s, "ext_pos", K(sid, "epos"), disabled=not s["ext_tipo"],
                         placeholder="46S 25W 47S 35W")
                with c[4]:
                    sel("Mov. del frente", sc["movimientos"], s, "ext_mov", K(sid, "emov"), disabled=not s["ext_tipo"])
                if s["ext_tipo"]:
                    c = st.columns([2.4, 1, 4])
                    with c[0]:
                        t_in("Posición final del frente", s, "ext_exp_pos", K(sid, "eep"), placeholder="38S 44W 48S 24W")
                    with c[1]:
                        t_in("El (DD/HHMM) ", s, "ext_exp_hora", K(sid, "eeh"), placeholder="02/1200")
            vista_previa(lambda lang: render.linea_sistema(CAT, s, lang))
    if st.button("➕ Agregar sistema"):
        B["sinopsis"].append(modelo.nuevo_sistema())
        st.rerun()


def estado_zona(zid, errores):
    zd = B["zonas"][zid]
    if not zd["incluir"]:
        return "⏸️"
    nombre = ZONAS[zid]["es"]
    return "⚠️" if any(e.startswith(nombre) for e in errores) else "✅"


def ui_division(sz, pref):
    d = sz["division"]
    opciones = {"condiciones": "Al N / S / E / W de…", "coordenadas": "Por coordenadas",
                "cuadrante": "NE / NW / SE / SW del área", "resto": "Resto del área"}
    if d["tipo"] not in opciones:
        d["tipo"] = "condiciones"
    d["tipo"] = st.radio("Parte de la zona", list(opciones), index=list(opciones).index(d["tipo"]),
                         format_func=opciones.get, horizontal=True, key=K(pref, "dtipo"))
    rel = CAT["subdivision"]["relaciones"]
    if d["tipo"] == "condiciones":
        for j, cnd in enumerate(d["conds"]):
            c = st.columns([1.2, 1, 0.4, 3])
            with c[0]:
                sel("Condición", list(rel), cnd, "rel", K(pref, cnd["id"], "rel"), fmt=lambda k: rel[k]["ui"],
                    label_visibility="collapsed")
            with c[1]:
                t_in("Valor", cnd, "valor", K(pref, cnd["id"], "val"), placeholder="45S / 40W",
                     label_visibility="collapsed")
            with c[2]:
                if len(d["conds"]) > 1 and st.button("✕", key=K(pref, cnd["id"], "del")):
                    d["conds"].pop(j)
                    st.rerun()
        if len(d["conds"]) < 3 and st.button("y además…", key=K(pref, "addc")):
            d["conds"].append({"id": modelo.nid(), "rel": "S", "valor": ""})
            st.rerun()
    elif d["tipo"] == "cuadrante":
        c = st.columns([1.2, 4])
        with c[0]:
            sel("Cuadrante", CAT["subdivision"]["cuadrantes"], d, "cuadrante", K(pref, "cuad"),
                label_visibility="collapsed")
    elif d["tipo"] == "coordenadas":
        c = st.columns(4)
        for col, (k, ph) in zip(c, [("lat1", "Lat. desde (40S)"), ("lat2", "Lat. hasta (45S)"),
                                    ("lon1", "Lon. desde (30W)"), ("lon2", "Lon. hasta (40W)")]):
            with col:
                t_in(ph, d, k, K(pref, k))


def ui_viento(v, pref):
    raf = {"": "Sin ráfagas", "CON": "Con ráfagas", "INT": "Ráfagas con intensidad"}
    st.markdown("**Viento**")
    c = st.columns([1.5, 1, 1.6, 1])
    with c[0]:
        sel("Dirección", [""] + DIRS, v, "dir", K(pref, "dir"))
    with c[1]:
        t_in("Fuerza", v, "fuerza", K(pref, "f"), placeholder="5 o 5/6")
    with c[2]:
        sel("Ráfagas", list(raf), v, "rafagas", K(pref, "raf"), fmt=raf.get)
    with c[3]:
        t_in("Intensidad", v, "raf_int", K(pref, "ri"), disabled=v["rafagas"] != "INT", placeholder="8")
    for j, cb in enumerate(v["cambios"]):
        cid = cb["id"]
        c = st.columns([1, 1.2, 1.4, 0.8, 1.5, 0.6, 1.1, 0.4])
        with c[0]:
            st.write("")
            chk("TEMPO", cb, "tempo", K(pref, cid, "tempo"))
        with c[1]:
            sel("Cambio", CAT["viento"]["cambios"], cb, "tipo", K(pref, cid, "tipo"))
        with c[2]:
            sel("A dirección", [""] + DIRS, cb, "dir", K(pref, cid, "dir"))
        with c[3]:
            t_in("Fuerza", cb, "fuerza", K(pref, cid, "f"))
        with c[4]:
            sel("Ráfagas", list(raf), cb, "rafagas", K(pref, cid, "raf"), fmt=raf.get)
        with c[5]:
            t_in("Int.", cb, "raf_int", K(pref, cid, "ri"), disabled=cb["rafagas"] != "INT")
        with c[6]:
            t_in("El (DD/HHMM)", cb, "hora", K(pref, cid, "h"), placeholder="24/0600")
        with c[7]:
            st.write("")
            if st.button("✕", key=K(pref, cid, "del")):
                v["cambios"].pop(j)
                st.rerun()
    if st.button("➕ cambio de viento", key=K(pref, "addcb")):
        v["cambios"].append(modelo.nuevo_cambio())
        st.rerun()


def ui_fenomenos(f, pref):
    st.markdown("**Fenómenos**")
    chk("Sin fenómenos significativos", f, "sin_fenomenos", K(pref, "sinf"))
    if f["sin_fenomenos"]:
        return
    for j, it in enumerate(f["items"]):
        iid = it["id"]
        if j == 0:
            c = [None] + st.columns([1.4, 2.2, 1.1, 1.6, 1.4, 1.5, 1.0, 0.4])
        else:
            c = st.columns([0.9, 1.1, 2.0, 1.0, 1.5, 1.3, 1.4, 1.0, 0.4])
            with c[0]:
                sel("Conector", list(FEN["conector"]), it, "conector", K(pref, iid, "con"),
                    fmt=fmt_dic(FEN["conector"], "(nada)"))
        with c[1]:
            sel("Probabilidad", list(FEN["probabilidad"]), it, "prob", K(pref, iid, "prob"),
                fmt=fmt_dic(FEN["probabilidad"], "(sin prob.)"))
        with c[2]:
            multi("Fenómeno/s", list(FEN["lista"]), it, "fen", K(pref, iid, "fen"),
                  fmt=lambda k: FEN["lista"][k]["es"])
        with c[3]:
            sel("Calificativo", list(FEN["calificativo"]), it, "cal", K(pref, iid, "cal"),
                fmt=fmt_dic(FEN["calificativo"]))
        with c[4]:
            sel("Momento", list(FEN["momento"]), it, "momento", K(pref, iid, "mom"), fmt=fmt_dic(FEN["momento"]))
        with c[5]:
            sel("Evolución", list(FEN["evolucion"]), it, "evol", K(pref, iid, "evo"), fmt=fmt_dic(FEN["evolucion"]))
        with c[6]:
            sel("…cuándo", list(FEN["momento"]), it, "momento_evol", K(pref, iid, "mevo"), fmt=fmt_dic(FEN["momento"]),
                disabled=not it.get("evol"))
        with c[7]:
            t_in("…hora", it, "hora_evol", K(pref, iid, "hevo"), disabled=not it.get("evol"), placeholder="24/1800")
        with c[8]:
            st.write("")
            if len(f["items"]) > 1 and st.button("✕", key=K(pref, iid, "del")):
                f["items"].pop(j)
                st.rerun()
    if st.button("➕ fenómeno", key=K(pref, "addf")):
        nuevo = modelo.nuevo_item_fenomeno()
        nuevo["conector"] = "LUEGO"
        f["items"].append(nuevo)
        st.rerun()


def ui_vis(v, pref):
    st.markdown("**Visibilidad**")
    nombres = lambda k: VIS[k]["es"] if k else "—"
    c = st.columns(3)
    with c[0]:
        sel("Visibilidad", [""] + list(VIS), v, "v1", K(pref, "v1"), fmt=nombres)
    with c[1]:
        sel("…a", [""] + list(VIS), v, "hasta", K(pref, "v2"), fmt=nombres)
    with c[2]:
        sel("…ocasionalmente", [""] + list(VIS), v, "ocnl", K(pref, "v3"), fmt=nombres)
    if v.get("ocnl") and v.get("hasta"):
        chk("Escribir «ocasionalmente» antes del rango (VIS MALA OCNL MUY MALA A REGULAR)", v, "ocnl_antes",
            K(pref, "oant"))


def ui_zonas(errores):
    col_lista, col_edit = st.columns([1, 3.4])
    ids = list(ZONAS)
    with col_lista:
        zid = st.radio("Zona", ids, key="zona_sel",
                       format_func=lambda k: f"{estado_zona(k, errores)} "
                       + (ZONAS[k].get("aviso_es") or ZONAS[k]["es"].split(" (")[0]))
        st.caption("✅ completa · ⚠️ falta algo · ⏸️ no se incluye")
    with col_edit:
        z, zd = ZONAS[zid], B["zonas"][zid]
        st.subheader(z["es"])
        c = st.columns([2, 2, 1])
        with c[0]:
            chk("Incluir esta zona en el boletín", zd, "incluir", K(zid, "inc"))
        with c[1]:
            origen = st.selectbox("Copiar el pronóstico de…", [k for k in ids if k != zid], key=K(zid, "copia_de"),
                                  format_func=lambda k: ZONAS[k]["es"])
        with c[2]:
            st.write("")
            if st.button("Copiar", key=K(zid, "copiar"), help="Reemplaza el pronóstico de esta zona"):
                zd["subzonas"] = modelo.recargar_ids(copy.deepcopy(B["zonas"][origen]["subzonas"]))
                zd["incluir"] = True
                ss.ver += 1
                st.rerun()
        if not zd["incluir"]:
            st.info("Esta zona no va a aparecer en el boletín.")
            return
        subs = zd["subzonas"]
        for i, sz in enumerate(subs):
            pref = f"{zid}:{sz['id']}"
            with st.container(border=True):
                if len(subs) > 1:
                    c = st.columns([6, 1])
                    c[0].markdown(f"#### Subzona {i + 1}")
                    if c[1].button("Quitar subzona", key=K(pref, "del")):
                        subs.pop(i)
                        st.rerun()
                    ui_division(sz, pref)
                ui_viento(sz["viento"], pref)
                ui_fenomenos(sz["fenomenos"], pref)
                ui_vis(sz["vis"], pref)
                t_in("Texto adicional (va al final, antes de la visibilidad)", sz, "obs", K(pref, "obs"))
                vista_previa(lambda lang: render.linea_subzona(CAT, B, z, sz, len(subs) > 1, lang))
        if st.button("➕ Dividir la zona (agregar subzona)", key=K(zid, "addsub")):
            nueva = modelo.nueva_subzona()
            nueva["division"]["tipo"] = "resto"
            subs.append(nueva)
            st.rerun()


def ui_textos_libres():
    pendientes = render.textos_libres(B)
    if not pendientes:
        st.caption("No hay textos libres en este boletín.")
        return
    st.caption("Traducción al inglés de lo que no entró en los campos estructurados.")
    for p in pendientes:
        c = st.columns(2)
        c[0].text_input("Castellano", value=p, disabled=True, key=K("tl_es", p))
        en = c[1].text_input("Inglés", value=B["traducciones"].get(p, ""), key=K("tl_en", p))
        if en.strip():
            B["traducciones"][p] = render.normalizar(en)
        else:
            B["traducciones"].pop(p, None)
    if ia.disponible() and st.button("🤖 Traducir con IA los que faltan"):
        faltan = [p for p in pendientes if not B["traducciones"].get(p)]
        try:
            B["traducciones"].update(ia.traducir(CAT, faltan))
        except Exception as e:  # noqa: BLE001
            st.error(f"No se pudo traducir: {e}")
        ss.ver += 1
        st.rerun()


with tab_fino:
    st.caption("Los datos interpretados del texto (o cargados a mano). Si cambiás algo, tocá «Regenerar».")
    if st.button("Regenerar con estos datos", type="primary"):
        generar_salida()
        st.rerun()
    errores_fino, _ = validar.validar(CAT, B)
    s_av, s_sin, s_zon, s_tl = st.tabs(["Avisos", "Sinopsis", "Zonas", "Textos libres"])
    with s_av:
        ui_avisos()
    with s_sin:
        ui_sinopsis()
    with s_zon:
        ui_zonas(errores_fino)
    with s_tl:
        ui_textos_libres()
