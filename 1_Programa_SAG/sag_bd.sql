-- =====================================================================
--  SAG – Sistema Administrativo de Gimnasios
--  Base de datos (versión sencilla)
--
--  Las mismas tablas y columnas que usa el programa, escritas de la
--  forma más básica: CREATE TABLE con PRIMARY KEY, FOREIGN KEY,
--  NOT NULL, DEFAULT y UNIQUE, y los datos de ejemplo con INSERT.
--  Las reglas (vencimientos, cupo de clases, plan semanal, etc.)
--  las revisa el programa en Python.
--
--  Los datos de ejemplo tienen fechas al 23/11/2026.
-- =====================================================================

DROP DATABASE IF EXISTS sags;
CREATE DATABASE sags CHARACTER SET utf8mb4;
USE sags;
SET NAMES utf8mb4;

-- =====================================================================
-- 1. TABLAS
-- =====================================================================

-- Roles del sistema: Administrador, Recepcionista, Entrenador
CREATE TABLE rol (
    codigo      INT NOT NULL AUTO_INCREMENT,
    nombre_rol  VARCHAR(30) NOT NULL,
    PRIMARY KEY (codigo),
    UNIQUE (nombre_rol)
);

-- Personas que usan el sistema (usuario y contraseña)
CREATE TABLE empleado (
    codigo          INT NOT NULL AUTO_INCREMENT,
    codigo_rol      INT NOT NULL,
    nombre_pila     VARCHAR(50) NOT NULL,
    ap_1            VARCHAR(50) NOT NULL,
    ap_2            VARCHAR(50),
    nombre_usuario  VARCHAR(30) NOT NULL,
    contrasena      VARCHAR(100) NOT NULL,
    correo          VARCHAR(100) NOT NULL,
    estado          ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    PRIMARY KEY (codigo),
    UNIQUE (nombre_usuario),
    UNIQUE (correo),
    FOREIGN KEY (codigo_rol) REFERENCES rol (codigo)
);

-- Días y horas de trabajo de cada empleado
CREATE TABLE horario (
    codigo           INT NOT NULL AUTO_INCREMENT,
    codigo_empleado  INT NOT NULL,
    dia              ENUM('Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo') NOT NULL,
    hora_inicio      TIME NOT NULL,
    hora_fin         TIME NOT NULL,
    PRIMARY KEY (codigo),
    UNIQUE (codigo_empleado, dia),
    FOREIGN KEY (codigo_empleado) REFERENCES empleado (codigo)
);

-- Tipo de actividad de una clase (Yoga, Spinning...)
CREATE TABLE especialidad (
    codigo       INT NOT NULL AUTO_INCREMENT,
    nombre       VARCHAR(50) NOT NULL,
    descripcion  VARCHAR(255),
    PRIMARY KEY (codigo),
    UNIQUE (nombre)
);

-- Clases del gimnasio
CREATE TABLE clase (
    codigo               INT NOT NULL AUTO_INCREMENT,
    codigo_empleado      INT NOT NULL,
    codigo_especialidad  INT NOT NULL,
    nombre               VARCHAR(60) NOT NULL,
    hora_inicio          TIME NOT NULL,
    hora_fin             TIME NOT NULL,
    cupo_max             INT NOT NULL,
    estado               ENUM('Activa','Cerrada') NOT NULL DEFAULT 'Activa',
    publico              ENUM('Sí','No') NOT NULL DEFAULT 'Sí',
    PRIMARY KEY (codigo),
    FOREIGN KEY (codigo_empleado) REFERENCES empleado (codigo),
    FOREIGN KEY (codigo_especialidad) REFERENCES especialidad (codigo)
);

-- Días en que se imparte cada clase
CREATE TABLE clase_dia (
    codigo_clase  INT NOT NULL,
    dia           ENUM('Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo') NOT NULL,
    PRIMARY KEY (codigo_clase, dia),
    FOREIGN KEY (codigo_clase) REFERENCES clase (codigo)
);

-- Personas inscritas al gimnasio
CREATE TABLE cliente (
    codigo            INT NOT NULL AUTO_INCREMENT,
    nombre_pila       VARCHAR(50) NOT NULL,
    ap_1              VARCHAR(50) NOT NULL,
    ap_2              VARCHAR(50),
    fecha_nacimiento  DATE NOT NULL,
    estado            ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    colonia           VARCHAR(60) NOT NULL,
    calle             VARCHAR(100) NOT NULL,
    PRIMARY KEY (codigo)
);

-- Celulares de cada cliente (puede tener varios)
CREATE TABLE cliente_celular (
    codigo_cliente  INT NOT NULL,
    num_celular     CHAR(10) NOT NULL,
    PRIMARY KEY (codigo_cliente, num_celular),
    FOREIGN KEY (codigo_cliente) REFERENCES cliente (codigo)
);

-- Clientes inscritos en cada clase
CREATE TABLE inscripcion_clase (
    codigo          INT NOT NULL AUTO_INCREMENT,
    codigo_cliente  INT NOT NULL,
    codigo_clase    INT NOT NULL,
    fecha           DATE NOT NULL,
    estado          ENUM('Activa','Cancelada') NOT NULL DEFAULT 'Activa',
    observaciones   VARCHAR(255),
    PRIMARY KEY (codigo),
    FOREIGN KEY (codigo_clase) REFERENCES clase (codigo),
    FOREIGN KEY (codigo_cliente) REFERENCES cliente (codigo)
);

