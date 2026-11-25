"""
repositorio_mysql.py – Repositorio conectado a la base de datos MySQL «sag».

RepositorioMySQL HEREDA de Repositorio: las consultas (buscar clientes,
autenticar, etc.) se reutilizan tal cual, y solo se SOBRESCRIBEN los métodos
que agregan, editan o eliminan datos para que además hagan el INSERT, UPDATE
o DELETE en MySQL. Por eso los menús no cambian.

Funcionamiento:
  • Al iniciar se leen todas las tablas y se arman los objetos de modelos.py.
  • Cada alta, edición o baja se guarda en la base en ese momento.
  • En la base los códigos son números (1, 2, 3…); en el programa se
    muestran como texto (CLI-001). La conversión se hace aquí.

Requisito:
    pip install mysql-connector-python
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from typing import Optional

import mysql.connector

from modelos import (
    DIAS, AsignacionRutina, Beneficio, Clase, Cliente, Ejercicio, EjercicioEnfoque, Empleado, Enfoque,
    Especialidad, Horario, InscripcionClase, Membresia, MetodoPago, Pago, ReglaNegocio, Rol, Rutina,
    SesionEntrenamiento, TipoMembresia,
)
from repositorio import Repositorio

# Mensajes amigables para los errores más comunes de MySQL / MariaDB
MENSAJES_ERROR = {
    1062: "Ya existe un registro con ese dato (debe ser único).",
    1451: "No se puede eliminar: tiene registros relacionados.",
    1452: "El registro relacionado no existe.",
    1406: "Uno de los datos es demasiado largo.",
    3819: "Un dato no cumple las reglas de la base de datos.",   # CHECK en MySQL
    4025: "Un dato no cumple las reglas de la base de datos.",   # CHECK en MariaDB
}


def a_hora(valor) -> time:
    """MySQL regresa las columnas TIME como timedelta; se convierten a time."""
    if isinstance(valor, timedelta):
        return (datetime.min + valor).time()
    return valor


class RepositorioMySQL(Repositorio):
    """Repositorio que guarda todo en la base de datos MySQL."""

    def __init__(self, **config):
        super().__init__()
        self.con = mysql.connector.connect(**config, charset="utf8mb4", autocommit=True)
        self.cargar()

    # ================================================================ utilidades
    @staticmethod
    def codigo(prefijo: str, numero: int) -> str:
        return f"{prefijo}-{numero:03d}"

    @staticmethod
    def id_(objeto) -> int:
        """Convierte el código del objeto (CLI-003) al número de la base (3)."""
        return int(objeto.codigo.split("-")[-1])

    @staticmethod
    def traducir(error: mysql.connector.Error) -> ReglaNegocio:
        # Los triggers usan SIGNAL SQLSTATE '45000' con un mensaje ya en español.
        if error.sqlstate == "45000":
            return ReglaNegocio(error.msg)
        return ReglaNegocio(MENSAJES_ERROR.get(error.errno, f"Error de base de datos: {error.msg}"))

    def _cursor(self):
        if not self.con.is_connected():
            self.con.reconnect(attempts=2, delay=1)
        return self.con.cursor()

    def consultar(self, sql: str, params=()) -> list:
        try:
            cur = self._cursor()
            cur.execute(sql, params)
            filas = cur.fetchall()
            cur.close()
            return filas
        except mysql.connector.Error as e:
            raise self.traducir(e) from e

    def ejecutar(self, sql: str, params=()) -> int:
        """Ejecuta INSERT/UPDATE/DELETE. Regresa el código generado (si hay)."""
        try:
            cur = self._cursor()
            cur.execute(sql, params)
            nuevo = cur.lastrowid
            cur.close()
            return nuevo
        except mysql.connector.Error as e:
            raise self.traducir(e) from e

    @contextmanager
    def transaccion(self):
        """Agrupa varias instrucciones: se guardan todas o ninguna."""
        self.con.start_transaction()
        try:
            yield
            self.con.commit()
        except Exception:
            self.con.rollback()
            raise

    # ================================================================ carga inicial
    def cargar(self) -> None:
        """Lee todas las tablas y arma los objetos (con sus relaciones)."""
        Repositorio.__init__(self)          # vacía las listas
        c = self.codigo

        roles = {i: Rol(c("ROL", i), nombre)
                 for i, nombre in self.consultar("SELECT codigo, nombre_rol FROM rol ORDER BY codigo")}

        emps = {}
        for i, rol, pila, ap1, ap2, usuario, clave, correo, estado in self.consultar(
                "SELECT codigo, codigo_rol, nombre_pila, ap_1, ap_2, nombre_usuario, contrasena, "
                "correo, estado FROM empleado ORDER BY codigo"):
            emps[i] = Empleado(c("EMP", i), roles[rol], pila, ap1, ap2 or "", usuario, clave, correo, estado)

        for i, emp, dia, ini, fin in self.consultar(
                "SELECT codigo, codigo_empleado, dia, hora_inicio, hora_fin FROM horario ORDER BY codigo"):
            h = Horario(c("HOR", i), emps[emp], dia, a_hora(ini), a_hora(fin))
            emps[emp].horarios.append(h)
            self.horarios.append(h)

        esps = {i: Especialidad(c("ESP", i), nombre, desc or "")
                for i, nombre, desc in self.consultar(
                    "SELECT codigo, nombre, descripcion FROM especialidad ORDER BY codigo")}

        dias_de = {}
        for cla, dia in self.consultar("SELECT codigo_clase, dia FROM clase_dia"):
            dias_de.setdefault(cla, []).append(dia)
        clases = {}
        for i, emp, esp, nombre, ini, fin, cupo, estado, publico in self.consultar(
                "SELECT codigo, codigo_empleado, codigo_especialidad, nombre, hora_inicio, "
                "hora_fin, cupo_max, estado, publico FROM clase ORDER BY codigo"):
            cl = Clase(c("CLA", i), nombre, emps[emp], esps[esp], dias_de.get(i, ["Lunes"]), a_hora(ini),
                       a_hora(fin), cupo, estado, publico == "Sí")
            emps[emp].clases.append(cl)
            esps[esp].clases.append(cl)
            clases[i] = cl

        clientes = {}
        for i, pila, ap1, ap2, nac, estado, colonia, calle in self.consultar(
                "SELECT codigo, nombre_pila, ap_1, ap_2, fecha_nacimiento, estado, colonia, calle "
                "FROM cliente ORDER BY codigo"):
            clientes[i] = Cliente(c("CLI", i), pila, ap1, ap2 or "", nac, colonia, calle, [], estado)
        for cli, numero in self.consultar("SELECT codigo_cliente, num_celular FROM cliente_celular"):
            clientes[cli].celulares.append(numero)

        bens = {i: Beneficio(c("BEN", i), desc)
                for i, desc in self.consultar("SELECT codigo, descripcion FROM beneficio ORDER BY codigo")}
        tipos = {i: TipoMembresia(c("TIP", i), nombre, dias, float(monto))
                 for i, nombre, dias, monto in self.consultar(
                     "SELECT codigo, nombre, duracion_dias, monto FROM tipo_membresia ORDER BY codigo")}
        for tipo, ben in self.consultar(
                "SELECT codigo_tipo_membresia, codigo_beneficio FROM tipo_beneficio "
                "ORDER BY codigo_tipo_membresia, codigo_beneficio"):
            tipos[tipo].beneficios.append(bens[ben])

        mets = {i: MetodoPago(c("MET", i), nombre, estado)
                for i, nombre, estado in self.consultar("SELECT codigo, nombre, estado FROM metodo_pago ORDER BY codigo")}

        mems = {}
        for i, cli, tipo, emp, ini, venc, estado, fcan, motivo in self.consultar(
                "SELECT codigo, codigo_cliente, codigo_tipo_membresia, codigo_empleado, fecha_inicio, "
                "fecha_vencimiento, estado, fecha_cancelacion, motivo_cancelacion FROM membresia ORDER BY codigo"):
            m = Membresia(c("MEM", i), clientes[cli], tipos[tipo], emps[emp], ini, venc, estado, fcan, motivo or "")
            clientes[cli].membresias.append(m)
            tipos[tipo].membresias.append(m)
            mems[i] = m

        for i, mem, met, monto, fecha in self.consultar(
                "SELECT codigo, codigo_membresia, codigo_metodo_pago, monto, fecha_pago FROM pago ORDER BY codigo"):
            p = Pago(c("PAG", i), mems[mem], mets[met], float(monto), fecha)
            mems[mem].pagos.append(p)
            self.pagos.append(p)

        for i, cli, cla, fecha, estado, obs in self.consultar(
                "SELECT codigo, codigo_cliente, codigo_clase, fecha, estado, observaciones "
                "FROM inscripcion_clase ORDER BY codigo"):
            ins = InscripcionClase(c("INS", i), clientes[cli], clases[cla], fecha, estado, obs or "")
            clases[cla].inscripciones.append(ins)
            clientes[cli].inscripciones.append(ins)
            self.inscripciones.append(ins)

        ejs = {i: Ejercicio(c("EJE", i), nombre, desc)
               for i, nombre, desc in self.consultar("SELECT codigo, nombre, descripcion FROM ejercicio ORDER BY codigo")}
        ruts = {}
        for (i, emp, nombre, objetivo, desc, frec, dur, total, descanso, fecha, estado) in self.consultar(
                "SELECT codigo, codigo_empleado, nombre, objetivo, descripcion, frecuencia, duracion_sesion, "
                "total_sesiones, dias_descanso, fecha_creacion, estado FROM rutina ORDER BY codigo"):
            r = Rutina(c("RUT", i), emps[emp], nombre, objetivo, desc or "", frec, dur, total, descanso, fecha, estado)
            emps[emp].rutinas.append(r)
            ruts[i] = r
        enfs = {}
        for i, rut, dia, desc in self.consultar(
                "SELECT codigo, codigo_rutina, dia_rutina, descripcion FROM enfoque ORDER BY codigo_rutina, dia_rutina"):
            en = Enfoque(c("ENF", i), ruts[rut], dia, desc)
            ruts[rut].enfoques.append(en)
            enfs[i] = en
        for enf, eje, orden, series, reps in self.consultar(
                "SELECT codigo_enfoque, codigo_ejercicio, orden, series, repeticiones FROM enfoque_ejercicio "
                "ORDER BY codigo_enfoque, orden"):
            enfs[enf].ejercicios.append(EjercicioEnfoque(ejs[eje], orden, series, reps))
        asigs = {}
        for i, cli, rut, emp, fecha, estado, obs in self.consultar(
                "SELECT codigo, codigo_cliente, codigo_rutina, codigo_empleado, fecha_asignacion, estado, "
                "observaciones FROM asignacion_rutina ORDER BY codigo"):
            a = AsignacionRutina(c("ASR", i), clientes[cli], ruts[rut], emps[emp], fecha, [], estado, obs or "")
            asigs[i] = a
            clientes[cli].asignaciones.append(a)
            ruts[rut].asignaciones.append(a)
            emps[emp].asignaciones.append(a)
            self.asignaciones.append(a)
        for asg, dia in self.consultar("SELECT codigo_asignacion, dia FROM asignacion_dia"):
            asigs[asg].dias.append(dia)
        for a in asigs.values():
            a.dias.sort(key=DIAS.index)
        for i, mem, asg, enf, fecha, asistio, ini, fin, obs in self.consultar(
                "SELECT codigo, codigo_membresia, codigo_asignacion, codigo_enfoque, fecha, asistio, hora_inicio, "
                "hora_fin, observaciones FROM sesion_entrenamiento ORDER BY codigo"):
            ses = SesionEntrenamiento(c("SES", i), mems[mem], fecha, asistio == "Sí", asigs.get(asg), enfs.get(enf),
                                      a_hora(ini) if ini is not None else None,
                                      a_hora(fin) if fin is not None else None, obs or "")
            mems[mem].sesiones.append(ses)
            if ses.asignacion:
                ses.asignacion.sesiones.append(ses)
            self.sesiones.append(ses)

        self.roles, self.empleados = list(roles.values()), list(emps.values())
        self.especialidades, self.clases = list(esps.values()), list(clases.values())
        self.clientes, self.beneficios = list(clientes.values()), list(bens.values())
        self.tipos, self.metodos = list(tipos.values()), list(mets.values())
        self.membresias, self.rutinas = list(mems.values()), list(ruts.values())
        self.ejercicios = list(ejs.values())

    # ================================================================ altas
    def agregar_rol(self, nombre):
        nuevo = self.ejecutar("INSERT INTO rol (nombre_rol) VALUES (%s)", (nombre,))
        rol = Rol(self.codigo("ROL", nuevo), nombre)
        self.roles.append(rol)
        return rol

    def agregar_empleado(self, rol, nombre_pila, ap_1, ap_2, usuario, contrasena, correo):
        if any(e.nombre_usuario == usuario for e in self.empleados):
            raise ReglaNegocio(f"El nombre de usuario «{usuario}» ya existe.")
        nuevo = self.ejecutar(
            "INSERT INTO empleado (codigo_rol, nombre_pila, ap_1, ap_2, nombre_usuario, contrasena, correo) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (self.id_(rol), nombre_pila, ap_1, ap_2 or None, usuario, contrasena, correo))
        emp = Empleado(self.codigo("EMP", nuevo), rol, nombre_pila, ap_1, ap_2, usuario, contrasena, correo)
        self.empleados.append(emp)
        return emp

    def agregar_horario(self, empleado, dia, inicio, fin):
        if fin <= inicio:
            raise ReglaNegocio("La hora de fin debe ser posterior a la de inicio.")
        nuevo = self.ejecutar(
            "INSERT INTO horario (codigo_empleado, dia, hora_inicio, hora_fin) VALUES (%s, %s, %s, %s)",
            (self.id_(empleado), dia, inicio, fin))
        h = Horario(self.codigo("HOR", nuevo), empleado, dia, inicio, fin)
        empleado.horarios.append(h)
        self.horarios.append(h)
        return h

    def agregar_especialidad(self, nombre, descripcion):
        nuevo = self.ejecutar("INSERT INTO especialidad (nombre, descripcion) VALUES (%s, %s)",
                              (nombre, descripcion or None))
        esp = Especialidad(self.codigo("ESP", nuevo), nombre, descripcion)
        self.especialidades.append(esp)
        return esp

    def agregar_clase(self, nombre, empleado, especialidad, dias, inicio, fin, cupo, publico=True):
        if cupo <= 0:
            raise ReglaNegocio("El cupo máximo debe ser mayor que 0.")
        if fin <= inicio:
            raise ReglaNegocio("La hora de fin debe ser posterior a la de inicio.")
        if not dias:
            raise ReglaNegocio("La clase debe tener al menos un día.")
        with self.transaccion():
            nuevo = self.ejecutar(
                "INSERT INTO clase (codigo_empleado, codigo_especialidad, nombre, hora_inicio, hora_fin, "
                "cupo_max, publico) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (self.id_(empleado), self.id_(especialidad), nombre, inicio, fin, cupo,
                 "Sí" if publico else "No"))
            for dia in dict.fromkeys(dias):
                self.ejecutar("INSERT INTO clase_dia (codigo_clase, dia) VALUES (%s, %s)", (nuevo, dia))
        clase = Clase(self.codigo("CLA", nuevo), nombre, empleado, especialidad, list(dias), inicio, fin,
                      cupo, publico=publico)
        empleado.clases.append(clase)
        especialidad.clases.append(clase)
        self.clases.append(clase)
        return clase

    def agregar_cliente(self, nombre_pila, ap_1, ap_2, fecha_nac, colonia, calle, celulares):
        if not celulares:
            raise ReglaNegocio("El cliente debe tener al menos un celular.")
        with self.transaccion():
            nuevo = self.ejecutar(
                "INSERT INTO cliente (nombre_pila, ap_1, ap_2, fecha_nacimiento, colonia, calle) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (nombre_pila, ap_1, ap_2 or None, fecha_nac, colonia, calle))
            for numero in dict.fromkeys(celulares):          # sin repetidos
                self.ejecutar("INSERT INTO cliente_celular (codigo_cliente, num_celular) VALUES (%s, %s)",
                              (nuevo, numero))
        cli = Cliente(self.codigo("CLI", nuevo), nombre_pila, ap_1, ap_2, fecha_nac, colonia, calle,
                      list(dict.fromkeys(celulares)))
        self.clientes.append(cli)
        return cli

    def agregar_beneficio(self, descripcion):
        nuevo = self.ejecutar("INSERT INTO beneficio (descripcion) VALUES (%s)", (descripcion,))
        b = Beneficio(self.codigo("BEN", nuevo), descripcion)
        self.beneficios.append(b)
        return b

    def agregar_tipo(self, nombre, duracion, monto, beneficios=()):
        if duracion <= 0 or monto <= 0:
            raise ReglaNegocio("La duración y el monto deben ser mayores que 0.")
        with self.transaccion():
            nuevo = self.ejecutar(
                "INSERT INTO tipo_membresia (nombre, duracion_dias, monto) VALUES (%s, %s, %s)",
                (nombre, duracion, monto))
            for b in beneficios:
                self.ejecutar("INSERT INTO tipo_beneficio (codigo_tipo_membresia, codigo_beneficio) "
                              "VALUES (%s, %s)", (nuevo, self.id_(b)))
        t = TipoMembresia(self.codigo("TIP", nuevo), nombre, duracion, monto, list(beneficios))
        self.tipos.append(t)
        return t

    def agregar_metodo(self, nombre):
        nuevo = self.ejecutar("INSERT INTO metodo_pago (nombre) VALUES (%s)", (nombre,))
        m = MetodoPago(self.codigo("MET", nuevo), nombre)
        self.metodos.append(m)
        return m

    # ================================================================ operaciones
    def vender_membresia(self, cliente, tipo, empleado, fecha_inicio, metodo, fecha_pago=None):
        """RF-06: membresía + pago en una sola transacción.
        (renovar_membresia, heredado, también usa este método)."""
        if not cliente.activo:
            raise ReglaNegocio("El cliente está dado de baja.")
        if not metodo.activo:
            raise ReglaNegocio("El método de pago está desactivado.")
        fecha_pago = fecha_pago or date.today()
        with self.transaccion():
            # El vencimiento lo calcula el programa (inicio + duración del tipo), así funciona
            # también con la base sencilla, que no tiene triggers.
            vencimiento = fecha_inicio + timedelta(days=tipo.duracion_dias)
            id_mem = self.ejecutar(
                "INSERT INTO membresia (codigo_cliente, codigo_tipo_membresia, codigo_empleado, fecha_inicio, "
                "fecha_vencimiento) VALUES (%s, %s, %s, %s, %s)",
                (self.id_(cliente), self.id_(tipo), self.id_(empleado), fecha_inicio, vencimiento))
            id_pago = self.ejecutar(
                "INSERT INTO pago (codigo_membresia, codigo_metodo_pago, monto, fecha_pago) "
                "VALUES (%s, %s, %s, %s)", (id_mem, self.id_(metodo), tipo.monto, fecha_pago))
        mem = Membresia(self.codigo("MEM", id_mem), cliente, tipo, empleado, fecha_inicio, vencimiento)
        if mem.sincronizar_estado():        # por si se vendió con fecha pasada
            self.ejecutar("UPDATE membresia SET estado = %s WHERE codigo = %s", (mem.estado, id_mem))
        pago = Pago(self.codigo("PAG", id_pago), mem, metodo, tipo.monto, fecha_pago)
        mem.pagos.append(pago)
        cliente.membresias.append(mem)
        tipo.membresias.append(mem)
        self.membresias.append(mem)
        self.pagos.append(pago)
        return mem

    def inscribir(self, cliente, clase, observaciones="", fecha: Optional[date] = None):
        if not cliente.activo:
            raise ReglaNegocio("El cliente está dado de baja.")
        clase.validar_inscripcion(cliente)          # el trigger de la base también lo valida
        fecha = fecha or date.today()
        nuevo = self.ejecutar(
            "INSERT INTO inscripcion_clase (codigo_cliente, codigo_clase, fecha, observaciones) "
            "VALUES (%s, %s, %s, %s)", (self.id_(cliente), self.id_(clase), fecha, observaciones or None))
        ins = InscripcionClase(self.codigo("INS", nuevo), cliente, clase, fecha, observaciones=observaciones)
        clase.inscripciones.append(ins)
        cliente.inscripciones.append(ins)
        self.inscripciones.append(ins)
        return ins

    def agregar_ejercicio(self, nombre, descripcion):
        if any(e.nombre.lower() == nombre.lower() for e in self.ejercicios):
            raise ReglaNegocio(f"Ya existe el ejercicio «{nombre}».")
        nuevo = self.ejecutar("INSERT INTO ejercicio (nombre, descripcion) VALUES (%s, %s)", (nombre, descripcion))
        e = Ejercicio(self.codigo("EJE", nuevo), nombre, descripcion)
        self.ejercicios.append(e)
        return e

    def crear_rutina(self, empleado, nombre, objetivo, descripcion, frecuencia, duracion_sesion,
                     total_sesiones, dias_descanso, enfoques, fecha=None):
        """La rutina, sus enfoques y sus ejercicios se guardan juntos (transacción)."""
        self.validar_rutina(nombre, enfoques)
        fecha = fecha or date.today()
        Rutina("RUT-000", empleado, nombre, objetivo, descripcion, frecuencia, duracion_sesion,
               total_sesiones, dias_descanso, fecha)                      # valida los números
        with self.transaccion():
            id_r = self.ejecutar(
                "INSERT INTO rutina (codigo_empleado, nombre, objetivo, descripcion, frecuencia, duracion_sesion, "
                "total_sesiones, dias_descanso, fecha_creacion) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (self.id_(empleado), nombre, objetivo, descripcion or None, frecuencia, duracion_sesion,
                 total_sesiones, dias_descanso, fecha))
            r = Rutina(self.codigo("RUT", id_r), empleado, nombre, objetivo, descripcion, frecuencia,
                       duracion_sesion, total_sesiones, dias_descanso, fecha)
            for dia, (desc, ejercicios) in enumerate(enfoques, 1):
                id_e = self.ejecutar("INSERT INTO enfoque (codigo_rutina, dia_rutina, descripcion) VALUES (%s, %s, %s)",
                                     (id_r, dia, desc))
                en = Enfoque(self.codigo("ENF", id_e), r, dia, desc)
                for orden, (ej, series, reps) in enumerate(ejercicios, 1):
                    self.ejecutar("INSERT INTO enfoque_ejercicio (codigo_enfoque, codigo_ejercicio, orden, series, "
                                  "repeticiones) VALUES (%s, %s, %s, %s, %s)",
                                  (id_e, self.id_(ej), orden, series, str(reps)))
                    en.ejercicios.append(EjercicioEnfoque(ej, orden, series, str(reps)))
                r.enfoques.append(en)
        empleado.rutinas.append(r)
        self.rutinas.append(r)
        return r

    def asignar_rutina(self, cliente, rutina, empleado, dias, observaciones="", fecha=None):
        """La asignación y sus días de la semana se guardan juntos (transacción)."""
        self.validar_asignacion(cliente, rutina, dias)                     # los triggers también lo revisan
        fecha = fecha or date.today()
        with self.transaccion():
            nuevo = self.ejecutar(
                "INSERT INTO asignacion_rutina (codigo_cliente, codigo_rutina, codigo_empleado, fecha_asignacion, "
                "observaciones) VALUES (%s, %s, %s, %s, %s)",
                (self.id_(cliente), self.id_(rutina), self.id_(empleado), fecha, observaciones or None))
            for d in dias:
                self.ejecutar("INSERT INTO asignacion_dia (codigo_asignacion, dia) VALUES (%s, %s)", (nuevo, d))
        a = AsignacionRutina(self.codigo("ASR", nuevo), cliente, rutina, empleado, fecha, list(dias),
                             observaciones=observaciones)
        cliente.asignaciones.append(a)
        rutina.asignaciones.append(a)
        empleado.asignaciones.append(a)
        self.asignaciones.append(a)
        return a

    def registrar_sesion(self, membresia, fecha, asistio=True, asignacion=None, enfoque=None,
                         hora_inicio=None, hora_fin=None, observaciones=""):
        self.validar_sesion(membresia, asignacion, enfoque, fecha)        # el trigger también lo revisa
        if asistio and hora_inicio is None:
            hora_inicio = datetime.now().time().replace(second=0, microsecond=0)
        if asistio and hora_fin is None:
            hora_inicio, hora_fin = self.horario_sesion(asignacion, hora_inicio)
        if not asistio:
            hora_inicio = hora_fin = None
        ses = SesionEntrenamiento("SES-000", membresia, fecha, asistio, asignacion, enfoque,
                                  hora_inicio, hora_fin, observaciones)    # valida antes de guardar
        ses.codigo = self.codigo("SES", self.ejecutar(
            "INSERT INTO sesion_entrenamiento (codigo_membresia, codigo_asignacion, codigo_enfoque, fecha, asistio, "
            "hora_inicio, hora_fin, observaciones) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (self.id_(membresia), self.id_(asignacion) if asignacion else None,
             self.id_(enfoque) if enfoque else None, fecha, "Sí" if asistio else "No",
             hora_inicio, hora_fin, observaciones or None)))
        membresia.sesiones.append(ses)
        if asignacion:
            asignacion.sesiones.append(ses)
            if asignacion.terminada_por_avance:          # completó el total de sesiones
                asignacion.estado = "Terminada"
                self.ejecutar("UPDATE asignacion_rutina SET estado = 'Terminada' WHERE codigo = %s",
                              (self.id_(asignacion),))
        self.sesiones.append(ses)
        return ses

    def actualizar_estados(self) -> int:
        """Equivale al procedimiento sp_actualizar_vencidas() de la base."""
        self.ejecutar("UPDATE membresia SET estado = 'Vencida' "
                      "WHERE estado = 'Activa' AND fecha_vencimiento < CURDATE()")
        return super().actualizar_estados()

    def recargar(self) -> None:
        """Vuelve a leer toda la base de datos para sincronizar esta instancia
        con cambios que hayan hecho otras instancias del programa."""
        self.cargar()
        self.actualizar_estados()


    # ================================================================ bajas
    def eliminar_horario(self, h):
        self.ejecutar("DELETE FROM horario WHERE codigo = %s", (self.id_(h),))
        super().eliminar_horario(h)

    def eliminar_especialidad(self, esp):
        if esp.clases:
            raise ReglaNegocio("No se puede eliminar: hay clases con esta especialidad.")
        self.ejecutar("DELETE FROM especialidad WHERE codigo = %s", (self.id_(esp),))
        super().eliminar_especialidad(esp)

    def eliminar_beneficio(self, b):
        with self.transaccion():                       # primero se quita de todos los tipos
            self.ejecutar("DELETE FROM tipo_beneficio WHERE codigo_beneficio = %s", (self.id_(b),))
            self.ejecutar("DELETE FROM beneficio WHERE codigo = %s", (self.id_(b),))
        super().eliminar_beneficio(b)

    def eliminar_tipo(self, t):
        if t.membresias:
            raise ReglaNegocio("No se puede eliminar: ya hay membresías vendidas de este tipo.")
        with self.transaccion():
            self.ejecutar("DELETE FROM tipo_beneficio WHERE codigo_tipo_membresia = %s", (self.id_(t),))
            self.ejecutar("DELETE FROM tipo_membresia WHERE codigo = %s", (self.id_(t),))
        super().eliminar_tipo(t)

    # ================================================================ ediciones
    def reasignar_clase(self, clase, empleado, especialidad):
        super().reasignar_clase(clase, empleado, especialidad)
        self.guardar_cambios(clase)

    def guardar_cambios(self, objeto) -> None:
        """Hace el UPDATE del objeto editado (polimorfismo según su clase).
        Si la base lo rechaza, se recargan los datos para deshacer el cambio."""
        acciones = {
            Rol: self._guardar_rol, Empleado: self._guardar_empleado, Horario: self._guardar_horario,
            Especialidad: self._guardar_especialidad, Clase: self._guardar_clase,
            Cliente: self._guardar_cliente, TipoMembresia: self._guardar_tipo,
            MetodoPago: self._guardar_metodo, Membresia: self._guardar_membresia,
            InscripcionClase: self._guardar_inscripcion, Rutina: self._guardar_rutina,
            Ejercicio: self._guardar_ejercicio, AsignacionRutina: self._guardar_asignacion,
        }
        try:
            acciones[type(objeto)](objeto)
        except ReglaNegocio:
            self.cargar()
            raise

    def _guardar_rol(self, r):
        self.ejecutar("UPDATE rol SET nombre_rol = %s WHERE codigo = %s", (r.nombre_rol, self.id_(r)))

    def _guardar_empleado(self, e):
        self.ejecutar(
            "UPDATE empleado SET codigo_rol = %s, nombre_pila = %s, ap_1 = %s, ap_2 = %s, "
            "nombre_usuario = %s, contrasena = %s, correo = %s, estado = %s WHERE codigo = %s",
            (self.id_(e.rol), e.nombre_pila, e.ap_1, e.ap_2 or None, e.nombre_usuario,
             e.contrasena, e.correo, e.estado, self.id_(e)))

    def _guardar_horario(self, h):
        self.ejecutar("UPDATE horario SET dia = %s, hora_inicio = %s, hora_fin = %s WHERE codigo = %s",
                      (h.dia, h.hora_inicio, h.hora_fin, self.id_(h)))

    def _guardar_especialidad(self, e):
        self.ejecutar("UPDATE especialidad SET nombre = %s, descripcion = %s WHERE codigo = %s",
                      (e.nombre, e.descripcion or None, self.id_(e)))

    def _guardar_clase(self, c):
        with self.transaccion():
            self.ejecutar(
                "UPDATE clase SET codigo_empleado = %s, codigo_especialidad = %s, nombre = %s, "
                "hora_inicio = %s, hora_fin = %s, cupo_max = %s, estado = %s, publico = %s WHERE codigo = %s",
                (self.id_(c.empleado), self.id_(c.especialidad), c.nombre, c.hora_inicio,
                 c.hora_fin, c.cupo_max, c.estado, "Sí" if c.publico else "No", self.id_(c)))
            self.ejecutar("DELETE FROM clase_dia WHERE codigo_clase = %s", (self.id_(c),))
            for dia in c.dias:
                self.ejecutar("INSERT INTO clase_dia (codigo_clase, dia) VALUES (%s, %s)", (self.id_(c), dia))

    def _guardar_cliente(self, c):
        with self.transaccion():
            self.ejecutar(
                "UPDATE cliente SET nombre_pila = %s, ap_1 = %s, ap_2 = %s, fecha_nacimiento = %s, "
                "estado = %s, colonia = %s, calle = %s WHERE codigo = %s",
                (c.nombre_pila, c.ap_1, c.ap_2 or None, c.fecha_nacimiento, c.estado,
                 c.colonia, c.calle, self.id_(c)))
            self.ejecutar("DELETE FROM cliente_celular WHERE codigo_cliente = %s", (self.id_(c),))
            for numero in dict.fromkeys(c.celulares):
                self.ejecutar("INSERT INTO cliente_celular (codigo_cliente, num_celular) VALUES (%s, %s)",
                              (self.id_(c), numero))

    def _guardar_tipo(self, t):
        with self.transaccion():
            self.ejecutar("UPDATE tipo_membresia SET nombre = %s, duracion_dias = %s, monto = %s "
                          "WHERE codigo = %s", (t.nombre, t.duracion_dias, t.monto, self.id_(t)))
            self.ejecutar("DELETE FROM tipo_beneficio WHERE codigo_tipo_membresia = %s", (self.id_(t),))
            for b in t.beneficios:
                self.ejecutar("INSERT INTO tipo_beneficio (codigo_tipo_membresia, codigo_beneficio) "
                              "VALUES (%s, %s)", (self.id_(t), self.id_(b)))

    def _guardar_metodo(self, m):
        self.ejecutar("UPDATE metodo_pago SET nombre = %s, estado = %s WHERE codigo = %s",
                      (m.nombre, m.estado, self.id_(m)))

    def _guardar_membresia(self, m):
        self.ejecutar("UPDATE membresia SET estado = %s, fecha_cancelacion = %s, motivo_cancelacion = %s "
                      "WHERE codigo = %s",
                      (m.estado, m.fecha_cancelacion, m.motivo_cancelacion or None, self.id_(m)))

    def _guardar_inscripcion(self, i):
        self.ejecutar("UPDATE inscripcion_clase SET estado = %s, observaciones = %s WHERE codigo = %s",
                      (i.estado, i.observaciones or None, self.id_(i)))

    def _guardar_rutina(self, r):
        self.ejecutar(
            "UPDATE rutina SET nombre = %s, objetivo = %s, descripcion = %s, frecuencia = %s, duracion_sesion = %s, "
            "total_sesiones = %s, dias_descanso = %s, estado = %s WHERE codigo = %s",
            (r.nombre, r.objetivo, r.descripcion or None, r.frecuencia, r.duracion_sesion, r.total_sesiones,
             r.dias_descanso, r.estado, self.id_(r)))

    def _guardar_ejercicio(self, e):
        self.ejecutar("UPDATE ejercicio SET nombre = %s, descripcion = %s WHERE codigo = %s",
                      (e.nombre, e.descripcion, self.id_(e)))

    def _guardar_asignacion(self, a):
        self.ejecutar("UPDATE asignacion_rutina SET estado = %s, observaciones = %s WHERE codigo = %s",
                      (a.estado, a.observaciones or None, self.id_(a)))
