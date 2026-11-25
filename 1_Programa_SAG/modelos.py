"""
modelos.py – Clases del dominio de SAG (una por entidad del DER, versión 8).

Cada clase representa una entidad del Diagrama Entidad-Relación. Las relaciones
se guardan como referencias a objetos (por ejemplo, Membresia.cliente es un
objeto Cliente), y el lado "muchos" se guarda como lista (Cliente.membresias).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Optional

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


# ---------------------------------------------------------------------------
# Excepciones del sistema
# ---------------------------------------------------------------------------
class ReglaNegocio(Exception):
    """Se lanza cuando una operación viola una regla del gimnasio."""


class Cancelado(Exception):
    """Se lanza cuando el usuario cancela una operación (Enter vacío, 'N', etc.)."""


# ---------------------------------------------------------------------------
# Clase base (herencia): personas con nombre compuesto
# ---------------------------------------------------------------------------
class Persona:
    """Atributo compuesto 'nombre' del DER: nombre_pila, ap_1, ap_2."""

    nombre_pila: str
    ap_1: str
    ap_2: str

    @property
    def nombre_completo(self) -> str:
        return " ".join(p for p in (self.nombre_pila, self.ap_1, self.ap_2) if p)


# ---------------------------------------------------------------------------
# Empleados, roles y horarios
# ---------------------------------------------------------------------------
@dataclass(eq=False)
class Rol:
    codigo: str
    nombre_rol: str


@dataclass(eq=False)
class Empleado(Persona):
    codigo: str
    rol: Rol
    nombre_pila: str
    ap_1: str
    ap_2: str
    nombre_usuario: str
    contrasena: str
    correo: str
    estado: str = "Activo"
    horarios: list = field(default_factory=list, repr=False)
    clases: list = field(default_factory=list, repr=False)
    rutinas: list = field(default_factory=list, repr=False)          # rutinas que diseñó
    asignaciones: list = field(default_factory=list, repr=False)     # rutinas que asignó

    @property
    def activo(self) -> bool:
        return self.estado == "Activo"

    def verificar(self, usuario: str, contrasena: str) -> bool:
        return self.activo and self.nombre_usuario == usuario and self.contrasena == contrasena


@dataclass(eq=False)
class Horario:
    codigo: str
    empleado: Empleado
    dia: str
    hora_inicio: time
    hora_fin: time

    def __post_init__(self):
        if self.hora_fin <= self.hora_inicio:
            raise ReglaNegocio("La hora de fin debe ser posterior a la de inicio.")


# ---------------------------------------------------------------------------
# Clases, especialidades e inscripciones
# ---------------------------------------------------------------------------
@dataclass(eq=False)
class Especialidad:
    codigo: str
    nombre: str
    descripcion: str
    clases: list = field(default_factory=list, repr=False)


@dataclass(eq=False)
class Clase:
    codigo: str
    nombre: str
    empleado: Empleado
    especialidad: Especialidad
    dias: list                      # atributo multivalorado (tabla clase_dia)
    hora_inicio: time
    hora_fin: time
    cupo_max: int
    estado: str = "Activa"
    publico: bool = True
    inscripciones: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        if not self.dias:
            raise ReglaNegocio("La clase debe tener al menos un día.")
        self.dias = sorted(dict.fromkeys(self.dias), key=DIAS.index)

    @property
    def dias_txt(self) -> str:
        return ", ".join(self.dias)

    @property
    def orden(self) -> tuple:
        """Para ordenar las clases por su primer día y su hora."""
        return (DIAS.index(self.dias[0]), self.hora_inicio)

    @property
    def inscritos(self) -> list:
        return [i for i in self.inscripciones if i.estado == "Activa"]

    @property
    def lugares(self) -> int:
        return self.cupo_max - len(self.inscritos)

    @property
    def horario_txt(self) -> str:
        return f"{self.hora_inicio:%H:%M} – {self.hora_fin:%H:%M}"

    def validar_inscripcion(self, cliente: "Cliente") -> None:
        if self.estado != "Activa":
            raise ReglaNegocio("La clase está cerrada.")
        if not self.publico:
            raise ReglaNegocio("La clase no está abierta al público.")
        if self.lugares <= 0:
            raise ReglaNegocio("La clase ya llegó a su cupo máximo.")
        if any(i.cliente is cliente for i in self.inscritos):
            raise ReglaNegocio("El cliente ya está inscrito en esta clase.")


@dataclass(eq=False)
class InscripcionClase:
    codigo: str
    cliente: "Cliente"
    clase: Clase
    fecha: date
    estado: str = "Activa"
    observaciones: str = ""


# ---------------------------------------------------------------------------
# Clientes, rutinas y asistencia
# ---------------------------------------------------------------------------
@dataclass(eq=False)
class Cliente(Persona):
    codigo: str
    nombre_pila: str
    ap_1: str
    ap_2: str
    fecha_nacimiento: date
    colonia: str
    calle: str
    celulares: list = field(default_factory=list)       # atributo multivalorado
    estado: str = "Activo"
    membresias: list = field(default_factory=list, repr=False)
    inscripciones: list = field(default_factory=list, repr=False)
    asignaciones: list = field(default_factory=list, repr=False)     # rutinas asignadas

    @property
    def edad(self) -> int:
        """Atributo derivado: no se guarda, se calcula."""
        hoy, fn = date.today(), self.fecha_nacimiento
        return hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))

    @property
    def direccion(self) -> str:
        return f"{self.calle}, Col. {self.colonia}"

    @property
    def activo(self) -> bool:
        return self.estado == "Activo"

    @property
    def membresia_activa(self) -> Optional["Membresia"]:
        activas = [m for m in self.membresias if m.estado_actual == "Activa"]
        return max(activas, key=lambda m: m.fecha_vencimiento, default=None)

    @property
    def asignaciones_activas(self) -> list:
        return [a for a in self.asignaciones if a.estado == "Activa"]

    @property
    def sesiones(self) -> list:
        return [s for m in self.membresias for s in m.sesiones]

    def asignacion_del_dia(self, dia: date) -> Optional["AsignacionRutina"]:
        """Rutina que le toca al cliente ese día según su plan semanal."""
        nombre = DIAS[dia.weekday()]
        return next((a for a in self.asignaciones_activas if nombre in a.dias), None)

    @property
    def plan_semanal(self) -> dict:
        """{día: asignación o None} para los 7 días de la semana."""
        plan = {d: None for d in DIAS}
        for a in self.asignaciones_activas:
            for d in a.dias:
                plan[d] = a
        return plan

    def sesion_del_dia(self, dia: date) -> Optional["SesionEntrenamiento"]:
        return next((s for s in self.sesiones if s.fecha == dia), None)

    @property
    def situacion(self) -> str:
        """Activa / Vencida / Sin membresía (para reportes)."""
        if self.membresia_activa:
            return "Activa"
        return "Vencida" if self.membresias else "Sin membresía"


@dataclass(eq=False)
class Ejercicio:
    """Catálogo de ejercicios: se reutilizan en muchos enfoques."""
    codigo: str
    nombre: str
    descripcion: str


@dataclass(eq=False)
class EjercicioEnfoque:
    """Atributos de la relación M:M ENFOQUE–EJERCICIO (tabla enfoque_ejercicio)."""
    ejercicio: Ejercicio
    orden: int
    series: int
    repeticiones: str


@dataclass(eq=False)
class Enfoque:
    """Un día de la rutina: «Día 1: Pierna y glúteo»."""
    codigo: str
    rutina: "Rutina"
    dia_rutina: int
    descripcion: str
    ejercicios: list = field(default_factory=list)      # EjercicioEnfoque

    @property
    def titulo(self) -> str:
        return f"Día {self.dia_rutina}: {self.descripcion}"


@dataclass(eq=False)
class Rutina:
    """Rutina del catálogo. La diseña un entrenador y se asigna a muchos clientes."""
    codigo: str
    empleado: Empleado
    nombre: str
    objetivo: str
    descripcion: str
    frecuencia: int           # sesiones por semana
    duracion_sesion: int      # minutos
    total_sesiones: int
    dias_descanso: int        # por semana
    fecha_creacion: date
    estado: str = "Activa"
    enfoques: list = field(default_factory=list, repr=False)
    asignaciones: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        self.validar()

    def validar(self) -> None:
        if not 1 <= self.frecuencia <= 7:
            raise ReglaNegocio("La frecuencia debe ser de 1 a 7 sesiones por semana.")
        if self.dias_descanso < 0 or self.frecuencia + self.dias_descanso > 7:
            raise ReglaNegocio("Frecuencia más días de descanso no puede pasar de 7.")
        if self.duracion_sesion <= 0 or self.total_sesiones <= 0:
            raise ReglaNegocio("La duración y el total de sesiones deben ser mayores que 0.")

    @property
    def activa(self) -> bool:
        return self.estado == "Activa"

    @property
    def total_ejercicios(self) -> int:
        return sum(len(e.ejercicios) for e in self.enfoques)


@dataclass(eq=False)
class AsignacionRutina:
    """Resuelve la relación M:M CLIENTE–RUTINA y fija los días de la semana en que
    el cliente entrena esa rutina (atributo multivalorado «dias»). Con varias
    asignaciones se arma el plan semanal; el sistema guía qué enfoque toca."""
    codigo: str
    cliente: Cliente
    rutina: Rutina
    empleado: Empleado
    fecha_asignacion: date
    dias: list = field(default_factory=list)
    estado: str = "Activa"
    observaciones: str = ""
    sesiones: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        self.dias = sorted(set(self.dias), key=DIAS.index)

    @property
    def dias_txt(self) -> str:
        return ", ".join(d[:3] for d in self.dias)

    @property
    def completadas(self) -> int:
        """Sesiones a las que sí asistió con esta rutina."""
        return sum(s.asistio for s in self.sesiones)

    @property
    def faltas(self) -> int:
        return sum(not s.asistio for s in self.sesiones)

    @property
    def siguiente_enfoque(self) -> Optional["Enfoque"]:
        """El sistema guía la rutina: toca el enfoque que sigue al último completado.
        Si el cliente falta, el enfoque no avanza; al terminar el último vuelve al Día 1."""
        enfoques = sorted(self.rutina.enfoques, key=lambda e: e.dia_rutina)
        return enfoques[self.completadas % len(enfoques)] if enfoques else None

    @property
    def avance_txt(self) -> str:
        return f"{self.completadas} de {self.rutina.total_sesiones}"

    @property
    def terminada_por_avance(self) -> bool:
        return self.completadas >= self.rutina.total_sesiones


# ---------------------------------------------------------------------------
# Membresías, beneficios y pagos
# ---------------------------------------------------------------------------
@dataclass(eq=False)
class Beneficio:
    codigo: str
    descripcion: str


@dataclass(eq=False)
class TipoMembresia:
    codigo: str
    nombre: str
    duracion_dias: int
    monto: float
    beneficios: list = field(default_factory=list)       # relación M:M (TIPO_BENEFICIO)
    membresias: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        if self.duracion_dias <= 0 or self.monto <= 0:
            raise ReglaNegocio("La duración y el monto deben ser mayores que 0.")


@dataclass(eq=False)
class MetodoPago:
    codigo: str
    nombre: str
    estado: str = "Activo"

    @property
    def activo(self) -> bool:
        return self.estado == "Activo"


@dataclass(eq=False)
class Membresia:
    codigo: str
    cliente: Cliente
    tipo: TipoMembresia
    empleado: Empleado
    fecha_inicio: date
    fecha_vencimiento: Optional[date] = None
    estado: str = "Activa"
    fecha_cancelacion: Optional[date] = None
    motivo_cancelacion: str = ""
    pagos: list = field(default_factory=list, repr=False)
    sesiones: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        # La fecha de vencimiento se calcula automáticamente.
        if self.fecha_vencimiento is None:
            self.fecha_vencimiento = self.fecha_inicio + timedelta(days=self.tipo.duracion_dias)

    @property
    def estado_actual(self) -> str:
        if self.estado == "Cancelada":
            return "Cancelada"
        return "Vencida" if self.fecha_vencimiento < date.today() else "Activa"

    def vigente_en(self, dia: date) -> bool:
        return self.estado != "Cancelada" and self.fecha_inicio <= dia <= self.fecha_vencimiento

    @property
    def dias_restantes(self) -> int:
        return (self.fecha_vencimiento - date.today()).days

    @property
    def total_pagado(self) -> float:
        return sum(p.monto for p in self.pagos)

    def sincronizar_estado(self) -> bool:
        """Guarda en 'estado' el valor calculado. Regresa True si cambió."""
        nuevo = self.estado_actual
        cambio = nuevo != self.estado
        self.estado = nuevo
        return cambio

    def cancelar(self, motivo: str) -> None:
        if self.estado_actual == "Cancelada":
            raise ReglaNegocio("La membresía ya estaba cancelada.")
        self.estado = "Cancelada"
        self.fecha_cancelacion = date.today()
        self.motivo_cancelacion = motivo


@dataclass(eq=False)
class Pago:
    codigo: str
    membresia: Membresia
    metodo: MetodoPago
    monto: float
    fecha_pago: date


# ---------------------------------------------------------------------------
# Sesiones de entrenamiento (asistencia al gimnasio)
# ---------------------------------------------------------------------------
@dataclass(eq=False)
class SesionEntrenamiento:
    """Asistencia del cliente en un día: si asistió o no a lo que le tocaba.
    El cliente sale de la membresía; la rutina, de la asignación del plan semanal."""
    codigo: str
    membresia: Membresia
    fecha: date
    asistio: bool = True
    asignacion: Optional[AsignacionRutina] = None
    enfoque: Optional[Enfoque] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    observaciones: str = ""

    def __post_init__(self):
        if self.asistio:
            if not self.hora_inicio or not self.hora_fin or self.hora_fin <= self.hora_inicio:
                raise ReglaNegocio("Una asistencia necesita hora de inicio y una hora final posterior.")
        else:
            self.hora_inicio = self.hora_fin = None
        if (self.asignacion is None) != (self.enfoque is None):
            raise ReglaNegocio("La sesión necesita la rutina asignada y su enfoque, o ninguno.")

    @property
    def cliente(self) -> Cliente:
        return self.membresia.cliente

    @property
    def rutina(self) -> Optional[Rutina]:
        return self.asignacion.rutina if self.asignacion else None

    @property
    def asistio_txt(self) -> str:
        return "Sí" if self.asistio else "No"

    @property
    def minutos(self) -> int:
        if not self.asistio:
            return 0
        return (self.hora_fin.hour * 60 + self.hora_fin.minute) - (self.hora_inicio.hour * 60 + self.hora_inicio.minute)