-- Catálogo de rutinas que diseñan los entrenadores
CREATE TABLE rutina (
    codigo           INT NOT NULL AUTO_INCREMENT,
    codigo_empleado  INT NOT NULL,
    nombre           VARCHAR(80) NOT NULL,
    objetivo         VARCHAR(100) NOT NULL,
    descripcion      VARCHAR(255),
    frecuencia       INT NOT NULL,
    duracion_sesion  INT NOT NULL,
    total_sesiones   INT NOT NULL,
    dias_descanso    INT NOT NULL,
    fecha_creacion   DATE NOT NULL,
    estado           ENUM('Activa','Inactiva') NOT NULL DEFAULT 'Activa',
    PRIMARY KEY (codigo),
    UNIQUE (nombre),
    FOREIGN KEY (codigo_empleado) REFERENCES empleado (codigo)
);

-- Cada día de una rutina (Día 1: Pierna...)
CREATE TABLE enfoque (
    codigo         INT NOT NULL AUTO_INCREMENT,
    codigo_rutina  INT NOT NULL,
    dia_rutina     INT NOT NULL,
    descripcion    VARCHAR(100) NOT NULL,
    PRIMARY KEY (codigo),
    UNIQUE (codigo_rutina, dia_rutina),
    FOREIGN KEY (codigo_rutina) REFERENCES rutina (codigo)
);

-- Catálogo de ejercicios
CREATE TABLE ejercicio (
    codigo       INT NOT NULL AUTO_INCREMENT,
    nombre       VARCHAR(80) NOT NULL,
    descripcion  VARCHAR(255) NOT NULL,
    PRIMARY KEY (codigo),
    UNIQUE (nombre)
);

-- Ejercicios de cada enfoque con series y repeticiones
CREATE TABLE enfoque_ejercicio (
    codigo_enfoque    INT NOT NULL,
    codigo_ejercicio  INT NOT NULL,
    orden             INT NOT NULL,
    series            INT NOT NULL,
    repeticiones      VARCHAR(20) NOT NULL,
    PRIMARY KEY (codigo_enfoque, codigo_ejercicio),
    FOREIGN KEY (codigo_ejercicio) REFERENCES ejercicio (codigo),
    FOREIGN KEY (codigo_enfoque) REFERENCES enfoque (codigo)
);

-- Rutinas asignadas a cada cliente
CREATE TABLE asignacion_rutina (
    codigo            INT NOT NULL AUTO_INCREMENT,
    codigo_cliente    INT NOT NULL,
    codigo_rutina     INT NOT NULL,
    codigo_empleado   INT NOT NULL,
    fecha_asignacion  DATE NOT NULL,
    estado            ENUM('Activa','Terminada') NOT NULL DEFAULT 'Activa',
    observaciones     VARCHAR(255),
    PRIMARY KEY (codigo),
    FOREIGN KEY (codigo_rutina) REFERENCES rutina (codigo),
    FOREIGN KEY (codigo_empleado) REFERENCES empleado (codigo),
    FOREIGN KEY (codigo_cliente) REFERENCES cliente (codigo)
);

-- Días de la semana en que el cliente hace cada rutina (plan semanal)
CREATE TABLE asignacion_dia (
    codigo_asignacion  INT NOT NULL,
    dia                ENUM('Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo') NOT NULL,
    PRIMARY KEY (codigo_asignacion, dia),
    FOREIGN KEY (codigo_asignacion) REFERENCES asignacion_rutina (codigo)
);

-- Tipos de membresía: Mensual, Trimestral, Anual...
CREATE TABLE tipo_membresia (
    codigo         INT NOT NULL AUTO_INCREMENT,
    nombre         VARCHAR(50) NOT NULL,
    duracion_dias  INT NOT NULL,
    monto          DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (codigo),
    UNIQUE (nombre)
);

-- Beneficios que puede tener una membresía
CREATE TABLE beneficio (
    codigo       INT NOT NULL AUTO_INCREMENT,
    descripcion  VARCHAR(150) NOT NULL,
    PRIMARY KEY (codigo)
);

-- Qué beneficios tiene cada tipo de membresía
CREATE TABLE tipo_beneficio (
    codigo_tipo_membresia  INT NOT NULL,
    codigo_beneficio       INT NOT NULL,
    PRIMARY KEY (codigo_tipo_membresia, codigo_beneficio),
    FOREIGN KEY (codigo_tipo_membresia) REFERENCES tipo_membresia (codigo),
    FOREIGN KEY (codigo_beneficio) REFERENCES beneficio (codigo)
);

-- Formas de pago
CREATE TABLE metodo_pago (
    codigo  INT NOT NULL AUTO_INCREMENT,
    nombre  VARCHAR(40) NOT NULL,
    estado  ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    PRIMARY KEY (codigo),
    UNIQUE (nombre)
);

