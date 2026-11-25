"""
repositorio.py – Almacenamiento de datos en memoria.

Por ahora los datos viven en listas de Python y se cargan datos de ejemplo al
iniciar. Cuando se conecte la base de datos MySQL, solo hay que crear otra
clase con los mismos métodos (por ejemplo, RepositorioMySQL) y usarla en
main.py; los menús no cambian.
"""
from __future__ import annotations

import unicodedata
from datetime import date, datetime, time, timedelta
from typing import Optional

from modelos import (
    DIAS, AsignacionRutina, Beneficio, Clase, Cliente, Ejercicio, EjercicioEnfoque, Empleado, Enfoque,
    Especialidad, Horario, InscripcionClase, Membresia, MetodoPago, Pago, ReglaNegocio, Rol, Rutina,
    SesionEntrenamiento, TipoMembresia,
)


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para que «maria» encuentre a «María»."""
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


def coincide_codigo(codigo: str, texto: str) -> bool:
    """Acepta el código completo (CLI-003) o solo el número (3)."""
    t = texto.strip().upper()
    if not t:
        return False
    if t == codigo.upper():
        return True
    return t.isdigit() and int(t) == int(codigo.split("-")[-1])


class Repositorio:
    """Guarda todas las entidades del SAG y aplica las reglas de negocio."""

    def __init__(self):
        self.roles: list[Rol] = []
        self.empleados: list[Empleado] = []
        self.horarios: list[Horario] = []
        self.especialidades: list[Especialidad] = []
        self.clases: list[Clase] = []
        self.clientes: list[Cliente] = []
        self.inscripciones: list[InscripcionClase] = []
        self.rutinas: list[Rutina] = []
        self.ejercicios: list[Ejercicio] = []
        self.asignaciones: list[AsignacionRutina] = []
        self.sesiones: list[SesionEntrenamiento] = []
        self.tipos: list[TipoMembresia] = []
        self.beneficios: list[Beneficio] = []
        self.membresias: list[Membresia] = []
        self.metodos: list[MetodoPago] = []
        self.pagos: list[Pago] = []
        self._contadores: dict[str, int] = {}

    # ------------------------------------------------------------ utilidades
    def nuevo_codigo(self, prefijo: str) -> str:
        n = self._contadores.get(prefijo, 0) + 1
        self._contadores[prefijo] = n
        return f"{prefijo}-{n:03d}"

    @staticmethod
    def por_codigo(lista: list, texto: str):
        return next((x for x in lista if coincide_codigo(x.codigo, texto)), None)

    # ------------------------------------------------------------ consultas
    def autenticar(self, usuario: str, contrasena: str, nombre_rol: str) -> Optional[Empleado]:
        return next((e for e in self.empleados
                     if e.verificar(usuario, contrasena) and e.rol.nombre_rol == nombre_rol), None)

    def entrenadores(self) -> list[Empleado]:
        return [e for e in self.empleados if e.rol.nombre_rol == "Entrenador" and e.activo]

    def buscar_clientes(self, texto: str, solo_activos: bool = False) -> list[Cliente]:
        t = normalizar(texto.strip())
        resultado = [c for c in self.clientes
                     if coincide_codigo(c.codigo, t)
                     or t in normalizar(c.nombre_completo)
                     or any(t in cel for cel in c.celulares)]
        return [c for c in resultado if c.activo] if solo_activos else resultado

    def buscar_membresias(self, texto: str) -> list[Membresia]:
        if texto.strip().upper().startswith("MEM"):
            m = self.por_codigo(self.membresias, texto)
            return [m] if m else []
        return [m for c in self.buscar_clientes(texto) for m in c.membresias]

    def guardar_cambios(self, objeto) -> None:
        """Guarda un objeto que se editó. En memoria no hay nada que hacer;
        RepositorioMySQL sobrescribe este método para hacer el UPDATE."""


    def recargar(self) -> None:
        """Recarga todos los datos desde el origen. En memoria no hay nada que hacer;
        RepositorioMySQL lo sobreescribe para volver a leer la base de datos."""


    def actualizar_estados(self) -> int:
        """Marca como 'Vencida' las membresías cuya fecha ya pasó."""
        return sum(m.sincronizar_estado() for m in self.membresias)

    # ------------------------------------------------------------ altas
    def agregar_rol(self, nombre: str) -> Rol:
        rol = Rol(self.nuevo_codigo("ROL"), nombre)
        self.roles.append(rol)
        return rol

    def agregar_empleado(self, rol, nombre_pila, ap_1, ap_2, usuario, contrasena, correo) -> Empleado:
        if any(e.nombre_usuario == usuario for e in self.empleados):
            raise ReglaNegocio(f"El nombre de usuario «{usuario}» ya existe.")
        emp = Empleado(self.nuevo_codigo("EMP"), rol, nombre_pila, ap_1, ap_2,
                       usuario, contrasena, correo)
        self.empleados.append(emp)
        return emp

    def agregar_horario(self, empleado, dia, inicio, fin) -> Horario:
        h = Horario(self.nuevo_codigo("HOR"), empleado, dia, inicio, fin)
        empleado.horarios.append(h)
        self.horarios.append(h)
        return h

    def eliminar_horario(self, h: Horario) -> None:
        h.empleado.horarios.remove(h)
        self.horarios.remove(h)

    def agregar_especialidad(self, nombre, descripcion) -> Especialidad:
        esp = Especialidad(self.nuevo_codigo("ESP"), nombre, descripcion)
        self.especialidades.append(esp)
        return esp

    def eliminar_especialidad(self, esp: Especialidad) -> None:
        if esp.clases:
            raise ReglaNegocio("No se puede eliminar: hay clases con esta especialidad.")
        self.especialidades.remove(esp)

    def agregar_clase(self, nombre, empleado, especialidad, dias, inicio, fin, cupo, publico=True) -> Clase:
        if cupo <= 0:
            raise ReglaNegocio("El cupo máximo debe ser mayor que 0.")
        if fin <= inicio:
            raise ReglaNegocio("La hora de fin debe ser posterior a la de inicio.")
        clase = Clase(self.nuevo_codigo("CLA"), nombre, empleado, especialidad,
                      list(dias), inicio, fin, cupo, publico=publico)
        empleado.clases.append(clase)
        especialidad.clases.append(clase)
        self.clases.append(clase)
        return clase

    def reasignar_clase(self, clase: Clase, empleado: Empleado, especialidad: Especialidad) -> None:
        clase.empleado.clases.remove(clase)
        clase.especialidad.clases.remove(clase)
        clase.empleado, clase.especialidad = empleado, especialidad
        empleado.clases.append(clase)
        especialidad.clases.append(clase)

    def agregar_cliente(self, nombre_pila, ap_1, ap_2, fecha_nac, colonia, calle, celulares) -> Cliente:
        if not celulares:
            raise ReglaNegocio("El cliente debe tener al menos un celular.")
        cli = Cliente(self.nuevo_codigo("CLI"), nombre_pila, ap_1, ap_2, fecha_nac,
                      colonia, calle, list(celulares))
        self.clientes.append(cli)
        return cli

    def agregar_beneficio(self, descripcion) -> Beneficio:
        b = Beneficio(self.nuevo_codigo("BEN"), descripcion)
        self.beneficios.append(b)
        return b

    def eliminar_beneficio(self, b: Beneficio) -> None:
        for t in self.tipos:
            if b in t.beneficios:
                t.beneficios.remove(b)
        self.beneficios.remove(b)

    def agregar_tipo(self, nombre, duracion, monto, beneficios=()) -> TipoMembresia:
        t = TipoMembresia(self.nuevo_codigo("TIP"), nombre, duracion, monto, list(beneficios))
        self.tipos.append(t)
        return t

    def eliminar_tipo(self, t: TipoMembresia) -> None:
        if t.membresias:
            raise ReglaNegocio("No se puede eliminar: ya hay membresías vendidas de este tipo.")
        self.tipos.remove(t)

    def agregar_metodo(self, nombre) -> MetodoPago:
        m = MetodoPago(self.nuevo_codigo("MET"), nombre)
        self.metodos.append(m)
        return m

    # ------------------------------------------------------------ operaciones
    def vender_membresia(self, cliente: Cliente, tipo: TipoMembresia, empleado: Empleado,
                         fecha_inicio: date, metodo: MetodoPago,
                         fecha_pago: Optional[date] = None) -> Membresia:
        if not cliente.activo:
            raise ReglaNegocio("El cliente está dado de baja.")
        if not metodo.activo:
            raise ReglaNegocio("El método de pago está desactivado.")
        mem = Membresia(self.nuevo_codigo("MEM"), cliente, tipo, empleado, fecha_inicio)
        pago = Pago(self.nuevo_codigo("PAG"), mem, metodo, tipo.monto, fecha_pago or date.today())
        mem.pagos.append(pago)
        mem.sincronizar_estado()
        cliente.membresias.append(mem)
        tipo.membresias.append(mem)
        self.membresias.append(mem)
        self.pagos.append(pago)
        return mem

    @staticmethod
    def fecha_renovacion(mem: Membresia) -> date:
        """La renovación inicia al vencer la actual (o hoy si ya venció)."""
        return max(date.today(), mem.fecha_vencimiento)

    def renovar_membresia(self, mem: Membresia, empleado: Empleado, metodo: MetodoPago) -> Membresia:
        if mem.estado_actual == "Cancelada":
            raise ReglaNegocio("Una membresía cancelada no se renueva; vende una nueva.")
        return self.vender_membresia(mem.cliente, mem.tipo, empleado,
                                     self.fecha_renovacion(mem), metodo)

    def inscribir(self, cliente: Cliente, clase: Clase, observaciones: str = "",
                  fecha: Optional[date] = None) -> InscripcionClase:
        if not cliente.activo:
            raise ReglaNegocio("El cliente está dado de baja.")
        clase.validar_inscripcion(cliente)
        ins = InscripcionClase(self.nuevo_codigo("INS"), cliente, clase,
                               fecha or date.today(), observaciones=observaciones)
        clase.inscripciones.append(ins)
        cliente.inscripciones.append(ins)
        self.inscripciones.append(ins)
        return ins

    # ------------------------------------------------------------ rutinas
    def agregar_ejercicio(self, nombre, descripcion) -> Ejercicio:
        if any(normalizar(e.nombre) == normalizar(nombre) for e in self.ejercicios):
            raise ReglaNegocio(f"Ya existe el ejercicio «{nombre}».")
        e = Ejercicio(self.nuevo_codigo("EJE"), nombre, descripcion)
        self.ejercicios.append(e)
        return e

    def validar_rutina(self, nombre, enfoques, actual=None) -> None:
        """enfoques = [(descripcion, [(ejercicio, series, repeticiones), ...]), ...]"""
        if any(normalizar(r.nombre) == normalizar(nombre) and r is not actual for r in self.rutinas):
            raise ReglaNegocio(f"Ya existe una rutina llamada «{nombre}».")
        if not enfoques:
            raise ReglaNegocio("La rutina necesita al menos un enfoque.")
        for desc, ejercicios in enfoques:
            if not ejercicios:
                raise ReglaNegocio(f"El enfoque «{desc}» no tiene ejercicios.")
            usados = [e for e, _, _ in ejercicios]
            if len(usados) != len(set(map(id, usados))):
                raise ReglaNegocio(f"El enfoque «{desc}» repite un ejercicio.")
            if any(series <= 0 for _, series, _ in ejercicios):
                raise ReglaNegocio("Las series deben ser mayores que 0.")

    def _armar_enfoques(self, rutina, enfoques) -> None:
        rutina.enfoques = []
        for dia, (desc, ejercicios) in enumerate(enfoques, 1):
            en = Enfoque(self.nuevo_codigo("ENF"), rutina, dia, desc)
            en.ejercicios = [EjercicioEnfoque(ej, orden, series, str(reps))
                             for orden, (ej, series, reps) in enumerate(ejercicios, 1)]
            rutina.enfoques.append(en)

    def crear_rutina(self, empleado, nombre, objetivo, descripcion, frecuencia, duracion_sesion,
                     total_sesiones, dias_descanso, enfoques, fecha=None) -> Rutina:
        self.validar_rutina(nombre, enfoques)
        r = Rutina(self.nuevo_codigo("RUT"), empleado, nombre, objetivo, descripcion, frecuencia,
                   duracion_sesion, total_sesiones, dias_descanso, fecha or date.today())
        self._armar_enfoques(r, enfoques)
        empleado.rutinas.append(r)
        self.rutinas.append(r)
        return r

    def enfoques(self) -> list:
        return [e for r in self.rutinas for e in r.enfoques]

    # ------------------------------------------------------------ plan semanal guiado
    @staticmethod
    def dias_libres(cliente, excepto=None) -> list:
        """Días de la semana en que el cliente no entrena ninguna rutina activa."""
        ocupados = {d for a in cliente.asignaciones_activas if a is not excepto for d in a.dias}
        return [d for d in DIAS if d not in ocupados]

    @classmethod
    def proponer_dias(cls, cliente, rutina) -> list:
        """Propone los días para una rutina: reparte su frecuencia entre los días libres,
        dejando un día de por medio cuando se puede (ej. 3 días → Lun, Mié, Vie)."""
        libres = cls.dias_libres(cliente)
        n = rutina.frecuencia
        if len(libres) < n:
            return []
        if len(libres) == n:
            return libres
        paso = len(libres) / n
        return [libres[int(i * paso)] for i in range(n)]

    def validar_asignacion(self, cliente, rutina, dias, actual=None) -> None:
        if not cliente.activo:
            raise ReglaNegocio("El cliente está dado de baja.")
        if not rutina.activa:
            raise ReglaNegocio("La rutina está inactiva.")
        if any(a.rutina is rutina for a in cliente.asignaciones_activas if a is not actual):
            raise ReglaNegocio("El cliente ya tiene asignada esta rutina.")
        if len(set(dias)) != rutina.frecuencia:
            raise ReglaNegocio(f"«{rutina.nombre}» se entrena {rutina.frecuencia} días por semana; "
                               f"elige exactamente {rutina.frecuencia} días.")
        choques = [d for d in dias if d not in self.dias_libres(cliente, excepto=actual)]
        if choques:
            raise ReglaNegocio(f"El cliente ya entrena otra rutina el {', '.join(choques)}.")

    def asignar_rutina(self, cliente, rutina, empleado, dias, observaciones="", fecha=None) -> AsignacionRutina:
        self.validar_asignacion(cliente, rutina, dias)
        a = AsignacionRutina(self.nuevo_codigo("ASR"), cliente, rutina, empleado,
                             fecha or date.today(), list(dias), observaciones=observaciones)
        cliente.asignaciones.append(a)
        rutina.asignaciones.append(a)
        empleado.asignaciones.append(a)
        self.asignaciones.append(a)
        return a

    @staticmethod
    def membresia_en(cliente, dia):
        """Membresía vigente del cliente en esa fecha (la más reciente)."""
        vig = [m for m in cliente.membresias if m.vigente_en(dia)]
        return max(vig, key=lambda m: int(m.codigo.split("-")[-1]), default=None)

    @staticmethod
    def que_le_toca(cliente, dia) -> tuple:
        """(asignación, enfoque) que el plan semanal marca para ese día, o (None, None)."""
        a = cliente.asignacion_del_dia(dia)
        return (a, a.siguiente_enfoque) if a else (None, None)

    @staticmethod
    def validar_sesion(membresia, asignacion, enfoque, fecha) -> None:
        if not membresia.vigente_en(fecha):
            raise ReglaNegocio("La membresía no está vigente en esa fecha.")
        if membresia.cliente.sesion_del_dia(fecha):
            raise ReglaNegocio("Ya se registró la asistencia de este cliente ese día.")
        if asignacion:
            if asignacion.cliente is not membresia.cliente or asignacion.estado != "Activa":
                raise ReglaNegocio("Esa rutina no está asignada al cliente.")
            if DIAS[fecha.weekday()] not in asignacion.dias:
                raise ReglaNegocio("Esa rutina no le toca al cliente ese día.")
            if enfoque not in asignacion.rutina.enfoques:
                raise ReglaNegocio("Ese enfoque no es de la rutina asignada.")

    @staticmethod
    def horario_sesion(asignacion, inicio: time) -> tuple:
        """Hora de inicio y hora final calculada con la duración de la rutina (60 min si es libre)."""
        minutos = asignacion.rutina.duracion_sesion if asignacion else 60
        fin = (datetime.combine(date.today(), inicio) + timedelta(minutes=minutos)).time()
        if fin <= inicio:                                   # cruza la medianoche
            fin = time(23, 59)
        return inicio, fin

    def registrar_sesion(self, membresia, fecha, asistio=True, asignacion=None, enfoque=None,
                         hora_inicio=None, hora_fin=None, observaciones="") -> SesionEntrenamiento:
        """Registra si el cliente asistió o no a lo que le tocaba. Si asistió y no se dan horas,
        la entrada es ahora y la salida se calcula con la duración de la rutina."""
        self.validar_sesion(membresia, asignacion, enfoque, fecha)
        if asistio and hora_inicio is None:
            hora_inicio, hora_fin = self.horario_sesion(asignacion, datetime.now().time().replace(second=0, microsecond=0))
        elif asistio and hora_fin is None:
            hora_inicio, hora_fin = self.horario_sesion(asignacion, hora_inicio)
        s = SesionEntrenamiento(self.nuevo_codigo("SES"), membresia, fecha, asistio, asignacion, enfoque,
                                hora_inicio if asistio else None, hora_fin if asistio else None, observaciones)
        membresia.sesiones.append(s)
        if asignacion:
            asignacion.sesiones.append(s)
            if asignacion.terminada_por_avance:          # completó el total de sesiones
                asignacion.estado = "Terminada"
                self.guardar_cambios(asignacion)
        self.sesiones.append(s)
        return s

    def historial_demo(self, hoy=None) -> None:
        """Genera las sesiones de las últimas dos semanas siguiendo el plan semanal de cada
        asignación (igual que el procedimiento sp_demo_historial de sag_bd.sql)."""
        hoy = hoy or date.today()
        base = date(2000, 1, 1)
        for a in sorted(self.asignaciones, key=lambda x: int(x.codigo.split("-")[-1])):
            n = int(a.codigo.split("-")[-1])
            d = max(a.fecha_asignacion, hoy - timedelta(days=14))
            while d < hoy:
                if DIAS[d.weekday()] in a.dias and a.estado == "Activa":
                    m = self.membresia_en(a.cliente, d)
                    if m:
                        falta = (n * 3 + (d - base).days) % 6 == 0
                        primera = a.completadas == 0 and not falta and a.fecha_asignacion >= hoy - timedelta(days=14)
                        ini = time(7, 0) if int(a.cliente.codigo.split("-")[-1]) % 2 else time(18, 30)
                        self.registrar_sesion(m, d, not falta, a, a.siguiente_enfoque,
                                              *(self.horario_sesion(a, ini) if not falta else (None, None)),
                                              "Primera sesión de la rutina" if primera else "")
                d += timedelta(days=1)

    # ------------------------------------------------------------ datos demo
    def cargar_datos_demo(self) -> None:
        hoy = date.today()
        h = lambda texto: time.fromisoformat(texto)

        admin_rol = self.agregar_rol("Administrador")
        recep_rol = self.agregar_rol("Recepcionista")
        entre_rol = self.agregar_rol("Entrenador")

        admin = self.agregar_empleado(admin_rol, "Laura", "Méndez", "Ruiz", "admin", "admin123",
                                      "laura@sag.mx")
        recep = self.agregar_empleado(recep_rol, "Sofía", "Castro", "León", "recep", "recep123",
                                      "sofia@sag.mx")
        carlos = self.agregar_empleado(entre_rol, "Carlos", "Ramírez", "Soto", "entrenador",
                                       "entre123", "carlos@sag.mx")
        diana = self.agregar_empleado(entre_rol, "Diana", "Flores", "", "diana", "diana123",
                                      "diana@sag.mx")

        for emp, dias, ini, fin in [
            (admin, ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"], "09:00", "17:00"),
            (recep, ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"], "06:00", "14:00"),
            (carlos, ["Lunes", "Miércoles", "Viernes"], "07:00", "15:00"),
            (diana, ["Martes", "Jueves", "Sábado"], "14:00", "22:00"),
        ]:
            for d in dias:
                self.agregar_horario(emp, d, h(ini), h(fin))

        yoga = self.agregar_especialidad("Yoga", "Flexibilidad, respiración y equilibrio")
        spin = self.agregar_especialidad("Spinning", "Ciclismo indoor de alta intensidad")
        func = self.agregar_especialidad("Funcional", "Entrenamiento con peso corporal y circuitos")
        box_ = self.agregar_especialidad("Box", "Técnica de golpeo y acondicionamiento")

        c_yoga = self.agregar_clase("Yoga matutino", carlos, yoga, ["Lunes", "Miércoles"], h("07:00"), h("08:00"), 15)
        c_spin = self.agregar_clase("Spinning power", carlos, spin, ["Miércoles", "Viernes"], h("08:00"), h("09:00"), 4)
        c_func = self.agregar_clase("Funcional total", diana, func, ["Martes", "Jueves"], h("18:00"), h("19:00"), 20)
        c_box = self.agregar_clase("Box para todos", diana, box_, ["Jueves", "Sábado"], h("19:00"), h("20:00"), 12)
        self.agregar_clase("Yoga privado", carlos, yoga, ["Viernes"], h("10:00"), h("11:00"), 3, publico=False)

        bens = [self.agregar_beneficio(d) for d in (
            "Acceso al área de pesas", "Clases grupales ilimitadas", "Regaderas y lockers",
            "Rutina personalizada", "Un invitado al mes", "Evaluación física cada mes",
            "Estacionamiento gratuito")]
        b = lambda *n: [bens[i - 1] for i in n]
        mensual = self.agregar_tipo("Mensual", 30, 500, b(1, 3))
        trimestral = self.agregar_tipo("Trimestral", 90, 1350, b(1, 3, 2, 4))
        anual = self.agregar_tipo("Anual", 365, 4800, b(1, 3, 2, 4, 5, 6, 7))
        estudiante = self.agregar_tipo("Estudiante", 30, 400, b(1, 3))

        efectivo = self.agregar_metodo("Efectivo")
        debito = self.agregar_metodo("Tarjeta de débito")
        credito = self.agregar_metodo("Tarjeta de crédito")
        transfer = self.agregar_metodo("Transferencia")

        datos_clientes = [
            ("Ana", "García", "López", date(1998, 3, 14), "Otay", "Av. Universidad 120", ["6641234567"]),
            ("Luis", "Hernández", "Pérez", date(1990, 11, 2), "Sendero", "Calle Pino 45", ["6649876543", "6631112233"]),
            ("María", "Torres", "Vega", date(2003, 7, 21), "Natura", "Blvd. Natura 300", ["6645551122"]),
            ("Jorge", "Sánchez", "", date(1985, 1, 30), "Santa Fe", "Calle Olivo 8", ["6647778899"]),
            ("Fernanda", "Ortiz", "Navarro", date(2001, 9, 9), "Villa Fontana", "Calle Fresno 77", ["6642223344"]),
            ("Ricardo", "Morales", "Díaz", date(1979, 5, 17), "El Florido", "Av. Florido 15", ["6643334455"]),
            ("Valeria", "Ruiz", "Campos", date(1996, 4, 3), "Otay", "Calle Cedro 12", ["6644445566"]),
            ("Diego", "Navarro", "Lugo", date(1993, 12, 19), "Playas", "Paseo Ensenada 210", ["6646667788"]),
            ("Camila", "Rojas", "Medina", date(2000, 6, 25), "Sendero", "Calle Roble 33", ["6648889900"]),
            ("Andrés", "Silva", "Ochoa", date(1988, 8, 11), "Natura", "Blvd. Natura 145", ["6641010101"]),
            ("Paola", "Castillo", "Reyes", date(1995, 2, 7), "Santa Fe", "Calle Laurel 9", ["6642020202", "6633030303"]),
            ("Miguel", "Herrera", "Sosa", date(1991, 10, 30), "Villa Fontana", "Calle Abeto 64", ["6644040404"]),
        ]
        cli = [self.agregar_cliente(*c) for c in datos_clientes]
        C = lambda n: cli[n - 1]

        ventas = [(1, anual, 40, credito, recep), (2, mensual, 70, efectivo, recep), (2, mensual, 10, efectivo, recep),
                  (3, estudiante, 45, debito, recep), (4, trimestral, 20, debito, recep), (5, mensual, 5, efectivo, recep),
                  (6, mensual, 12, credito, recep), (7, trimestral, 15, transfer, recep), (8, anual, 60, credito, admin),
                  (9, estudiante, 8, efectivo, recep), (10, mensual, 3, debito, recep), (11, trimestral, 25, transfer, admin),
                  (12, mensual, 18, efectivo, recep)]
        mems = [self.vender_membresia(C(n), tipo, emp, hoy - timedelta(days=d), met, fecha_pago=hoy - timedelta(days=d))
                for n, tipo, d, met, emp in ventas]
        mems[6].cancelar("Cambio de ciudad")
        M = lambda n: mems[n - 1]

        for n, clase, d in [(1, c_yoga, 3), (7, c_yoga, 3), (2, c_spin, 3), (4, c_spin, 3), (5, c_spin, 3), (8, c_spin, 2),
                            (1, c_func, 9), (2, c_func, 9), (4, c_func, 8), (5, c_func, 8), (7, c_func, 7), (8, c_func, 7),
                            (9, c_func, 6), (10, c_func, 3), (11, c_func, 5), (12, c_func, 4), (3, c_func, 30),
                            (5, c_box, 3), (4, c_box, 3), (12, c_box, 2)]:
            self.inscribir(C(n), clase, fecha=hoy - timedelta(days=d))

        ej = [self.agregar_ejercicio(n, d) for n, d in EJERCICIOS_DEMO]
        E = lambda n: ej[n - 1]
        def enf(desc, *items):
            return (desc, [(E(n), series, reps) for n, series, reps in items])
        r1 = self.crear_rutina(carlos, "Fuerza total 3 días", "Ganar masa muscular",
                               "Rutina dividida por grupos musculares con cargas progresivas", 3, 60, 36, 4, [
                                   enf("Pierna y glúteo", (1, 4, "10"), (2, 4, "12"), (3, 3, "10")),
                                   enf("Pecho y tríceps", (4, 4, "10"), (5, 3, "12"), (6, 3, "10")),
                                   enf("Espalda y bíceps", (7, 4, "8"), (8, 4, "10"), (9, 3, "12"))],
                               fecha=hoy - timedelta(days=90))
        r2 = self.crear_rutina(diana, "Quema grasa HIIT", "Bajar de peso",
                               "Intervalos de alta intensidad y circuitos con poco descanso", 2, 45, 24, 5, [
                                   enf("Cardio por intervalos", (10, 4, "15"), (11, 4, "60 s"), (12, 4, "30 s")),
                                   enf("Circuito funcional", (13, 4, "15"), (14, 3, "12"), (15, 3, "10")),
                                   enf("Core y abdomen", (16, 3, "45 s"), (17, 3, "20"), (18, 3, "15"))],
                               fecha=hoy - timedelta(days=80))
        r3 = self.crear_rutina(carlos, "Tonificación integral", "Tonificación",
                               "Trabajo de cuerpo completo con peso moderado y muchas repeticiones", 3, 50, 24, 4, [
                                   enf("Tren inferior", (19, 3, "12"), (20, 3, "15"), (14, 3, "12")),
                                   enf("Tren superior", (21, 3, "12"), (22, 3, "12"), (23, 3, "15")),
                                   enf("Core", (16, 3, "40 s"), (17, 3, "20"), (28, 3, "10"))],
                               fecha=hoy - timedelta(days=70))
        r4 = self.crear_rutina(diana, "Movilidad y postura", "Mejorar postura y flexibilidad",
                               "Ejercicios de movilidad, estabilidad del tronco y estiramientos", 2, 40, 16, 5, [
                                   enf("Movilidad de columna", (24, 2, "10"), (26, 2, "8"), (25, 2, "30 s")),
                                   enf("Cadera y glúteo", (30, 2, "8"), (27, 3, "12"), (19, 2, "10")),
                                   enf("Estabilidad y hombros", (28, 3, "10"), (29, 3, "15"), (16, 3, "30 s"))],
                               fecha=hoy - timedelta(days=60))

        L, Ma, Mi, J, V, S, D = DIAS
        # Plan semanal: Ana y Jorge combinan 3 rutinas y entrenan los 7 días (consulta 1).
        for n, rut, emp, d, dias, obs in [
                (1, r3, carlos, 35, [L, Mi, V], "Empezar con 2 kg en las mancuernas"),
                (1, r4, diana, 20, [S, D], "Hacerla en los días de descanso"),
                (1, r2, diana, 10, [Ma, J], ""),
                (2, r1, carlos, 9, [L, Mi, V], "Subir carga cada dos semanas"),
                (2, r2, diana, 9, [Ma, J], "Combinar con fuerza para entrenar 5 días"),
                (4, r2, diana, 18, [Ma, J], "Cuidar la rodilla derecha en los saltos"),
                (4, r4, diana, 18, [S, D], ""),
                (4, r3, carlos, 12, [L, Mi, V], ""),
                (5, r2, diana, 4, [L, J], ""),
                (7, r3, carlos, 14, [Ma, J, S], ""),
                (8, r1, carlos, 50, [L, Mi, V], "Ya domina la técnica de sentadilla"),
                (8, r4, diana, 30, [S, D], ""),
                (12, r1, carlos, 15, [Ma, J, S], "")]:
            self.asignar_rutina(C(n), rut, emp, dias, obs, fecha=hoy - timedelta(days=d))

        self.historial_demo(hoy)
        self.actualizar_estados()


EJERCICIOS_DEMO = [
    ("Sentadilla con barra", "Barra sobre los trapecios; bajar con la espalda recta hasta que los muslos queden paralelos al piso"),
    ("Prensa de piernas", "En la máquina, empujar la plataforma con los talones sin bloquear las rodillas"),
    ("Peso muerto rumano", "Bajar la barra pegada a las piernas con la cadera hacia atrás y la espalda neutra"),
    ("Press de banca", "Acostado en el banco, bajar la barra al pecho y empujar hasta extender los brazos"),
    ("Aperturas con mancuernas", "Acostado, abrir los brazos en arco hasta estirar el pecho y cerrar arriba"),
    ("Fondos en paralelas", "Bajar el cuerpo flexionando los codos hasta 90 grados y subir con los tríceps"),
    ("Dominadas", "Colgado de la barra, subir hasta que la barbilla pase la barra"),
    ("Remo con barra", "Torso inclinado, jalar la barra hacia el abdomen juntando los omóplatos"),
    ("Curl de bíceps", "De pie, flexionar los codos subiendo las mancuernas sin mover los hombros"),
    ("Burpees", "Sentadilla, plancha, flexión y salto vertical, todo seguido"),
    ("Saltar la cuerda", "Saltos continuos sobre la punta de los pies a ritmo constante"),
    ("Mountain climbers", "En posición de plancha, llevar las rodillas al pecho alternando rápido"),
    ("Kettlebell swing", "Balancear la pesa desde la cadera hasta la altura del pecho"),
    ("Zancadas caminando", "Pasos largos bajando la rodilla trasera cerca del piso"),
    ("Box jump", "Salto con ambos pies hacia un cajón y bajar con control"),
    ("Plancha", "Apoyo en antebrazos y puntas de pie, cuerpo recto sin hundir la cadera"),
    ("Crunch abdominal", "Acostado, despegar los hombros del piso contrayendo el abdomen"),
    ("Elevación de piernas", "Acostado, subir las piernas rectas hasta 90 grados y bajar sin tocar el piso"),
    ("Sentadilla búlgara", "Pie trasero sobre un banco, bajar con la pierna de enfrente"),
    ("Hip thrust", "Espalda apoyada en un banco, empujar la cadera hacia arriba con la barra"),
    ("Press militar", "De pie, empujar las mancuernas desde los hombros hasta arriba de la cabeza"),
    ("Jalón al pecho", "En la polea, jalar la barra hacia el pecho con los codos hacia abajo"),
    ("Elevaciones laterales", "Subir las mancuernas a los lados hasta la altura de los hombros"),
    ("Gato-vaca", "En cuatro puntos, alternar entre arquear y redondear la espalda"),
    ("Estiramiento de isquiotibiales", "Sentado, llevar el pecho hacia las piernas estiradas sin rebotar"),
    ("Rotación torácica", "De lado en el piso, abrir el brazo de arriba girando el torso"),
    ("Puente de glúteo", "Acostado, subir la cadera apretando los glúteos y sostener"),
    ("Bird dog", "En cuatro puntos, estirar brazo y pierna contrarios manteniendo el equilibrio"),
    ("Retracción escapular", "Con banda elástica, juntar los omóplatos sin subir los hombros"),
    ("Movilidad de cadera 90/90", "Sentado con ambas rodillas a 90 grados, girar la cadera de un lado a otro"),
]
