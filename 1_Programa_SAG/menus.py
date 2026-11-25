"""
menus.py – Menús por rol (Recepcionista, Entrenador, Administrador).

Se usa herencia y polimorfismo: MenuBase define el ciclo del menú y las
operaciones compartidas; cada subclase define sus propias opciones().
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Callable

from modelos import DIAS, Cancelado, Cliente, Membresia, ReglaNegocio, Rutina
from repositorio import Repositorio
from vista import (Vista, barra, dinero, estado, f_fecha, f_fecha_hora, f_hora, t)

Opciones = list[tuple[str, Callable[[], None]]]


# ===========================================================================
# Clase base
# ===========================================================================
class MenuBase(ABC):
    titulo = "Menú"

    def __init__(self, repo: Repositorio, vista: Vista, usuario):
        self.repo = repo
        self.v = vista
        self.usuario = usuario

    # --------------------------------------------------------- polimorfismo
    @abstractmethod
    def opciones(self) -> Opciones:
        """Cada rol regresa su lista de (texto, método)."""

    def antes_del_menu(self) -> None:
        """Gancho opcional: lo que se muestra arriba del menú principal."""

    # --------------------------------------------------------- ciclo
    def ejecutar(self) -> None:
        self.bucle(self.titulo, self.opciones, principal=True)

    def bucle(self, titulo: str, generar: Callable[[], Opciones], principal: bool = False) -> None:
        while True:
            self.repo.recargar()
            self.usuario = self.repo.por_codigo(self.repo.empleados, self.usuario.codigo) or self.usuario
            self.v.encabezado(titulo, self.usuario)
            if principal:
                self.antes_del_menu()
            ops = generar()
            eleccion = self.v.menu(titulo, [texto for texto, _ in ops],
                                   salida="Cerrar sesión" if principal else "Regresar")
            if eleccion == 0:
                if not principal or self.v.confirmar("¿Cerrar sesión?"):
                    return
                continue
            texto, accion = ops[eleccion - 1]
            self.v.encabezado(texto, self.usuario)
            try:
                accion()
            except Cancelado as e:
                self.v.aviso(str(e) or "Operación cancelada.")
            except ReglaNegocio as e:
                self.v.error(str(e))
                # si la base rechazó un cambio, el repositorio se recarga;
                # se vuelve a tomar al usuario de la sesión ya actualizado
                self.usuario = self.repo.por_codigo(self.repo.empleados, self.usuario.codigo) or self.usuario
            self.v.pausa()

    def submenu(self, titulo: str, opciones: Opciones) -> Callable[[], None]:
        """Regresa una acción que abre un submenú."""
        return lambda: self.bucle(titulo, lambda: opciones)

    def guardar(self, msg: str = "¿Guardar los cambios?") -> None:
        if not self.v.confirmar(msg):
            raise Cancelado("No se guardaron cambios.")

    # --------------------------------------------------------- filas de tablas
    COLS_CLIENTE = ["Código", "Nombre", "Edad", "Celular(es)", "Membresía", "Estado"]

    @staticmethod
    def fila_cliente(c: Cliente):
        m = c.membresia_activa
        mem = f"{m.tipo.nombre} → {f_fecha(m.fecha_vencimiento)}" if m else estado(c.situacion)
        return [c.codigo, c.nombre_completo, c.edad, ", ".join(c.celulares), mem, estado(c.estado)]

    COLS_MEMBRESIA = ["Código", "Cliente", "Tipo", "Inicio", "Vence", "Estado"]

    @staticmethod
    def fila_membresia(m: Membresia):
        return [m.codigo, m.cliente.nombre_completo, m.tipo.nombre, f_fecha(m.fecha_inicio),
                f_fecha(m.fecha_vencimiento), estado(m.estado_actual)]

    COLS_CLASE = ["Código", "Clase", "Especialidad", "Días", "Horario", "Instructor",
                  "Inscritos", "Lugares", "Estado"]

    @staticmethod
    def fila_clase(c):
        lugares = f"[green]{c.lugares}[/]" if c.lugares > 0 else "[red]Lleno[/]"
        return [c.codigo, c.nombre, c.especialidad.nombre, c.dias_txt, c.horario_txt,
                c.empleado.nombre_completo, f"{len(c.inscritos)}/{c.cupo_max}", lugares,
                estado(c.estado)]

    COLS_PAGO = ["Código", "Fecha", "Cliente", "Membresía", "Método", "Monto"]

    @staticmethod
    def fila_pago(p):
        return [p.codigo, f_fecha(p.fecha_pago), p.membresia.cliente.nombre_completo,
                f"{p.membresia.codigo} ({p.membresia.tipo.nombre})", p.metodo.nombre, dinero(p.monto)]

    COLS_RUTINA = ["Código", "Rutina", "Objetivo", "Diseñó", "Por semana", "Duración", "Sesiones",
                   "Enfoques", "Clientes", "Estado"]

    @staticmethod
    def fila_rutina(r: Rutina):
        activos = sum(a.estado == "Activa" for a in r.asignaciones)
        return [r.codigo, t(r.nombre), t(r.objetivo), r.empleado.nombre_pila, f"{r.frecuencia} días",
                f"{r.duracion_sesion} min", r.total_sesiones, len(r.enfoques), activos, estado(r.estado)]

    COLS_ASIGNACION = ["Código", "Cliente", "Rutina", "Días", "Avance", "Le toca", "Asignó", "Estado", "Observaciones"]

    @staticmethod
    def fila_asignacion(a):
        sig = a.siguiente_enfoque
        return [a.codigo, a.cliente.nombre_completo, t(a.rutina.nombre), a.dias_txt, a.avance_txt,
                t(sig.titulo) if sig and a.estado == "Activa" else "—", a.empleado.nombre_pila,
                estado(a.estado), t(a.observaciones)]

    COLS_SESION = ["Código", "Membresía", "Cliente", "Fecha", "Rutina", "Enfoque", "Asistió", "Inicio", "Fin",
                   "Observaciones"]

    @staticmethod
    def fila_sesion(s):
        return [s.codigo, s.membresia.codigo, s.cliente.nombre_completo, f_fecha(s.fecha),
                t(s.rutina.nombre) if s.rutina else "Libre", t(s.enfoque.titulo) if s.enfoque else "—",
                "[green]Sí[/]" if s.asistio else "[red]No[/]",
                f_hora(s.hora_inicio), f_hora(s.hora_fin), t(s.observaciones)]

    def mostrar_plan(self, cliente) -> None:
        """Plan semanal guiado: qué rutina toca cada día y qué enfoque sigue."""
        hoy = DIAS[date.today().weekday()]
        filas = []
        for d, a in cliente.plan_semanal.items():
            marca = f"[bold]{d}[/] [yellow]← hoy[/]" if d == hoy else d
            if a:
                sig = a.siguiente_enfoque
                filas.append([marca, t(a.rutina.nombre), t(sig.titulo) if sig else "—", a.avance_txt])
            else:
                filas.append([marca, "[dim]Descanso[/]", "", ""])
        dias = sum(a is not None for a in cliente.plan_semanal.values())
        self.v.tabla(f"Plan semanal de {cliente.nombre_completo}", ["Día", "Rutina", "Le toca", "Sesiones"], filas,
                     pie=f"{dias} de 7 días con rutina · {len(cliente.asignaciones_activas)} rutina(s) combinada(s)")

    def mostrar_enfoque(self, enfoque) -> None:
        self.v.tabla(f"{enfoque.rutina.nombre} · {enfoque.titulo}", ["#", "Ejercicio", "Series × reps", "Cómo se hace"],
                     [[ee.orden, t(ee.ejercicio.nombre), f"{ee.series} × {t(ee.repeticiones)}",
                       t(ee.ejercicio.descripcion)] for ee in sorted(enfoque.ejercicios, key=lambda x: x.orden)])

    # --------------------------------------------------------- búsquedas comunes
    def buscar_cliente(self, solo_activos: bool = False) -> Cliente:
        texto = self.v.texto("Buscar cliente [dim](código, nombre o celular)[/]")
        encontrados = self.repo.buscar_clientes(texto, solo_activos)
        if not encontrados:
            raise Cancelado("No se encontró ningún cliente" + (" activo." if solo_activos else "."))
        if len(encontrados) == 1:
            c = encontrados[0]
            self.v.info(f"Cliente: [bold]{c.codigo}[/] · {c.nombre_completo}")
            return c
        return self.v.elegir(encontrados, "Clientes encontrados", self.COLS_CLIENTE, self.fila_cliente)

    def buscar_membresia(self) -> Membresia:
        texto = self.v.texto("Buscar membresía [dim](código MEM-###, nombre o celular del cliente)[/]")
        encontradas = self.repo.buscar_membresias(texto)
        if not encontradas:
            raise Cancelado("No se encontró ninguna membresía.")
        if len(encontradas) == 1:
            return encontradas[0]
        return self.v.elegir(encontradas, "Membresías encontradas", self.COLS_MEMBRESIA,
                             self.fila_membresia)

    def elegir_metodo_pago(self):
        activos = [m for m in self.repo.metodos if m.activo]
        return self.v.elegir(activos, "Métodos de pago", ["Código", "Método"],
                             lambda m: [m.codigo, m.nombre])

    def elegir_tipo(self):
        return self.v.elegir(self.repo.tipos, "Tipos de membresía",
                             ["Código", "Tipo", "Duración", "Monto"],
                             lambda x: [x.codigo, x.nombre, f"{x.duracion_dias} días", dinero(x.monto)],
                             derecha=["Monto"])

    def elegir_rutina(self, solo_activas: bool = True, rutinas=None):
        lista = rutinas if rutinas is not None else self.repo.rutinas
        lista = [r for r in lista if r.activa or not solo_activas]
        return self.v.elegir(lista, "Catálogo de rutinas", self.COLS_RUTINA, self.fila_rutina)

    def mostrar_rutina(self, r: Rutina) -> None:
        """Información completa de una rutina: datos, enfoques y ejercicios (consulta 4)."""
        self.v.ficha(f"Rutina {r.codigo}", {
            "Nombre": f"[bold]{t(r.nombre)}[/]",
            "Objetivo": t(r.objetivo),
            "Descripción": t(r.descripcion),
            "Frecuencia": f"{r.frecuencia} sesiones por semana",
            "Duración por sesión": f"{r.duracion_sesion} minutos",
            "Total de sesiones": r.total_sesiones,
            "Días de descanso": f"{r.dias_descanso} por semana",
            "Diseñó": r.empleado.nombre_completo,
            "Estado": estado(r.estado),
        })
        filas = []
        for en in r.enfoques:
            for i, ee in enumerate(en.ejercicios):
                filas.append([f"Día {en.dia_rutina}" if i == 0 else "", t(en.descripcion) if i == 0 else "",
                              t(ee.ejercicio.nombre), f"{ee.series} × {t(ee.repeticiones)}", t(ee.ejercicio.descripcion)])
        self.v.tabla("Enfoques y ejercicios", ["Día", "Enfoque", "Ejercicio", "Series × reps", "Descripción"], filas,
                     pie=f"{len(r.enfoques)} enfoque(s) · {r.total_ejercicios} ejercicio(s)")

    def sesiones_de(self, cliente) -> list:
        return sorted(cliente.sesiones, key=lambda s: (s.fecha, s.hora_inicio), reverse=True)

    # --------------------------------------------------------- operaciones comunes
    def ver_tipos_membresia(self) -> None:
        """RF-04"""
        self.v.tabla("Tipos de membresía disponibles",
                     ["Código", "Tipo", "Duración", "Monto", "Beneficios incluidos"],
                     [[x.codigo, f"[bold]{x.nombre}[/]", f"{x.duracion_dias} días", dinero(x.monto),
                       "\n".join(f"• {b.descripcion}" for b in x.beneficios) or "—"]
                      for x in self.repo.tipos], derecha=["Monto"])

    def registrar_cliente(self) -> None:
        """RF-05"""
        self.v.seccion("Datos personales")
        nombre = self.v.texto("Nombre(s)")
        ap_1 = self.v.texto("Primer apellido")
        ap_2 = self.v.texto("Segundo apellido", obligatorio=False)
        fecha_nac = self.v.fecha("Fecha de nacimiento")
        if fecha_nac >= date.today():
            raise ReglaNegocio("La fecha de nacimiento debe ser anterior a hoy.")
        celulares = self.v.celulares()
        self.v.seccion("Dirección")
        colonia = self.v.texto("Colonia")
        calle = self.v.texto("Calle y número")
        edad = date.today().year - fecha_nac.year - (
            (date.today().month, date.today().day) < (fecha_nac.month, fecha_nac.day))
        self.v.ficha("Nuevo cliente", {
            "Nombre": " ".join(p for p in (nombre, ap_1, ap_2) if p),
            "Nacimiento": f"{f_fecha(fecha_nac)}  ({edad} años)",
            "Celular(es)": ", ".join(celulares),
            "Dirección": f"{calle}, Col. {colonia}",
        })
        self.guardar("¿Registrar al cliente?")
        c = self.repo.agregar_cliente(nombre, ap_1, ap_2, fecha_nac, colonia, calle, celulares)
        self.v.exito(f"Cliente registrado con el código {c.codigo}")

    def mostrar_membresia(self, m: Membresia) -> None:
        datos = {
            "Código": f"[bold]{m.codigo}[/]",
            "Cliente": f"{m.cliente.nombre_completo} ({m.cliente.codigo})",
            "Tipo": f"{m.tipo.nombre} · {m.tipo.duracion_dias} días",
            "Inicio": f_fecha(m.fecha_inicio),
            "Vencimiento": f_fecha(m.fecha_vencimiento),
            "Estado": estado(m.estado_actual),
            "Inscrita por": m.empleado.nombre_completo,
        }
        if m.estado_actual == "Activa":
            datos["Días restantes"] = f"[bold]{m.dias_restantes}[/]"
        if m.estado_actual == "Cancelada":
            datos["Cancelada el"] = f_fecha(m.fecha_cancelacion)
            datos["Motivo"] = t(m.motivo_cancelacion)
        self.v.ficha("Membresía", datos)
        self.v.tabla("Historial de pagos", ["Código", "Fecha", "Método", "Monto"],
                     [[p.codigo, f_fecha(p.fecha_pago), p.metodo.nombre, dinero(p.monto)]
                      for p in m.pagos], derecha=["Monto"],
                     pie=f"Total pagado: {dinero(m.total_pagado)}")

    def historial_cliente(self, c: Cliente) -> None:
        self.v.ficha(f"Cliente {c.codigo}", {
            "Nombre": f"[bold]{c.nombre_completo}[/]",
            "Edad": f"{c.edad} años ({f_fecha(c.fecha_nacimiento)})",
            "Celular(es)": ", ".join(c.celulares),
            "Dirección": t(c.direccion),
            "Estado": estado(c.estado),
            "Membresía": estado(c.situacion),
        })
        self.v.tabla("Membresías", self.COLS_MEMBRESIA, map(self.fila_membresia, c.membresias))
        pagos = [p for m in c.membresias for p in m.pagos]
        self.v.tabla("Pagos", self.COLS_PAGO, map(self.fila_pago, pagos), derecha=["Monto"])
        self.v.tabla("Inscripciones a clases", ["Código", "Clase", "Días", "Fecha", "Estado"],
                     [[i.codigo, i.clase.nombre, i.clase.dias_txt, f_fecha(i.fecha), estado(i.estado)]
                      for i in c.inscripciones])
        self.mostrar_plan(c)
        self.v.tabla("Rutinas asignadas", self.COLS_ASIGNACION, map(self.fila_asignacion, c.asignaciones))
        self.v.tabla("Sesiones de entrenamiento", self.COLS_SESION, map(self.fila_sesion, self.sesiones_de(c)))

    def pedir_periodo(self, dias_atras: int = 30) -> tuple[date, date]:
        inicio = self.v.fecha("Desde", date.today() - timedelta(days=dias_atras))
        fin = self.v.fecha("Hasta", date.today())
        if fin < inicio:
            raise ReglaNegocio("La fecha final no puede ser anterior a la inicial.")
        return inicio, fin


# ===========================================================================
# Recepcionista
# ===========================================================================
class MenuRecepcionista(MenuBase):
    titulo = "Menú de Recepción"

    def opciones(self) -> Opciones:
        return [
            ("Tipos de membresía", self.ver_tipos_membresia),
            ("Registrar cliente", self.registrar_cliente),
            ("Vender membresía", self.vender_membresia),
            ("Consultar / renovar membresía", self.consultar_membresia),
            ("Cancelar membresía", self.cancelar_membresia),
            ("Inscribir cliente a una clase", self.inscribir_clase),
            ("Registrar asistencia ", self.registrar_sesion),
            ("Agenda de hoy", self.agenda_hoy),
        ]

    def vender_membresia(self) -> None:
        """RF-06"""
        cliente = self.buscar_cliente(solo_activos=True)
        if (actual := cliente.membresia_activa):
            self.v.aviso(f"{cliente.nombre_pila} ya tiene la membresía {actual.codigo} activa hasta "
                         f"{f_fecha(actual.fecha_vencimiento)}. Si quieres extenderla usa «Renovar».")
            if not self.v.si_no("¿Vender otra membresía de todos modos?", default=False):
                raise Cancelado()
        tipo = self.elegir_tipo()
        inicio = self.v.fecha("Fecha de inicio", date.today())
        metodo = self.elegir_metodo_pago()
        vence = inicio + timedelta(days=tipo.duracion_dias)
        self.v.ficha("Resumen de la venta", {
            "Cliente": cliente.nombre_completo,
            "Tipo": f"{tipo.nombre} ({tipo.duracion_dias} días)",
            "Inicio": f_fecha(inicio),
            "Vencimiento": f"[bold]{f_fecha(vence)}[/]",
            "Método de pago": metodo.nombre,
            "Total a cobrar": f"[bold green]{dinero(tipo.monto)}[/]",
        }, color="green")
        self.guardar("¿Confirmar venta y registrar el pago?")
        m = self.repo.vender_membresia(cliente, tipo, self.usuario, inicio, metodo)
        self.v.exito(f"Membresía {m.codigo} vendida · Pago {m.pagos[0].codigo} por {dinero(tipo.monto)}")

    def consultar_membresia(self) -> None:
        """RF-08 y RF-09"""
        m = self.buscar_membresia()
        self.v.encabezado("Consulta de membresía", self.usuario)
        self.mostrar_membresia(m)
        if m.estado_actual == "Cancelada" or not self.v.si_no("¿Renovar esta membresía?", default=False):
            return
        inicio = self.repo.fecha_renovacion(m)
        metodo = self.elegir_metodo_pago()
        self.v.ficha("Renovación", {
            "Tipo": m.tipo.nombre,
            "Nueva vigencia": f"{f_fecha(inicio)} → {f_fecha(inicio + timedelta(days=m.tipo.duracion_dias))}",
            "Método": metodo.nombre,
            "Total": f"[bold green]{dinero(m.tipo.monto)}[/]",
        }, color="green")
        self.guardar("¿Confirmar renovación?")
        nueva = self.repo.renovar_membresia(m, self.usuario, metodo)
        self.v.exito(f"Renovación registrada: nueva membresía {nueva.codigo}")

    def cancelar_membresia(self) -> None:
        """RF-07"""
        m = self.buscar_membresia()
        self.mostrar_membresia(m)
        if m.estado_actual == "Cancelada":
            raise ReglaNegocio("Esta membresía ya está cancelada.")
        motivo = self.v.texto("Motivo de la cancelación")
        self.guardar(f"¿Cancelar la membresía {m.codigo}?")
        m.cancelar(motivo)
        self.repo.guardar_cambios(m)      # guarda en la base de datos
        self.v.exito(f"Membresía {m.codigo} cancelada.")

    def inscribir_clase(self) -> None:
        """RF-10"""
        cliente = self.buscar_cliente(solo_activos=True)
        publicas = [c for c in self.repo.clases if c.publico and c.estado == "Activa"]
        publicas.sort(key=lambda c: c.orden)
        clase = self.v.elegir(publicas, "Clases disponibles", self.COLS_CLASE, self.fila_clase)
        clase.validar_inscripcion(cliente)
        obs = self.v.texto("Observaciones", obligatorio=False)
        self.guardar(f"¿Inscribir a {cliente.nombre_pila} en «{clase.nombre}» ({clase.dias_txt}, {clase.horario_txt})?")
        ins = self.repo.inscribir(cliente, clase, obs)
        self.v.exito(f"Inscripción {ins.codigo} registrada. Quedan {clase.lugares} lugar(es).")

    def registrar_sesion(self) -> None:
        """RF-11: el sistema dice qué le toca hoy al cliente según su plan semanal
        y solo se registra si asistió o no."""
        cliente = self.buscar_cliente(solo_activos=True)
        m = cliente.membresia_activa
        if not m:
            raise ReglaNegocio(f"{cliente.nombre_completo} no tiene una membresía activa. "
                               "No puede ingresar.")
        hoy = date.today()
        previa = cliente.sesion_del_dia(hoy)
        if previa:
            raise ReglaNegocio(f"Ya se registró hoy a {cliente.nombre_pila} "
                               f"({'asistió' if previa.asistio else 'faltó'}, sesión {previa.codigo}).")
        asignacion, enfoque = self.repo.que_le_toca(cliente, hoy)
        if asignacion:
            self.v.ficha(f"Hoy, {DIAS[hoy.weekday()].lower()}, a {cliente.nombre_pila} le toca", {
                "Rutina": f"[bold]{t(asignacion.rutina.nombre)}[/]",
                "Enfoque": f"[bold]{t(enfoque.titulo)}[/]",
                "Sesión": f"{asignacion.completadas + 1} de {asignacion.rutina.total_sesiones}",
                "Duración": f"{asignacion.rutina.duracion_sesion} min",
                "Membresía": f"{m.codigo} · vence {f_fecha(m.fecha_vencimiento)} ({m.dias_restantes} días)",
            })
            self.mostrar_enfoque(enfoque)
            if asignacion.observaciones:
                self.v.info(f"Nota del entrenador: {asignacion.observaciones}")
        else:
            self.v.aviso(f"Hoy es día de descanso en el plan de {cliente.nombre_pila}"
                         + ("." if cliente.asignaciones_activas else " (no tiene rutinas asignadas)."))
            self.v.info("Si viene a entrenar, se registra como entrenamiento libre.")
        asistio = self.v.si_no(f"¿{cliente.nombre_pila} asistió?", default=True)
        ses = self.repo.registrar_sesion(m, hoy, asistio, asignacion, enfoque)
        if asistio:
            self.v.exito(f"Bienvenido(a), {cliente.nombre_pila}. Asistencia {ses.codigo} registrada "
                         f"({f_hora(ses.hora_inicio)} – {f_hora(ses.hora_fin)}).")
            if asignacion and asignacion.estado == "Terminada":
                self.v.exito(f"¡Completó las {asignacion.rutina.total_sesiones} sesiones de "
                             f"«{asignacion.rutina.nombre}»! La rutina queda terminada.")
            elif asignacion:
                self.v.info(f"La próxima vez le toca: {asignacion.siguiente_enfoque.titulo}.")
        else:
            self.v.aviso(f"Falta registrada ({ses.codigo}). La próxima vez le vuelve a tocar "
                         f"{enfoque.titulo}." if enfoque else f"Falta registrada ({ses.codigo}).")

    def agenda_hoy(self) -> None:
        """Clientes que entrenan hoy según su plan semanal y si ya se registraron."""
        hoy = date.today()
        filas = []
        for c in sorted(self.repo.clientes, key=lambda c: c.nombre_completo):
            a, en = self.repo.que_le_toca(c, hoy)
            ses = c.sesion_del_dia(hoy)
            if not a and not ses:
                continue
            situacion = ("[dim]Pendiente[/]" if not ses else
                         "[green]Asistió[/]" if ses.asistio else "[red]Faltó[/]")
            if ses and ses.enfoque:
                en = ses.enfoque
            filas.append([c.codigo, c.nombre_completo, t(a.rutina.nombre) if a else "Libre",
                          t(en.titulo) if en else "—", situacion])
        self.v.tabla(f"Agenda de hoy · {DIAS[hoy.weekday()]} {f_fecha(hoy)}",
                     ["Código", "Cliente", "Rutina", "Le toca", "Asistencia"], filas,
                     pie=f"{len(filas)} cliente(s) programado(s)")


# ===========================================================================
# Entrenador
# ===========================================================================
class MenuEntrenador(MenuBase):
    titulo = "Menú del Entrenador"

    def opciones(self) -> Opciones:
        return [
            ("Mi horario", self.mi_horario),
            ("Mis clases", self.mis_clases),
            ("Catálogo de rutinas (ver completa)", self.ver_rutina),
            ("Diseñar rutina", self.disenar_rutina),
            ("Asignar rutina a un cliente", self.asignar_rutina),
            ("Plan semanal de un cliente", self.rutinas_cliente),
            ("Sesiones de un cliente", self.sesiones_cliente),
            ("Catálogo de ejercicios", self.catalogo_ejercicios),
        ]

    def mi_horario(self) -> None:
        """RF-12"""
        horarios = sorted(self.usuario.horarios, key=lambda h: DIAS.index(h.dia))
        self.v.tabla("Mi horario de trabajo", ["Día", "Entrada", "Salida", "Horas"],
                     [[h.dia, f_hora(h.hora_inicio), f_hora(h.hora_fin),
                       f"{(h.hora_fin.hour * 60 + h.hora_fin.minute - h.hora_inicio.hour * 60 - h.hora_inicio.minute) / 60:.1f}"]
                      for h in horarios], derecha=["Horas"])

    def mis_clases(self) -> None:
        """RF-13"""
        clases = sorted(self.usuario.clases, key=lambda c: c.orden)
        clase = self.v.elegir(clases, "Clases que imparto", self.COLS_CLASE, self.fila_clase,
                              opcional=True, pregunta="Ver inscritos de la clase")
        if clase:
            self.v.tabla(f"Inscritos en {clase.nombre}", ["Cliente", "Celular", "Inscrito el", "Observaciones"],
                         [[i.cliente.nombre_completo, i.cliente.celulares[0], f_fecha(i.fecha),
                           t(i.observaciones)] for i in clase.inscritos],
                         pie=f"{len(clase.inscritos)} de {clase.cupo_max} lugares ocupados")

    def ver_rutina(self) -> None:
        """RF-15: catálogo y detalle completo (enfoques y ejercicios)."""
        r = self.elegir_rutina(solo_activas=False)
        self.v.encabezado(f"Rutina {r.nombre}", self.usuario)
        self.mostrar_rutina(r)

    def capturar_enfoques(self) -> list:
        """Pide los enfoques (días) y, en cada uno, sus ejercicios con series y repeticiones."""
        enfoques = []
        while True:
            dia = len(enfoques) + 1
            self.v.seccion(f"Día {dia} de la rutina")
            desc = self.v.texto(f"Enfoque del día {dia} [dim](ej. Pierna y glúteo; Enter para terminar)[/]",
                                obligatorio=not enfoques)
            if not desc:
                return enfoques
            self.v.tabla("Catálogo de ejercicios", ["Código", "Ejercicio"],
                         [[e.codigo, t(e.nombre)] for e in self.repo.ejercicios])
            ejercicios = []
            while True:
                texto = self.v.texto(f"Ejercicio {len(ejercicios) + 1} [dim](código; N = nuevo; Enter para terminar)[/]",
                                     obligatorio=not ejercicios)
                if not texto:
                    break
                if texto.upper() == "N":
                    ej = self.repo.agregar_ejercicio(self.v.texto("Nombre del ejercicio"),
                                                     self.v.texto("Descripción (cómo se hace)"))
                    self.v.info(f"Ejercicio {ej.codigo} agregado al catálogo.")
                else:
                    ej = self.repo.por_codigo(self.repo.ejercicios, texto)
                    if not ej:
                        self.v.consola.print("[red]  Código no encontrado en el catálogo.[/]")
                        continue
                if any(e is ej for e, _, _ in ejercicios):
                    self.v.consola.print("[red]  Ese ejercicio ya está en este enfoque.[/]")
                    continue
                series = self.v.entero("  Series", 3)
                reps = self.v.texto("  Repeticiones [dim](ej. 12 o 30 s)[/]", "12")
                ejercicios.append((ej, series, reps))
                self.v.info(f"{t(ej.nombre)}: {series} × {t(reps)}")
            enfoques.append((desc, ejercicios))

    def disenar_rutina(self) -> None:
        """RF-14: diseñar una rutina del catálogo con sus enfoques y ejercicios."""
        self.v.seccion("Datos generales")
        nombre = self.v.texto("Nombre de la rutina")
        if any(r.nombre.lower() == nombre.lower() for r in self.repo.rutinas):
            raise ReglaNegocio(f"Ya existe una rutina llamada «{nombre}».")
        objetivo = self.v.texto("Objetivo")
        descripcion = self.v.texto("Descripción", obligatorio=False)
        frecuencia = self.v.entero("Frecuencia (sesiones por semana, 1 a 7)", 3)
        if frecuencia > 7:
            raise ReglaNegocio("La frecuencia debe ser de 1 a 7 sesiones por semana.")
        descanso = self.v.entero("Días de descanso por semana", 7 - frecuencia, minimo=0)
        duracion = self.v.entero("Duración por sesión (minutos)", 60)
        total = self.v.entero("Total de sesiones", frecuencia * 12)
        Rutina("RUT-000", self.usuario, nombre, objetivo, descripcion, frecuencia, duracion, total, descanso,
               date.today())                                     # valida antes de pedir enfoques
        enfoques = self.capturar_enfoques()
        self.v.ficha("Nueva rutina", {
            "Nombre": t(nombre), "Objetivo": t(objetivo), "Frecuencia": f"{frecuencia} por semana",
            "Duración": f"{duracion} min", "Total de sesiones": total, "Descanso": f"{descanso} días",
            "Enfoques": " · ".join(f"Día {i}: {t(d)} ({len(e)} ej.)" for i, (d, e) in enumerate(enfoques, 1)),
        })
        self.guardar("¿Guardar la rutina?")
        r = self.repo.crear_rutina(self.usuario, nombre, objetivo, descripcion, frecuencia, duracion, total,
                                   descanso, enfoques)
        self.v.exito(f"Rutina {r.codigo} «{r.nombre}» guardada con {len(r.enfoques)} enfoque(s).")

    def asignar_rutina(self) -> None:
        """RF-15: asignar una rutina del catálogo y fijar sus días de la semana.
        Se pueden combinar varias rutinas para cubrir los 7 días."""
        cliente = self.buscar_cliente(solo_activos=True)
        self.mostrar_plan(cliente)
        libres = self.repo.dias_libres(cliente)
        if not libres:
            raise ReglaNegocio(f"{cliente.nombre_pila} ya tiene rutina los 7 días. "
                               "Termina una asignación para cambiar su plan.")
        ya = {a.rutina for a in cliente.asignaciones_activas}
        posibles = [r for r in self.repo.rutinas if r.activa and r not in ya and r.frecuencia <= len(libres)]
        if not posibles:
            raise ReglaNegocio(f"Ninguna rutina activa cabe en sus {len(libres)} día(s) libre(s).")
        self.v.info(f"Días libres: {', '.join(libres)}. Solo aparecen rutinas que caben en ellos.")
        rutina = self.elegir_rutina(rutinas=posibles)
        propuesta = self.repo.proponer_dias(cliente, rutina)
        self.v.info(f"«{rutina.nombre}» se entrena {rutina.frecuencia} días por semana. "
                    f"Propuesta: {', '.join(propuesta)}. Enter para aceptar o escribe otros días.")
        while True:
            dias = self.v.dias(propuesta)
            try:
                self.repo.validar_asignacion(cliente, rutina, dias)
                break
            except ReglaNegocio as e:
                self.v.consola.print(f"[red]  {e}[/]")
        obs = self.v.texto("Observaciones para este cliente [dim](ajustes, lesiones…)[/]", obligatorio=False)
        self.guardar(f"¿Asignar «{rutina.nombre}» a {cliente.nombre_completo} los {', '.join(dias)}?")
        a = self.repo.asignar_rutina(cliente, rutina, self.usuario, dias, obs)
        self.v.exito(f"Asignación {a.codigo} guardada. El sistema le irá diciendo qué enfoque le toca cada día.")
        self.mostrar_plan(cliente)

    def rutinas_cliente(self) -> None:
        """RF-15: plan semanal y rutinas asignadas a un cliente."""
        cliente = self.buscar_cliente()
        self.mostrar_plan(cliente)
        self.v.tabla(f"Rutinas de {cliente.nombre_completo}", self.COLS_ASIGNACION,
                     map(self.fila_asignacion, sorted(cliente.asignaciones, key=lambda a: a.fecha_asignacion,
                                                     reverse=True)))

    def sesiones_cliente(self) -> None:
        """RF-16: sesiones de entrenamiento de un cliente en un periodo."""
        cliente = self.buscar_cliente()
        inicio, fin = self.pedir_periodo()
        lista = [s for s in self.sesiones_de(cliente) if inicio <= s.fecha <= fin]
        self.v.tabla(f"Sesiones de {cliente.nombre_completo}", self.COLS_SESION, map(self.fila_sesion, lista))

    def catalogo_ejercicios(self) -> None:
        """Catálogo de ejercicios; permite agregar uno nuevo."""
        self.v.tabla("Catálogo de ejercicios", ["Código", "Ejercicio", "Descripción", "Enfoques"],
                     [[e.codigo, t(e.nombre), t(e.descripcion),
                       sum(any(x.ejercicio is e for x in en.ejercicios) for en in self.repo.enfoques())]
                      for e in self.repo.ejercicios], derecha=["Enfoques"])
        if self.v.si_no("¿Agregar un ejercicio nuevo?", default=False):
            nombre = self.v.texto("Nombre del ejercicio")
            desc = self.v.texto("Descripción (cómo se hace)")
            self.guardar()
            self.v.exito(f"Ejercicio {self.repo.agregar_ejercicio(nombre, desc).codigo} agregado.")


# ===========================================================================
# Administrador
# ===========================================================================
class MenuAdministrador(MenuEntrenador, MenuRecepcionista):
    """El administrador hereda las operaciones de recepción y de entrenador
    y agrega las de administración."""
    titulo = "Panel de Administración"

    def antes_del_menu(self) -> None:
        hoy = date.today()
        self.v.tarjetas({
            "Clientes activos": sum(c.activo for c in self.repo.clientes),
            "Membresías activas": sum(m.estado_actual == "Activa" for m in self.repo.membresias),
            "Ingresos del mes": dinero(sum(p.monto for p in self.repo.pagos
                                           if (p.fecha_pago.year, p.fecha_pago.month) == (hoy.year, hoy.month))),
            "Asistencias hoy": sum(x.fecha == hoy and x.asistio for x in self.repo.sesiones),
        })

    def opciones(self) -> Opciones:
        s = self.submenu
        return [
            ("Empleados", s("Empleados", [
                ("Listar empleados", self.listar_empleados),
                ("Agregar empleado", self.agregar_empleado),
                ("Editar empleado", self.editar_empleado),
                ("Activar / desactivar empleado", self.cambiar_estado_empleado)])),
            ("Roles", s("Roles", [
                ("Listar roles", self.listar_roles),
                ("Agregar rol", self.agregar_rol),
                ("Editar rol", self.editar_rol)])),
            ("Horarios de empleados", s("Horarios", [
                ("Consultar horarios", self.consultar_horarios),
                ("Asignar horario", self.asignar_horario),
                ("Editar horario", self.editar_horario),
                ("Eliminar horario", self.eliminar_horario)])),
            ("Clientes", s("Clientes", [
                ("Listar clientes", self.listar_clientes),
                ("Buscar cliente e historial", self.ver_historial_cliente),
                ("Agregar cliente", self.registrar_cliente),
                ("Editar cliente", self.editar_cliente),
                ("Dar de baja / reactivar cliente", self.cambiar_estado_cliente)])),
            ("Tipos de membresía y beneficios", s("Tipos de membresía y beneficios", [
                ("Ver tipos de membresía", self.ver_tipos_membresia),
                ("Agregar tipo de membresía", self.agregar_tipo),
                ("Editar tipo de membresía", self.editar_tipo),
                ("Eliminar tipo de membresía", self.eliminar_tipo),
                ("Beneficios: listar / agregar / eliminar", self.gestionar_beneficios),
                ("Asignar o quitar beneficios a un tipo", self.asignar_beneficios)])),
            ("Membresías", s("Membresías", [
                ("Consultar membresías (con filtros)", self.consultar_membresias),
                ("Vender membresía", self.vender_membresia),
                ("Consultar / renovar membresía", self.consultar_membresia),
                ("Cancelar membresía", self.cancelar_membresia),
                ("Actualizar membresías vencidas", self.actualizar_vencidas)])),
            ("Pagos y métodos de pago", s("Pagos y métodos de pago", [
                ("Historial de pagos", self.historial_pagos),
                ("Listar métodos de pago", self.listar_metodos),
                ("Agregar método de pago", self.agregar_metodo),
                ("Editar método de pago", self.editar_metodo),
                ("Activar / desactivar método", self.cambiar_estado_metodo)])),
            ("Clases y especialidades", s("Clases y especialidades", [
                ("Listar clases", self.listar_clases),
                ("Agregar clase", self.agregar_clase),
                ("Editar clase", self.editar_clase),
                ("Cerrar / reabrir clase", self.cambiar_estado_clase),
                ("Listar especialidades", self.listar_especialidades),
                ("Agregar especialidad", self.agregar_especialidad),
                ("Editar especialidad", self.editar_especialidad),
                ("Eliminar especialidad", self.eliminar_especialidad)])),
            ("Inscripciones a clases", s("Inscripciones", [
                ("Por clase", self.inscripciones_por_clase),
                ("Por cliente", self.inscripciones_por_cliente),
                ("Inscribir cliente", self.inscribir_clase),
                ("Cambiar estado de una inscripción", self.cambiar_estado_inscripcion)])),
            ("Rutinas y sesiones", s("Rutinas y sesiones", [
                ("Catálogo de rutinas (ver completa)", self.ver_rutina),
                ("Diseñar rutina", self.disenar_rutina),
                ("Editar datos o activar / inactivar una rutina", self.editar_rutina),
                ("Asignar rutina a un cliente", self.asignar_rutina),
                ("Consultar asignaciones", self.consultar_asignaciones),
                ("Terminar / reactivar una asignación", self.cambiar_estado_asignacion),
                ("Catálogo de ejercicios", self.catalogo_ejercicios),
                ("Consultar sesiones de entrenamiento", self.consultar_sesiones),
                ("Registrar asistencia ", self.registrar_sesion),
                ("Agenda de hoy", self.agenda_hoy)])),
            ("Reportes generales", s("Reportes", [
                ("Ingresos por periodo", self.reporte_ingresos),
                ("Membresías por estado", self.reporte_membresias),
                ("Clientes activos y vencidos", self.reporte_clientes),
                ("Asistencia al gimnasio (sesiones)", self.reporte_asistencia),
                ("Ocupación de las clases", self.reporte_ocupacion),
                ("Clases por especialidad", self.reporte_especialidades)])),
        ]

    # ------------------------------------------------------------ empleados (RF-17)
    COLS_EMP = ["Código", "Nombre", "Usuario", "Correo", "Rol", "Estado"]

    @staticmethod
    def fila_emp(e):
        return [e.codigo, e.nombre_completo, e.nombre_usuario, e.correo, e.rol.nombre_rol, estado(e.estado)]

    def elegir_empleado(self, solo_activos=False):
        lista = [e for e in self.repo.empleados if e.activo or not solo_activos]
        return self.v.elegir(lista, "Empleados", self.COLS_EMP, self.fila_emp)

    def elegir_rol(self):
        return self.v.elegir(self.repo.roles, "Roles", ["Código", "Rol"],
                             lambda r: [r.codigo, r.nombre_rol])

    def listar_empleados(self):
        self.v.tabla("Empleados", self.COLS_EMP, map(self.fila_emp, self.repo.empleados))

    def agregar_empleado(self):
        nombre = self.v.texto("Nombre(s)")
        ap_1 = self.v.texto("Primer apellido")
        ap_2 = self.v.texto("Segundo apellido", obligatorio=False)
        correo = self.v.texto("Correo")
        usuario = self.v.texto("Nombre de usuario")
        contrasena = self.v.contrasena()
        rol = self.elegir_rol()
        self.guardar(f"¿Agregar a {nombre} {ap_1} como {rol.nombre_rol}?")
        e = self.repo.agregar_empleado(rol, nombre, ap_1, ap_2, usuario, contrasena, correo)
        self.v.exito(f"Empleado {e.codigo} agregado.")

    def editar_empleado(self):
        e = self.elegir_empleado()
        self.v.seccion("Enter conserva el valor actual")
        nombre = self.v.texto("Nombre(s)", e.nombre_pila)
        ap_1 = self.v.texto("Primer apellido", e.ap_1)
        ap_2 = self.v.texto("Segundo apellido", e.ap_2 or None, obligatorio=False)
        correo = self.v.texto("Correo", e.correo)
        usuario = self.v.texto("Nombre de usuario", e.nombre_usuario)
        if usuario != e.nombre_usuario and any(x.nombre_usuario == usuario for x in self.repo.empleados):
            raise ReglaNegocio("Ese nombre de usuario ya existe.")
        nueva = self.v.contrasena("Nueva contraseña (Enter para no cambiar)") if \
            self.v.si_no("¿Cambiar contraseña?", default=False) else e.contrasena
        rol = self.elegir_rol() if self.v.si_no("¿Cambiar rol?", default=False) else e.rol
        self.guardar()
        e.nombre_pila, e.ap_1, e.ap_2, e.correo = nombre, ap_1, ap_2, correo
        e.nombre_usuario, e.contrasena, e.rol = usuario, nueva or e.contrasena, rol
        self.repo.guardar_cambios(e)      # guarda en la base de datos
        self.v.exito("Empleado actualizado.")

    def cambiar_estado_empleado(self):
        e = self.elegir_empleado()
        if e is self.usuario:
            raise ReglaNegocio("No puedes desactivar tu propia cuenta.")
        nuevo = "Inactivo" if e.activo else "Activo"
        self.guardar(f"¿Cambiar a {e.nombre_completo} a «{nuevo}»?")
        e.estado = nuevo
        self.repo.guardar_cambios(e)      # guarda en la base de datos
        self.v.exito(f"{e.nombre_completo} ahora está {nuevo.lower()}.")

    # ------------------------------------------------------------ roles (RF-18)
    def listar_roles(self):
        self.v.tabla("Roles", ["Código", "Rol", "Empleados"],
                     [[r.codigo, r.nombre_rol, sum(e.rol is r for e in self.repo.empleados)]
                      for r in self.repo.roles], derecha=["Empleados"])

    def agregar_rol(self):
        nombre = self.v.texto("Nombre del rol")
        self.guardar()
        self.v.exito(f"Rol {self.repo.agregar_rol(nombre).codigo} agregado.")

    def editar_rol(self):
        r = self.elegir_rol()
        nombre = self.v.texto("Nombre del rol", r.nombre_rol)
        self.guardar()
        r.nombre_rol = nombre
        self.repo.guardar_cambios(r)      # guarda en la base de datos
        self.v.exito("Rol actualizado.")

    # ------------------------------------------------------------ horarios (RF-19)
    COLS_HOR = ["Código", "Empleado", "Día", "Entrada", "Salida"]

    @staticmethod
    def fila_hor(h):
        return [h.codigo, h.empleado.nombre_completo, h.dia, f_hora(h.hora_inicio), f_hora(h.hora_fin)]

    def horarios_ordenados(self, empleado=None):
        lista = [h for h in self.repo.horarios if empleado is None or h.empleado is empleado]
        return sorted(lista, key=lambda h: (h.empleado.codigo, DIAS.index(h.dia)))

    def consultar_horarios(self):
        empleado = None
        if self.v.si_no("¿Filtrar por empleado?", default=False):
            empleado = self.elegir_empleado()
        self.v.tabla("Horarios", self.COLS_HOR, map(self.fila_hor, self.horarios_ordenados(empleado)))

    def asignar_horario(self):
        e = self.elegir_empleado(solo_activos=True)
        dia = self.v.dia()
        if any(h.dia == dia for h in e.horarios):
            raise ReglaNegocio(f"{e.nombre_pila} ya tiene horario el {dia.lower()}; edítalo.")
        inicio = self.v.hora("Hora de entrada")
        fin = self.v.hora("Hora de salida")
        self.guardar()
        self.v.exito(f"Horario {self.repo.agregar_horario(e, dia, inicio, fin).codigo} asignado.")

    def editar_horario(self):
        h = self.v.elegir(self.horarios_ordenados(), "Horarios", self.COLS_HOR, self.fila_hor)
        dia = self.v.dia(h.dia)
        inicio = self.v.hora("Hora de entrada", h.hora_inicio)
        fin = self.v.hora("Hora de salida", h.hora_fin)
        if fin <= inicio:
            raise ReglaNegocio("La hora de fin debe ser posterior a la de inicio.")
        self.guardar()
        h.dia, h.hora_inicio, h.hora_fin = dia, inicio, fin
        self.repo.guardar_cambios(h)      # guarda en la base de datos
        self.v.exito("Horario actualizado.")

    def eliminar_horario(self):
        h = self.v.elegir(self.horarios_ordenados(), "Horarios", self.COLS_HOR, self.fila_hor)
        self.guardar(f"¿Eliminar el horario del {h.dia.lower()} de {h.empleado.nombre_pila}?")
        self.repo.eliminar_horario(h)
        self.v.exito("Horario eliminado.")

    # ------------------------------------------------------------ clientes (RF-20)
    def listar_clientes(self):
        self.v.tabla("Clientes", self.COLS_CLIENTE, map(self.fila_cliente, self.repo.clientes))

    def ver_historial_cliente(self):
        c = self.buscar_cliente()
        self.v.encabezado(f"Historial de {c.nombre_completo}", self.usuario)
        self.historial_cliente(c)

    def editar_cliente(self):
        c = self.buscar_cliente()
        self.v.seccion("Enter conserva el valor actual")
        nombre = self.v.texto("Nombre(s)", c.nombre_pila)
        ap_1 = self.v.texto("Primer apellido", c.ap_1)
        ap_2 = self.v.texto("Segundo apellido", c.ap_2 or None, obligatorio=False)
        fecha_nac = self.v.fecha("Fecha de nacimiento", c.fecha_nacimiento)
        colonia = self.v.texto("Colonia", c.colonia)
        calle = self.v.texto("Calle y número", c.calle)
        celulares = self.v.celulares(c.celulares) if self.v.si_no("¿Cambiar celulares?", False) else c.celulares
        self.guardar()
        c.nombre_pila, c.ap_1, c.ap_2, c.fecha_nacimiento = nombre, ap_1, ap_2, fecha_nac
        c.colonia, c.calle, c.celulares = colonia, calle, celulares
        self.repo.guardar_cambios(c)      # guarda en la base de datos
        self.v.exito("Cliente actualizado.")

    def cambiar_estado_cliente(self):
        c = self.buscar_cliente()
        nuevo = "Inactivo" if c.activo else "Activo"
        accion = "dar de baja" if c.activo else "reactivar"
        self.guardar(f"¿{accion.capitalize()} a {c.nombre_completo}?")
        c.estado = nuevo
        self.repo.guardar_cambios(c)      # guarda en la base de datos
        self.v.exito(f"Cliente {c.codigo} ahora está {nuevo.lower()}.")

    # ------------------------------------------------------------ tipos y beneficios (RF-21)
    def elegir_beneficios(self, actuales=()) -> list:
        self.v.tabla("Beneficios", ["Código", "Descripción", "Incluido"],
                     [[b.codigo, b.descripcion, "[green]✔[/]" if b in actuales else ""]
                      for b in self.repo.beneficios])
        texto = self.v.texto("Códigos de los beneficios separados por coma [dim](ej. 1,3,4)[/]",
                             ",".join(b.codigo.split("-")[-1].lstrip("0") for b in actuales) or None,
                             obligatorio=False)
        elegidos = []
        for parte in filter(None, (p.strip() for p in texto.split(","))):
            b = self.repo.por_codigo(self.repo.beneficios, parte)
            if not b:
                raise ReglaNegocio(f"No existe el beneficio «{parte}».")
            if b not in elegidos:
                elegidos.append(b)
        return elegidos

    def agregar_tipo(self):
        nombre = self.v.texto("Nombre del tipo")
        duracion = self.v.entero("Duración en días")
        monto = self.v.decimal("Monto ($)")
        beneficios = self.elegir_beneficios()
        self.guardar()
        self.v.exito(f"Tipo {self.repo.agregar_tipo(nombre, duracion, monto, beneficios).codigo} agregado.")

    def editar_tipo(self):
        x = self.elegir_tipo()
        nombre = self.v.texto("Nombre", x.nombre)
        duracion = self.v.entero("Duración en días", x.duracion_dias)
        monto = self.v.decimal("Monto ($)", x.monto)
        self.v.info("Los cambios aplican a las membresías que se vendan de aquí en adelante.")
        self.guardar()
        x.nombre, x.duracion_dias, x.monto = nombre, duracion, monto
        self.repo.guardar_cambios(x)      # guarda en la base de datos
        self.v.exito("Tipo de membresía actualizado.")

    def eliminar_tipo(self):
        x = self.elegir_tipo()
        self.guardar(f"¿Eliminar el tipo «{x.nombre}»?")
        self.repo.eliminar_tipo(x)
        self.v.exito("Tipo eliminado.")

    def gestionar_beneficios(self):
        self.v.tabla("Beneficios", ["Código", "Descripción", "Tipos que lo incluyen"],
                     [[b.codigo, b.descripcion,
                       ", ".join(x.nombre for x in self.repo.tipos if b in x.beneficios) or "—"]
                      for b in self.repo.beneficios])
        accion = self.v.opcion("¿Qué deseas hacer?", ["Agregar", "Eliminar", "Nada"])
        if accion == 0:
            desc = self.v.texto("Descripción del beneficio")
            self.guardar()
            self.v.exito(f"Beneficio {self.repo.agregar_beneficio(desc).codigo} agregado.")
        elif accion == 1:
            b = self.repo.por_codigo(self.repo.beneficios, self.v.texto("Código del beneficio"))
            if not b:
                raise ReglaNegocio("Beneficio no encontrado.")
            self.guardar(f"¿Eliminar «{b.descripcion}»? Se quitará de todos los tipos.")
            self.repo.eliminar_beneficio(b)
            self.v.exito("Beneficio eliminado.")

    def asignar_beneficios(self):
        x = self.elegir_tipo()
        nuevos = self.elegir_beneficios(x.beneficios)
        self.guardar()
        x.beneficios = nuevos
        self.repo.guardar_cambios(x)      # guarda en la base de datos
        self.v.exito(f"«{x.nombre}» ahora incluye {len(nuevos)} beneficio(s).")

    # ------------------------------------------------------------ membresías (RF-22)
    def consultar_membresias(self):
        filtro = self.v.opcion("Filtrar por", ["Todas", "Estado", "Tipo", "Cliente", "Empleado"])
        lista = self.repo.membresias
        titulo = "Membresías"
        if filtro == 1:
            est = ["Activa", "Vencida", "Cancelada"][self.v.opcion("Estado", ["Activa", "Vencida", "Cancelada"])]
            lista, titulo = [m for m in lista if m.estado_actual == est], f"Membresías {est.lower()}s"
        elif filtro == 2:
            x = self.elegir_tipo()
            lista, titulo = x.membresias, f"Membresías tipo {x.nombre}"
        elif filtro == 3:
            c = self.buscar_cliente()
            lista, titulo = c.membresias, f"Membresías de {c.nombre_completo}"
        elif filtro == 4:
            e = self.elegir_empleado()
            lista, titulo = [m for m in lista if m.empleado is e], f"Membresías inscritas por {e.nombre_completo}"
        self.v.tabla(titulo, self.COLS_MEMBRESIA + ["Inscribió"],
                     [self.fila_membresia(m) + [m.empleado.nombre_pila] for m in lista])

    def actualizar_vencidas(self):
        cambios = self.repo.actualizar_estados()
        self.v.exito(f"Se actualizaron {cambios} membresía(s).") if cambios else \
            self.v.info("Todas las membresías ya tenían su estado correcto.")

    # ------------------------------------------------------------ pagos (RF-23)
    def historial_pagos(self):
        filtro = self.v.opcion("Filtrar por", ["Todos", "Cliente", "Periodo", "Método de pago"])
        pagos = self.repo.pagos
        if filtro == 1:
            c = self.buscar_cliente()
            pagos = [p for p in pagos if p.membresia.cliente is c]
        elif filtro == 2:
            ini, fin = self.pedir_periodo()
            pagos = [p for p in pagos if ini <= p.fecha_pago <= fin]
        elif filtro == 3:
            m = self.v.elegir(self.repo.metodos, "Métodos", ["Código", "Método"], lambda x: [x.codigo, x.nombre])
            pagos = [p for p in pagos if p.metodo is m]
        pagos = sorted(pagos, key=lambda p: p.fecha_pago, reverse=True)
        self.v.tabla("Historial de pagos", self.COLS_PAGO, map(self.fila_pago, pagos), derecha=["Monto"],
                     pie=f"{len(pagos)} pago(s) · Total: {dinero(sum(p.monto for p in pagos))}")

    def listar_metodos(self):
        self.v.tabla("Métodos de pago", ["Código", "Método", "Estado", "Pagos"],
                     [[m.codigo, m.nombre, estado(m.estado), sum(p.metodo is m for p in self.repo.pagos)]
                      for m in self.repo.metodos], derecha=["Pagos"])

    def agregar_metodo(self):
        nombre = self.v.texto("Nombre del método")
        self.guardar()
        self.v.exito(f"Método {self.repo.agregar_metodo(nombre).codigo} agregado.")

    def editar_metodo(self):
        m = self.v.elegir(self.repo.metodos, "Métodos", ["Código", "Método"], lambda x: [x.codigo, x.nombre])
        nombre = self.v.texto("Nombre", m.nombre)
        self.guardar()
        m.nombre = nombre
        self.repo.guardar_cambios(m)      # guarda en la base de datos
        self.v.exito("Método actualizado.")

    def cambiar_estado_metodo(self):
        m = self.v.elegir(self.repo.metodos, "Métodos", ["Código", "Método", "Estado"],
                          lambda x: [x.codigo, x.nombre, estado(x.estado)])
        nuevo = "Inactivo" if m.activo else "Activo"
        self.guardar(f"¿Cambiar «{m.nombre}» a {nuevo.lower()}?")
        m.estado = nuevo
        self.repo.guardar_cambios(m)      # guarda en la base de datos
        self.v.exito(f"Método {m.nombre} {nuevo.lower()}.")

    # ------------------------------------------------------------ clases y especialidades (RF-24, RF-25)
    def clases_ordenadas(self):
        return sorted(self.repo.clases, key=lambda c: c.orden)

    def elegir_clase(self):
        return self.v.elegir(self.clases_ordenadas(), "Clases", self.COLS_CLASE + ["Pública"],
                             lambda c: self.fila_clase(c) + [estado("Sí" if c.publico else "No")])

    def elegir_especialidad(self):
        return self.v.elegir(self.repo.especialidades, "Especialidades", ["Código", "Especialidad"],
                             lambda e: [e.codigo, e.nombre])

    def elegir_instructor(self):
        return self.v.elegir(self.repo.entrenadores(), "Entrenadores", ["Código", "Nombre"],
                             lambda e: [e.codigo, e.nombre_completo])

    def listar_clases(self):
        self.v.tabla("Clases", self.COLS_CLASE + ["Pública"],
                     [self.fila_clase(c) + [estado("Sí" if c.publico else "No")] for c in self.clases_ordenadas()])

    def agregar_clase(self):
        nombre = self.v.texto("Nombre de la clase")
        dias = self.v.dias()
        inicio = self.v.hora("Hora de inicio")
        fin = self.v.hora("Hora de fin")
        cupo = self.v.entero("Cupo máximo")
        publico = self.v.si_no("¿Es pública?")
        esp = self.elegir_especialidad()
        instructor = self.elegir_instructor()
        self.guardar()
        c = self.repo.agregar_clase(nombre, instructor, esp, dias, inicio, fin, cupo, publico)
        self.v.exito(f"Clase {c.codigo} creada.")

    def editar_clase(self):
        c = self.elegir_clase()
        self.v.seccion("Enter conserva el valor actual")
        nombre = self.v.texto("Nombre", c.nombre)
        dias = self.v.dias(c.dias)
        inicio = self.v.hora("Hora de inicio", c.hora_inicio)
        fin = self.v.hora("Hora de fin", c.hora_fin)
        cupo = self.v.entero("Cupo máximo", c.cupo_max)
        if fin <= inicio:
            raise ReglaNegocio("La hora de fin debe ser posterior a la de inicio.")
        if cupo < len(c.inscritos):
            raise ReglaNegocio(f"Ya hay {len(c.inscritos)} inscritos; el cupo no puede ser menor.")
        publico = self.v.si_no("¿Es pública?", c.publico)
        esp = self.elegir_especialidad() if self.v.si_no("¿Cambiar especialidad?", False) else c.especialidad
        inst = self.elegir_instructor() if self.v.si_no("¿Cambiar instructor?", False) else c.empleado
        self.guardar()
        c.nombre, c.dias, c.hora_inicio, c.hora_fin, c.cupo_max, c.publico = nombre, dias, inicio, fin, cupo, publico
        self.repo.reasignar_clase(c, inst, esp)
        self.v.exito("Clase actualizada.")

    def cambiar_estado_clase(self):
        c = self.elegir_clase()
        nuevo = "Cerrada" if c.estado == "Activa" else "Activa"
        self.guardar(f"¿Cambiar «{c.nombre}» a {nuevo.lower()}?")
        c.estado = nuevo
        self.repo.guardar_cambios(c)      # guarda en la base de datos
        self.v.exito(f"Clase {c.codigo} {nuevo.lower()}.")

    def listar_especialidades(self):
        self.v.tabla("Especialidades", ["Código", "Especialidad", "Descripción", "Clases"],
                     [[e.codigo, e.nombre, t(e.descripcion), len(e.clases)] for e in self.repo.especialidades],
                     derecha=["Clases"])

    def agregar_especialidad(self):
        nombre = self.v.texto("Nombre")
        desc = self.v.texto("Descripción", obligatorio=False)
        self.guardar()
        self.v.exito(f"Especialidad {self.repo.agregar_especialidad(nombre, desc).codigo} agregada.")

    def editar_especialidad(self):
        e = self.elegir_especialidad()
        nombre = self.v.texto("Nombre", e.nombre)
        desc = self.v.texto("Descripción", e.descripcion or None, obligatorio=False)
        self.guardar()
        e.nombre, e.descripcion = nombre, desc
        self.repo.guardar_cambios(e)      # guarda en la base de datos
        self.v.exito("Especialidad actualizada.")

    def eliminar_especialidad(self):
        e = self.elegir_especialidad()
        self.guardar(f"¿Eliminar «{e.nombre}»?")
        self.repo.eliminar_especialidad(e)
        self.v.exito("Especialidad eliminada.")

    # ------------------------------------------------------------ inscripciones (RF-26)
    COLS_INS = ["Código", "Cliente", "Clase", "Días", "Fecha", "Estado", "Observaciones"]

    @staticmethod
    def fila_ins(i):
        return [i.codigo, i.cliente.nombre_completo, i.clase.nombre, i.clase.dias_txt, f_fecha(i.fecha),
                estado(i.estado), t(i.observaciones)]

    def inscripciones_por_clase(self):
        c = self.elegir_clase()
        self.v.tabla(f"Inscripciones de {c.nombre}", self.COLS_INS, map(self.fila_ins, c.inscripciones),
                     pie=f"{len(c.inscritos)} activa(s) de {c.cupo_max} lugares")

    def inscripciones_por_cliente(self):
        c = self.buscar_cliente()
        self.v.tabla(f"Inscripciones de {c.nombre_completo}", self.COLS_INS, map(self.fila_ins, c.inscripciones))

    def cambiar_estado_inscripcion(self):
        i = self.v.elegir(self.repo.inscripciones, "Inscripciones", self.COLS_INS, self.fila_ins)
        if i.estado == "Activa":
            nuevo = "Cancelada"
        else:
            if i.clase.lugares <= 0:
                raise ReglaNegocio("La clase está llena; no se puede reactivar la inscripción.")
            nuevo = "Activa"
        self.guardar(f"¿Cambiar la inscripción {i.codigo} a {nuevo.lower()}?")
        i.estado = nuevo
        self.repo.guardar_cambios(i)      # guarda en la base de datos
        self.v.exito("Inscripción actualizada.")

    # ------------------------------------------------------------ rutinas y sesiones (RF-27)
    def editar_rutina(self):
        r = self.elegir_rutina(solo_activas=False)
        self.v.seccion("Enter conserva el valor actual")
        nombre = self.v.texto("Nombre", r.nombre)
        if nombre.lower() != r.nombre.lower() and any(x.nombre.lower() == nombre.lower() for x in self.repo.rutinas):
            raise ReglaNegocio(f"Ya existe una rutina llamada «{nombre}».")
        objetivo = self.v.texto("Objetivo", r.objetivo)
        desc = self.v.texto("Descripción", r.descripcion or None, obligatorio=False)
        frecuencia = self.v.entero("Frecuencia (sesiones por semana)", r.frecuencia)
        descanso = self.v.entero("Días de descanso por semana", r.dias_descanso, minimo=0)
        duracion = self.v.entero("Duración por sesión (minutos)", r.duracion_sesion)
        total = self.v.entero("Total de sesiones", r.total_sesiones)
        activa = self.v.si_no("¿Rutina activa?", r.activa)
        Rutina(r.codigo, r.empleado, nombre, objetivo, desc, frecuencia, duracion, total, descanso,
               r.fecha_creacion)                                 # valida los números
        self.guardar()
        r.nombre, r.objetivo, r.descripcion = nombre, objetivo, desc
        r.frecuencia, r.dias_descanso, r.duracion_sesion, r.total_sesiones = frecuencia, descanso, duracion, total
        r.estado = "Activa" if activa else "Inactiva"
        self.repo.guardar_cambios(r)      # guarda en la base de datos
        self.v.exito("Rutina actualizada.")

    def consultar_asignaciones(self):
        filtro = self.v.opcion("Filtrar por", ["Todas", "Cliente", "Rutina", "Entrenador que asignó"])
        lista = self.repo.asignaciones
        if filtro == 1:
            lista = self.buscar_cliente().asignaciones
        elif filtro == 2:
            lista = self.elegir_rutina(solo_activas=False).asignaciones
        elif filtro == 3:
            lista = self.elegir_instructor().asignaciones
        self.v.tabla("Asignaciones de rutinas", self.COLS_ASIGNACION,
                     map(self.fila_asignacion, sorted(lista, key=lambda a: a.fecha_asignacion, reverse=True)))

    def cambiar_estado_asignacion(self):
        a = self.v.elegir(self.repo.asignaciones, "Asignaciones", self.COLS_ASIGNACION, self.fila_asignacion)
        if a.estado == "Activa":
            nuevo = "Terminada"
        else:
            self.repo.validar_asignacion(a.cliente, a.rutina, a.dias, actual=a)   # rutina repetida o días ocupados
            nuevo = "Activa"
        self.guardar(f"¿Cambiar la asignación {a.codigo} a {nuevo.lower()}?")
        a.estado = nuevo
        self.repo.guardar_cambios(a)      # guarda en la base de datos
        self.v.exito("Asignación actualizada.")

    def consultar_sesiones(self):
        filtro = self.v.opcion("Filtrar por", ["Todas", "Cliente", "Rutina", "Periodo"])
        lista = self.repo.sesiones
        if filtro == 1:
            lista = self.buscar_cliente().sesiones
        elif filtro == 2:
            r = self.elegir_rutina(solo_activas=False)
            lista = [x for x in lista if x.rutina is r]
        elif filtro == 3:
            ini, fin = self.pedir_periodo()
            lista = [x for x in lista if ini <= x.fecha <= fin]
        lista = sorted(lista, key=lambda x: x.fecha, reverse=True)
        self.v.tabla("Sesiones de entrenamiento", self.COLS_SESION, map(self.fila_sesion, lista),
                     pie=f"{sum(x.asistio for x in lista)} asistencia(s) · {sum(not x.asistio for x in lista)} falta(s)")

    # ------------------------------------------------------------ reportes (RF-28)
    def reporte_ingresos(self):
        ini, fin = self.pedir_periodo()
        pagos = [p for p in self.repo.pagos if ini <= p.fecha_pago <= fin]
        total = sum(p.monto for p in pagos)
        self.v.encabezado(f"Ingresos del {f_fecha(ini)} al {f_fecha(fin)}", self.usuario)
        for titulo, clave in [("Por método de pago", lambda p: p.metodo.nombre),
                              ("Por tipo de membresía", lambda p: p.membresia.tipo.nombre)]:
            grupos: dict[str, list] = {}
            for p in pagos:
                grupos.setdefault(clave(p), []).append(p)
            self.v.tabla(titulo, ["Concepto", "Pagos", "Monto", "Participación"],
                         [[k, len(v), dinero(s := sum(p.monto for p in v)),
                           f"{barra(s, total)} {s / total * 100:5.1f}%"]
                          for k, v in sorted(grupos.items(), key=lambda kv: -sum(p.monto for p in kv[1]))],
                         derecha=["Pagos", "Monto"])
        self.v.ficha("Total del periodo", {"Pagos": len(pagos), "Ingresos": f"[bold green]{dinero(total)}[/]"},
                     color="green")

    def reporte_membresias(self):
        conteo = Counter(m.estado_actual for m in self.repo.membresias)
        total = sum(conteo.values())
        self.v.tabla("Membresías por estado", ["Estado", "Cantidad", "Proporción"],
                     [[estado(e), conteo.get(e, 0), f"{barra(conteo.get(e, 0), total)} "
                       f"{conteo.get(e, 0) / total * 100 if total else 0:5.1f}%"]
                      for e in ("Activa", "Vencida", "Cancelada")],
                     derecha=["Cantidad"], pie=f"Total: {total} membresía(s)")
        por_tipo = Counter(m.tipo.nombre for m in self.repo.membresias if m.estado_actual == "Activa")
        self.v.tabla("Membresías activas por tipo", ["Tipo", "Activas"], por_tipo.most_common(),
                     derecha=["Activas"])

    def reporte_clientes(self):
        clientes = [c for c in self.repo.clientes if c.activo]
        conteo = Counter(c.situacion for c in clientes)
        self.v.tarjetas({"Con membresía activa": conteo["Activa"], "Vencidos": conteo["Vencida"],
                         "Sin membresía": conteo["Sin membresía"]})
        vencidos = [c for c in clientes if c.situacion != "Activa"]
        self.v.tabla("Clientes con membresía vencida o sin membresía",
                     ["Código", "Cliente", "Celular", "Última membresía", "Venció"],
                     [[c.codigo, c.nombre_completo, c.celulares[0],
                       (u := max(c.membresias, key=lambda m: m.fecha_vencimiento)).tipo.nombre if c.membresias else "—",
                       f_fecha(u.fecha_vencimiento) if c.membresias else "—"] for c in vencidos])

    def reporte_asistencia(self):
        ini, fin = self.pedir_periodo()
        todas = [x for x in self.repo.sesiones if ini <= x.fecha <= fin]
        lista = [x for x in todas if x.asistio]
        por_cliente = Counter(x.cliente.nombre_completo for x in lista)
        faltas = Counter(x.cliente.nombre_completo for x in todas if not x.asistio)
        maximo = max(por_cliente.values(), default=0)
        self.v.tabla("Asistencias por cliente", ["Cliente", "Visitas", "Faltas", ""],
                     [[n, v, faltas.get(n, 0), barra(v, maximo)] for n, v in por_cliente.most_common()],
                     derecha=["Visitas", "Faltas"])
        por_dia = Counter(DIAS[x.fecha.weekday()] for x in lista)
        maximo = max(por_dia.values(), default=0)
        self.v.tabla("Sesiones por día de la semana", ["Día", "Visitas", ""],
                     [[d, por_dia.get(d, 0), barra(por_dia.get(d, 0), maximo)] for d in DIAS],
                     derecha=["Visitas"], pie=f"Total: {len(lista)} sesión(es)")

    def reporte_ocupacion(self):
        clases = [c for c in self.clases_ordenadas() if c.estado == "Activa"]
        self.v.tabla("Ocupación de las clases", ["Clase", "Días", "Horario", "Inscritos", "Ocupación"],
                     [[c.nombre, c.dias_txt, c.horario_txt, f"{len(c.inscritos)}/{c.cupo_max}",
                       f"{barra(len(c.inscritos), c.cupo_max)} {len(c.inscritos) / c.cupo_max * 100:5.1f}%"]
                      for c in clases], derecha=["Inscritos"])

    def reporte_especialidades(self):
        self.v.tabla("Clases por especialidad", ["Especialidad", "Total", "Inscritos", "Clases que la imparten"],
                     [[e.nombre, len(e.clases), sum(len(c.inscritos) for c in e.clases),
                       ", ".join(c.nombre for c in e.clases) or "—"] for e in self.repo.especialidades],
                     derecha=["Total", "Inscritos"])