-- Membresías vendidas a los clientes
CREATE TABLE membresia (
    codigo                 INT NOT NULL AUTO_INCREMENT,
    codigo_cliente         INT NOT NULL,
    codigo_tipo_membresia  INT NOT NULL,
    codigo_empleado        INT NOT NULL,
    fecha_inicio           DATE NOT NULL,
    fecha_vencimiento      DATE,
    estado                 ENUM('Activa','Vencida','Cancelada') NOT NULL DEFAULT 'Activa',
    fecha_cancelacion      DATE,
    motivo_cancelacion     VARCHAR(255),
    PRIMARY KEY (codigo),
    FOREIGN KEY (codigo_tipo_membresia) REFERENCES tipo_membresia (codigo),
    FOREIGN KEY (codigo_empleado) REFERENCES empleado (codigo),
    FOREIGN KEY (codigo_cliente) REFERENCES cliente (codigo)
);

-- Pagos de cada membresía
CREATE TABLE pago (
    codigo              INT NOT NULL AUTO_INCREMENT,
    codigo_membresia    INT NOT NULL,
    codigo_metodo_pago  INT NOT NULL,
    monto               DECIMAL(10,2) NOT NULL,
    fecha_pago          DATE NOT NULL,
    PRIMARY KEY (codigo),
    FOREIGN KEY (codigo_metodo_pago) REFERENCES metodo_pago (codigo),
    FOREIGN KEY (codigo_membresia) REFERENCES membresia (codigo)
);

-- Asistencia: si el cliente asistió o no a lo que le tocaba
CREATE TABLE sesion_entrenamiento (
    codigo             INT NOT NULL AUTO_INCREMENT,
    codigo_membresia   INT NOT NULL,
    codigo_asignacion  INT,
    codigo_enfoque     INT,
    fecha              DATE NOT NULL,
    asistio            ENUM('Sí','No') NOT NULL DEFAULT 'Sí',
    hora_inicio        TIME,
    hora_fin           TIME,
    observaciones      VARCHAR(255),
    PRIMARY KEY (codigo),
    UNIQUE (codigo_membresia, fecha),
    FOREIGN KEY (codigo_membresia) REFERENCES membresia (codigo),
    FOREIGN KEY (codigo_enfoque) REFERENCES enfoque (codigo),
    FOREIGN KEY (codigo_asignacion) REFERENCES asignacion_rutina (codigo)
);

-- =====================================================================
-- 2. DATOS DE EJEMPLO
-- =====================================================================
-- Usuarios de prueba: admin / admin123, recep / recep123,
--                     entrenador / entre123, diana / diana123

-- Roles del sistema: Administrador, Recepcionista, Entrenador
INSERT INTO rol (codigo, nombre_rol) VALUES
    (1, 'Administrador'),
    (2, 'Recepcionista'),
    (3, 'Entrenador');

-- Personas que usan el sistema (usuario y contraseña)
INSERT INTO empleado (codigo, codigo_rol, nombre_pila, ap_1, ap_2, nombre_usuario, contrasena, correo, estado) VALUES
    (1, 1, 'Laura', 'Méndez', 'Ruiz', 'admin', 'admin123', 'laura@sag.mx', 'Activo'),
    (2, 2, 'Sofía', 'Castro', 'León', 'recep', 'recep123', 'sofia@sag.mx', 'Activo'),
    (3, 3, 'Carlos', 'Ramírez', 'Soto', 'entrenador', 'entre123', 'carlos@sag.mx', 'Activo'),
    (4, 3, 'Diana', 'Flores', NULL, 'diana', 'diana123', 'diana@sag.mx', 'Activo');

-- Días y horas de trabajo de cada empleado
INSERT INTO horario (codigo, codigo_empleado, dia, hora_inicio, hora_fin) VALUES
    (1, 1, 'Lunes', '09:00', '17:00'),
    (2, 1, 'Martes', '09:00', '17:00'),
    (3, 1, 'Miércoles', '09:00', '17:00'),
    (4, 1, 'Jueves', '09:00', '17:00'),
    (5, 1, 'Viernes', '09:00', '17:00'),
    (6, 2, 'Lunes', '06:00', '14:00'),
    (7, 2, 'Martes', '06:00', '14:00'),
    (8, 2, 'Miércoles', '06:00', '14:00'),
    (9, 2, 'Jueves', '06:00', '14:00'),
    (10, 2, 'Viernes', '06:00', '14:00'),
    (11, 2, 'Sábado', '06:00', '14:00'),
    (12, 3, 'Lunes', '07:00', '15:00'),
    (13, 3, 'Miércoles', '07:00', '15:00'),
    (14, 3, 'Viernes', '07:00', '15:00'),
    (15, 4, 'Martes', '14:00', '22:00'),
    (16, 4, 'Jueves', '14:00', '22:00'),
    (17, 4, 'Sábado', '14:00', '22:00');

-- Tipo de actividad de una clase (Yoga, Spinning...)
INSERT INTO especialidad (codigo, nombre, descripcion) VALUES
    (1, 'Yoga', 'Flexibilidad, respiración y equilibrio'),
    (2, 'Spinning', 'Ciclismo indoor de alta intensidad'),
    (3, 'Funcional', 'Entrenamiento con peso corporal y circuitos'),
    (4, 'Box', 'Técnica de golpeo y acondicionamiento');

