CREATE DATABASE gym_app;
USE gym_app;

-- Aquí abajo pegarías el código de las tablas que te pasé antes

CREATE TABLE Usuarios (
    id_usuario INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL, -- Nunca guardamos la contraseña real, sino un texto encriptado
    rol VARCHAR(20) DEFAULT 'ALUMNO',    -- Sirve para diferenciar a los profes de los alumnos
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Clases (
    id_clase INT PRIMARY KEY AUTO_INCREMENT,
    disciplina VARCHAR(50) NOT NULL, -- Ej: 'Jiu-Jitsu', 'MMA', 'Wrestling'
    dia_semana VARCHAR(15) NOT NULL, -- Ej: 'Lunes', 'Jueves'
    hora_inicio TIME NOT NULL,       -- Ej: '19:00:00'
    hora_fin TIME NOT NULL,          -- Ej: '20:00:00'
    cupo_maximo INT DEFAULT 20       -- Límite de personas en el tatami
);

CREATE TABLE Reservas (
    id_reserva INT PRIMARY KEY AUTO_INCREMENT,
    id_usuario INT,
    id_clase INT,
    fecha_reserva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) DEFAULT 'ACTIVA', -- Puede cambiar a 'CANCELADA' si el alumno se baja
    
    -- Aquí creamos las relaciones con las otras tablas:
    FOREIGN KEY (id_usuario) REFERENCES Usuarios(id_usuario),
    FOREIGN KEY (id_clase) REFERENCES Clases(id_clase)
);

-- CARGA DE CLASES DE KICKBOXING (Lunes a Viernes)
INSERT INTO Clases (disciplina, dia_semana, hora_inicio, hora_fin, cupo_maximo) VALUES 
('Kickboxing', 'Lunes', '18:00:00', '19:00:00', 20),
('Kickboxing', 'Martes', '18:00:00', '19:00:00', 20),
('Kickboxing', 'Miércoles', '18:00:00', '19:00:00', 20),
('Kickboxing', 'Jueves', '18:00:00', '19:00:00', 20),
('Kickboxing', 'Viernes', '18:00:00', '19:00:00', 20);

-- CARGA DE CLASES DE JIU-JITSU (Lunes a Viernes)
INSERT INTO Clases (disciplina, dia_semana, hora_inicio, hora_fin, cupo_maximo) VALUES 
('Jiu-Jitsu', 'Lunes', '19:00:00', '20:00:00', 25),
('Jiu-Jitsu', 'Martes', '19:00:00', '20:00:00', 25),
('Jiu-Jitsu', 'Miércoles', '19:00:00', '20:00:00', 25),
('Jiu-Jitsu', 'Jueves', '19:00:00', '20:00:00', 25),
('Jiu-Jitsu', 'Viernes', '19:00:00', '20:00:00', 25);

-- CARGA DE CLASES DE MMA (Solo Lunes, Martes y Miércoles)
INSERT INTO Clases (disciplina, dia_semana, hora_inicio, hora_fin, cupo_maximo) VALUES 
('MMA', 'Lunes', '20:00:00', '21:00:00', 15),
('MMA', 'Martes', '20:00:00', '21:00:00', 15),
('MMA', 'Miércoles', '20:00:00', '21:00:00', 15);

-- CARGA DE CLASES DE WRESTLING (Solo Jueves y Viernes)
INSERT INTO Clases (disciplina, dia_semana, hora_inicio, hora_fin, cupo_maximo) VALUES 
('Wrestling', 'Jueves', '20:00:00', '21:00:00', 15),
('Wrestling', 'Viernes', '20:00:00', '21:00:00', 15);