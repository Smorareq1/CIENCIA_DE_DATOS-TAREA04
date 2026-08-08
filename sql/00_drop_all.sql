-- Soft reset: borra objetos del esquema public (mantiene el contenedor/volumen)
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO PUBLIC;