-- Clases del gimnasio
INSERT INTO clase (codigo, codigo_empleado, codigo_especialidad, nombre, hora_inicio, hora_fin, cupo_max, estado, publico) VALUES
    (1, 3, 1, 'Yoga matutino', '07:00', '08:00', 15, 'Activa', 'Sí'),
    (2, 3, 2, 'Spinning power', '08:00', '09:00', 4, 'Activa', 'Sí'),
    (3, 4, 3, 'Funcional total', '18:00', '19:00', 20, 'Activa', 'Sí'),
    (4, 4, 4, 'Box para todos', '19:00', '20:00', 12, 'Activa', 'Sí'),
    (5, 3, 1, 'Yoga privado', '10:00', '11:00', 3, 'Activa', 'No');

-- Días en que se imparte cada clase
INSERT INTO clase_dia (codigo_clase, dia) VALUES
    (1, 'Lunes'),
    (1, 'Miércoles'),
    (2, 'Miércoles'),
    (2, 'Viernes'),
    (3, 'Martes'),
    (3, 'Jueves'),
    (4, 'Jueves'),
    (4, 'Sábado'),
    (5, 'Viernes');

-- Personas inscritas al gimnasio
INSERT INTO cliente (codigo, nombre_pila, ap_1, ap_2, fecha_nacimiento, estado, colonia, calle) VALUES
    (1, 'Ana', 'García', 'López', '1998-03-14', 'Activo', 'Otay', 'Av. Universidad 120'),
    (2, 'Luis', 'Hernández', 'Pérez', '1990-11-02', 'Activo', 'Sendero', 'Calle Pino 45'),
    (3, 'María', 'Torres', 'Vega', '2003-07-21', 'Activo', 'Natura', 'Blvd. Natura 300'),
    (4, 'Jorge', 'Sánchez', NULL, '1985-01-30', 'Activo', 'Santa Fe', 'Calle Olivo 8'),
    (5, 'Fernanda', 'Ortiz', 'Navarro', '2001-09-09', 'Activo', 'Villa Fontana', 'Calle Fresno 77'),
    (6, 'Ricardo', 'Morales', 'Díaz', '1979-05-17', 'Activo', 'El Florido', 'Av. Florido 15'),
    (7, 'Valeria', 'Ruiz', 'Campos', '1996-04-03', 'Activo', 'Otay', 'Calle Cedro 12'),
    (8, 'Diego', 'Navarro', 'Lugo', '1993-12-19', 'Activo', 'Playas', 'Paseo Ensenada 210'),
    (9, 'Camila', 'Rojas', 'Medina', '2000-06-25', 'Activo', 'Sendero', 'Calle Roble 33'),
    (10, 'Andrés', 'Silva', 'Ochoa', '1988-08-11', 'Activo', 'Natura', 'Blvd. Natura 145'),
    (11, 'Paola', 'Castillo', 'Reyes', '1995-02-07', 'Activo', 'Santa Fe', 'Calle Laurel 9'),
    (12, 'Miguel', 'Herrera', 'Sosa', '1991-10-30', 'Activo', 'Villa Fontana', 'Calle Abeto 64');

-- Celulares de cada cliente (puede tener varios)
INSERT INTO cliente_celular (codigo_cliente, num_celular) VALUES
    (1, '6641234567'),
    (2, '6631112233'),
    (2, '6649876543'),
    (3, '6645551122'),
    (4, '6647778899'),
    (5, '6642223344'),
    (6, '6643334455'),
    (7, '6644445566'),
    (8, '6646667788'),
    (9, '6648889900'),
    (10, '6641010101'),
    (11, '6633030303'),
    (11, '6642020202'),
    (12, '6644040404');

-- Clientes inscritos en cada clase
INSERT INTO inscripcion_clase (codigo, codigo_cliente, codigo_clase, fecha, estado, observaciones) VALUES
    (1, 1, 1, '2026-11-20', 'Activa', NULL),
    (2, 7, 1, '2026-11-20', 'Activa', NULL),
    (3, 2, 2, '2026-11-20', 'Activa', NULL),
    (4, 4, 2, '2026-11-20', 'Activa', NULL),
    (5, 5, 2, '2026-11-20', 'Activa', NULL),
    (6, 8, 2, '2026-11-21', 'Activa', NULL),
    (7, 1, 3, '2026-11-14', 'Activa', NULL),
    (8, 2, 3, '2026-11-14', 'Activa', NULL),
    (9, 4, 3, '2026-11-15', 'Activa', NULL),
    (10, 5, 3, '2026-11-15', 'Activa', NULL),
    (11, 7, 3, '2026-11-16', 'Activa', NULL),
    (12, 8, 3, '2026-11-16', 'Activa', NULL),
    (13, 9, 3, '2026-11-17', 'Activa', NULL),
    (14, 10, 3, '2026-11-20', 'Activa', NULL),
    (15, 11, 3, '2026-11-18', 'Activa', NULL),
    (16, 12, 3, '2026-11-19', 'Activa', NULL),
    (17, 3, 3, '2026-10-24', 'Activa', NULL),
    (18, 5, 4, '2026-11-20', 'Activa', NULL),
    (19, 4, 4, '2026-11-20', 'Activa', NULL),
    (20, 12, 4, '2026-11-21', 'Activa', NULL);

-- Catálogo de rutinas que diseñan los entrenadores
INSERT INTO rutina (codigo, codigo_empleado, nombre, objetivo, descripcion, frecuencia, duracion_sesion, total_sesiones, dias_descanso, fecha_creacion, estado) VALUES
    (1, 3, 'Fuerza total 3 días', 'Ganar masa muscular', 'Rutina dividida por grupos musculares con cargas progresivas', 3, 60, 36, 4, '2026-08-25', 'Activa'),
    (2, 4, 'Quema grasa HIIT', 'Bajar de peso', 'Intervalos de alta intensidad y circuitos con poco descanso', 2, 45, 24, 5, '2026-09-04', 'Activa'),
    (3, 3, 'Tonificación integral', 'Tonificación', 'Trabajo de cuerpo completo con peso moderado y muchas repeticiones', 3, 50, 24, 4, '2026-09-14', 'Activa'),
    (4, 4, 'Movilidad y postura', 'Mejorar postura y flexibilidad', 'Ejercicios de movilidad, estabilidad del tronco y estiramientos', 2, 40, 16, 5, '2026-09-24', 'Activa');

-- Cada día de una rutina (Día 1: Pierna...)
INSERT INTO enfoque (codigo, codigo_rutina, dia_rutina, descripcion) VALUES
    (1, 1, 1, 'Pierna y glúteo'),
    (2, 1, 2, 'Pecho y tríceps'),
    (3, 1, 3, 'Espalda y bíceps'),
    (4, 2, 1, 'Cardio por intervalos'),
    (5, 2, 2, 'Circuito funcional'),
    (6, 2, 3, 'Core y abdomen'),
    (7, 3, 1, 'Tren inferior'),
    (8, 3, 2, 'Tren superior'),
    (9, 3, 3, 'Core'),
    (10, 4, 1, 'Movilidad de columna'),
    (11, 4, 2, 'Cadera y glúteo'),
    (12, 4, 3, 'Estabilidad y hombros');

-- Catálogo de ejercicios
INSERT INTO ejercicio (codigo, nombre, descripcion) VALUES
    (1, 'Sentadilla con barra', 'Barra sobre los trapecios; bajar con la espalda recta hasta que los muslos queden paralelos al piso'),
    (2, 'Prensa de piernas', 'En la máquina, empujar la plataforma con los talones sin bloquear las rodillas'),
    (3, 'Peso muerto rumano', 'Bajar la barra pegada a las piernas con la cadera hacia atrás y la espalda neutra'),
    (4, 'Press de banca', 'Acostado en el banco, bajar la barra al pecho y empujar hasta extender los brazos'),
    (5, 'Aperturas con mancuernas', 'Acostado, abrir los brazos en arco hasta estirar el pecho y cerrar arriba'),
    (6, 'Fondos en paralelas', 'Bajar el cuerpo flexionando los codos hasta 90 grados y subir con los tríceps'),
    (7, 'Dominadas', 'Colgado de la barra, subir hasta que la barbilla pase la barra'),
    (8, 'Remo con barra', 'Torso inclinado, jalar la barra hacia el abdomen juntando los omóplatos'),
    (9, 'Curl de bíceps', 'De pie, flexionar los codos subiendo las mancuernas sin mover los hombros'),
    (10, 'Burpees', 'Sentadilla, plancha, flexión y salto vertical, todo seguido'),
    (11, 'Saltar la cuerda', 'Saltos continuos sobre la punta de los pies a ritmo constante'),
    (12, 'Mountain climbers', 'En posición de plancha, llevar las rodillas al pecho alternando rápido'),
    (13, 'Kettlebell swing', 'Balancear la pesa desde la cadera hasta la altura del pecho'),
    (14, 'Zancadas caminando', 'Pasos largos bajando la rodilla trasera cerca del piso'),
    (15, 'Box jump', 'Salto con ambos pies hacia un cajón y bajar con control'),
    (16, 'Plancha', 'Apoyo en antebrazos y puntas de pie, cuerpo recto sin hundir la cadera'),
    (17, 'Crunch abdominal', 'Acostado, despegar los hombros del piso contrayendo el abdomen'),
    (18, 'Elevación de piernas', 'Acostado, subir las piernas rectas hasta 90 grados y bajar sin tocar el piso'),
    (19, 'Sentadilla búlgara', 'Pie trasero sobre un banco, bajar con la pierna de enfrente'),
    (20, 'Hip thrust', 'Espalda apoyada en un banco, empujar la cadera hacia arriba con la barra'),
    (21, 'Press militar', 'De pie, empujar las mancuernas desde los hombros hasta arriba de la cabeza'),
    (22, 'Jalón al pecho', 'En la polea, jalar la barra hacia el pecho con los codos hacia abajo'),
    (23, 'Elevaciones laterales', 'Subir las mancuernas a los lados hasta la altura de los hombros'),
    (24, 'Gato-vaca', 'En cuatro puntos, alternar entre arquear y redondear la espalda'),
    (25, 'Estiramiento de isquiotibiales', 'Sentado, llevar el pecho hacia las piernas estiradas sin rebotar'),
    (26, 'Rotación torácica', 'De lado en el piso, abrir el brazo de arriba girando el torso'),
    (27, 'Puente de glúteo', 'Acostado, subir la cadera apretando los glúteos y sostener'),
    (28, 'Bird dog', 'En cuatro puntos, estirar brazo y pierna contrarios manteniendo el equilibrio'),
    (29, 'Retracción escapular', 'Con banda elástica, juntar los omóplatos sin subir los hombros'),
    (30, 'Movilidad de cadera 90/90', 'Sentado con ambas rodillas a 90 grados, girar la cadera de un lado a otro');

-- Ejercicios de cada enfoque con series y repeticiones
INSERT INTO enfoque_ejercicio (codigo_enfoque, codigo_ejercicio, orden, series, repeticiones) VALUES
    (1, 1, 1, 4, '10'),
    (1, 2, 2, 4, '12'),
    (1, 3, 3, 3, '10'),
    (2, 4, 1, 4, '10'),
    (2, 5, 2, 3, '12'),
    (2, 6, 3, 3, '10'),
    (3, 7, 1, 4, '8'),
    (3, 8, 2, 4, '10'),
    (3, 9, 3, 3, '12'),
    (4, 10, 1, 4, '15'),
    (4, 11, 2, 4, '60 s'),
    (4, 12, 3, 4, '30 s'),
    (5, 13, 1, 4, '15'),
    (5, 14, 2, 3, '12'),
    (5, 15, 3, 3, '10'),
    (6, 16, 1, 3, '45 s'),
    (6, 17, 2, 3, '20'),
    (6, 18, 3, 3, '15'),
    (7, 14, 3, 3, '12'),
    (7, 19, 1, 3, '12'),
    (7, 20, 2, 3, '15'),
    (8, 21, 1, 3, '12'),
    (8, 22, 2, 3, '12'),
    (8, 23, 3, 3, '15'),
    (9, 16, 1, 3, '40 s'),
    (9, 17, 2, 3, '20'),
    (9, 28, 3, 3, '10'),
    (10, 24, 1, 2, '10'),
    (10, 25, 3, 2, '30 s'),
    (10, 26, 2, 2, '8'),
    (11, 19, 3, 2, '10'),
    (11, 27, 2, 3, '12'),
    (11, 30, 1, 2, '8'),
    (12, 16, 3, 3, '30 s'),
    (12, 28, 1, 3, '10'),
    (12, 29, 2, 3, '15');

-- Rutinas asignadas a cada cliente
INSERT INTO asignacion_rutina (codigo, codigo_cliente, codigo_rutina, codigo_empleado, fecha_asignacion, estado, observaciones) VALUES
    (1, 1, 3, 3, '2026-10-19', 'Activa', 'Empezar con 2 kg en las mancuernas'),
    (2, 1, 4, 4, '2026-11-03', 'Activa', 'Hacerla en los días de descanso'),
    (3, 1, 2, 4, '2026-11-13', 'Activa', NULL),
    (4, 2, 1, 3, '2026-11-14', 'Activa', 'Subir carga cada dos semanas'),
    (5, 2, 2, 4, '2026-11-14', 'Activa', 'Combinar con fuerza para entrenar 5 días'),
    (6, 4, 2, 4, '2026-11-05', 'Activa', 'Cuidar la rodilla derecha en los saltos'),
    (7, 4, 4, 4, '2026-11-05', 'Activa', NULL),
    (8, 4, 3, 3, '2026-11-11', 'Activa', NULL),
    (9, 5, 2, 4, '2026-11-19', 'Activa', NULL),
    (10, 7, 3, 3, '2026-11-09', 'Activa', NULL),
    (11, 8, 1, 3, '2026-10-04', 'Activa', 'Ya domina la técnica de sentadilla'),
    (12, 8, 4, 4, '2026-10-24', 'Activa', NULL),
    (13, 12, 1, 3, '2026-11-08', 'Activa', NULL);

-- Días de la semana en que el cliente hace cada rutina (plan semanal)
INSERT INTO asignacion_dia (codigo_asignacion, dia) VALUES
    (1, 'Lunes'),
    (1, 'Miércoles'),
    (1, 'Viernes'),
    (2, 'Sábado'),
    (2, 'Domingo'),
    (3, 'Martes'),
    (3, 'Jueves'),
    (4, 'Lunes'),
    (4, 'Miércoles'),
    (4, 'Viernes'),
    (5, 'Martes'),
    (5, 'Jueves'),
    (6, 'Martes'),
    (6, 'Jueves'),
    (7, 'Sábado'),
    (7, 'Domingo'),
    (8, 'Lunes'),
    (8, 'Miércoles'),
    (8, 'Viernes'),
    (9, 'Lunes'),
    (9, 'Jueves'),
    (10, 'Martes'),
    (10, 'Jueves'),
    (10, 'Sábado'),
    (11, 'Lunes'),
    (11, 'Miércoles'),
    (11, 'Viernes'),
    (12, 'Sábado'),
    (12, 'Domingo'),
    (13, 'Martes'),
    (13, 'Jueves'),
    (13, 'Sábado');

-- Tipos de membresía: Mensual, Trimestral, Anual...
INSERT INTO tipo_membresia (codigo, nombre, duracion_dias, monto) VALUES
    (1, 'Mensual', 30, 500.00),
    (2, 'Trimestral', 90, 1350.00),
    (3, 'Anual', 365, 4800.00),
    (4, 'Estudiante', 30, 400.00);

-- Beneficios que puede tener una membresía
INSERT INTO beneficio (codigo, descripcion) VALUES
    (1, 'Acceso al área de pesas'),
    (2, 'Clases grupales ilimitadas'),
    (3, 'Regaderas y lockers'),
    (4, 'Rutina personalizada'),
    (5, 'Un invitado al mes'),
    (6, 'Evaluación física cada mes'),
    (7, 'Estacionamiento gratuito');

-- Qué beneficios tiene cada tipo de membresía
INSERT INTO tipo_beneficio (codigo_tipo_membresia, codigo_beneficio) VALUES
    (1, 1),
    (1, 3),
    (2, 1),
    (2, 2),
    (2, 3),
    (2, 4),
    (3, 1),
    (3, 2),
    (3, 3),
    (3, 4),
    (3, 5),
    (3, 6),
    (3, 7),
    (4, 1),
    (4, 3);

-- Formas de pago
INSERT INTO metodo_pago (codigo, nombre, estado) VALUES
    (1, 'Efectivo', 'Activo'),
    (2, 'Tarjeta de débito', 'Activo'),
    (3, 'Tarjeta de crédito', 'Activo'),
    (4, 'Transferencia', 'Activo');

-- Membresías vendidas a los clientes
INSERT INTO membresia (codigo, codigo_cliente, codigo_tipo_membresia, codigo_empleado, fecha_inicio, fecha_vencimiento, estado, fecha_cancelacion, motivo_cancelacion) VALUES
    (1, 1, 3, 2, '2026-10-14', '2027-10-14', 'Activa', NULL, NULL),
    (2, 2, 1, 2, '2026-09-14', '2026-10-14', 'Vencida', NULL, NULL),
    (3, 2, 1, 2, '2026-11-13', '2026-12-13', 'Activa', NULL, NULL),
    (4, 3, 4, 2, '2026-10-09', '2026-11-08', 'Vencida', NULL, NULL),
    (5, 4, 2, 2, '2026-11-03', '2027-02-01', 'Activa', NULL, NULL),
    (6, 5, 1, 2, '2026-11-18', '2026-12-18', 'Activa', NULL, NULL),
    (7, 6, 1, 2, '2026-11-11', '2026-12-11', 'Cancelada', '2026-11-23', 'Cambio de ciudad'),
    (8, 7, 2, 2, '2026-11-08', '2027-02-06', 'Activa', NULL, NULL),
    (9, 8, 3, 1, '2026-09-24', '2027-09-24', 'Activa', NULL, NULL),
    (10, 9, 4, 2, '2026-11-15', '2026-12-15', 'Activa', NULL, NULL),
    (11, 10, 1, 2, '2026-11-20', '2026-12-20', 'Activa', NULL, NULL),
    (12, 11, 2, 1, '2026-10-29', '2027-01-27', 'Activa', NULL, NULL),
    (13, 12, 1, 2, '2026-11-05', '2026-12-05', 'Activa', NULL, NULL);

-- Pagos de cada membresía
INSERT INTO pago (codigo, codigo_membresia, codigo_metodo_pago, monto, fecha_pago) VALUES
    (1, 1, 3, 4800.00, '2026-10-14'),
    (2, 2, 1, 500.00, '2026-09-14'),
    (3, 3, 1, 500.00, '2026-11-13'),
    (4, 4, 2, 400.00, '2026-10-09'),
    (5, 5, 2, 1350.00, '2026-11-03'),
    (6, 6, 1, 500.00, '2026-11-18'),
    (7, 7, 3, 500.00, '2026-11-11'),
    (8, 8, 4, 1350.00, '2026-11-08'),
    (9, 9, 3, 4800.00, '2026-09-24'),
    (10, 10, 1, 400.00, '2026-11-15'),
    (11, 11, 2, 500.00, '2026-11-20'),
    (12, 12, 4, 1350.00, '2026-10-29'),
    (13, 13, 1, 500.00, '2026-11-05');

-- Asistencia: si el cliente asistió o no a lo que le tocaba
INSERT INTO sesion_entrenamiento (codigo, codigo_membresia, codigo_asignacion, codigo_enfoque, fecha, asistio, hora_inicio, hora_fin, observaciones) VALUES
    (1, 1, 1, 7, '2026-11-09', 'Sí', '07:00', '07:50', NULL),
    (2, 1, 1, 8, '2026-11-11', 'Sí', '07:00', '07:50', NULL),
    (3, 1, 1, 9, '2026-11-13', 'No', NULL, NULL, NULL),
    (4, 1, 1, 9, '2026-11-16', 'Sí', '07:00', '07:50', NULL),
    (5, 1, 1, 7, '2026-11-18', 'Sí', '07:00', '07:50', NULL),
    (6, 1, 1, 8, '2026-11-20', 'Sí', '07:00', '07:50', NULL),
    (7, 1, 2, 10, '2026-11-14', 'Sí', '07:00', '07:40', NULL),
    (8, 1, 2, 11, '2026-11-15', 'Sí', '07:00', '07:40', NULL),
    (9, 1, 2, 12, '2026-11-21', 'Sí', '07:00', '07:40', NULL),
    (10, 1, 2, 10, '2026-11-22', 'No', NULL, NULL, NULL),
    (11, 1, 3, 4, '2026-11-17', 'Sí', '07:00', '07:45', 'Primera sesión de la rutina'),
    (12, 1, 3, 5, '2026-11-19', 'No', NULL, NULL, NULL),
    (13, 3, 4, 1, '2026-11-16', 'No', NULL, NULL, NULL),
    (14, 3, 4, 1, '2026-11-18', 'Sí', '18:30', '19:30', 'Primera sesión de la rutina'),
    (15, 3, 4, 2, '2026-11-20', 'Sí', '18:30', '19:30', NULL),
    (16, 3, 5, 4, '2026-11-17', 'Sí', '18:30', '19:15', 'Primera sesión de la rutina'),
    (17, 3, 5, 5, '2026-11-19', 'No', NULL, NULL, NULL),
    (18, 5, 6, 4, '2026-11-10', 'No', NULL, NULL, NULL),
    (19, 5, 6, 4, '2026-11-12', 'Sí', '18:30', '19:15', NULL),
    (20, 5, 6, 5, '2026-11-17', 'Sí', '18:30', '19:15', NULL),
    (21, 5, 6, 6, '2026-11-19', 'Sí', '18:30', '19:15', NULL),
    (22, 5, 7, 10, '2026-11-14', 'Sí', '18:30', '19:10', NULL),
    (23, 5, 7, 11, '2026-11-15', 'Sí', '18:30', '19:10', NULL),
    (24, 5, 7, 12, '2026-11-21', 'Sí', '18:30', '19:10', NULL),
    (25, 5, 7, 10, '2026-11-22', 'Sí', '18:30', '19:10', NULL),
    (26, 5, 8, 7, '2026-11-11', 'Sí', '18:30', '19:20', 'Primera sesión de la rutina'),
    (27, 5, 8, 8, '2026-11-13', 'Sí', '18:30', '19:20', NULL),
    (28, 5, 8, 9, '2026-11-16', 'No', NULL, NULL, NULL),
    (29, 5, 8, 9, '2026-11-18', 'Sí', '18:30', '19:20', NULL),
    (30, 5, 8, 7, '2026-11-20', 'Sí', '18:30', '19:20', NULL),
    (31, 6, 9, 4, '2026-11-19', 'No', NULL, NULL, NULL),
    (32, 8, 10, 7, '2026-11-10', 'No', NULL, NULL, NULL),
    (33, 8, 10, 7, '2026-11-12', 'Sí', '07:00', '07:50', 'Primera sesión de la rutina'),
    (34, 8, 10, 8, '2026-11-14', 'Sí', '07:00', '07:50', NULL),
    (35, 8, 10, 9, '2026-11-17', 'Sí', '07:00', '07:50', NULL),
    (36, 8, 10, 7, '2026-11-19', 'Sí', '07:00', '07:50', NULL),
    (37, 8, 10, 8, '2026-11-21', 'Sí', '07:00', '07:50', NULL),
    (38, 9, 11, 1, '2026-11-09', 'Sí', '18:30', '19:30', NULL),
    (39, 9, 11, 2, '2026-11-11', 'Sí', '18:30', '19:30', NULL),
    (40, 9, 11, 3, '2026-11-13', 'No', NULL, NULL, NULL),
    (41, 9, 11, 3, '2026-11-16', 'Sí', '18:30', '19:30', NULL),
    (42, 9, 11, 1, '2026-11-18', 'Sí', '18:30', '19:30', NULL),
    (43, 9, 11, 2, '2026-11-20', 'Sí', '18:30', '19:30', NULL),
    (44, 9, 12, 10, '2026-11-14', 'Sí', '18:30', '19:10', NULL),
    (45, 9, 12, 11, '2026-11-15', 'Sí', '18:30', '19:10', NULL),
    (46, 9, 12, 12, '2026-11-21', 'Sí', '18:30', '19:10', NULL),
    (47, 9, 12, 10, '2026-11-22', 'No', NULL, NULL, NULL),
    (48, 13, 13, 1, '2026-11-10', 'Sí', '18:30', '19:30', NULL),
    (49, 13, 13, 2, '2026-11-12', 'Sí', '18:30', '19:30', NULL),
    (50, 13, 13, 3, '2026-11-14', 'Sí', '18:30', '19:30', NULL),
    (51, 13, 13, 1, '2026-11-17', 'Sí', '18:30', '19:30', NULL),
    (52, 13, 13, 2, '2026-11-19', 'No', NULL, NULL, NULL),
    (53, 13, 13, 2, '2026-11-21', 'Sí', '18:30', '19:30', NULL);
