-- =============================================================================
-- MeliCrowd — bootstrap do banco
-- Executado uma vez pelo container postgres-melicrowd na primeira subida.
-- O schema das tabelas é gerenciado por Alembic (infra/postgres/migrations).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Schema dedicado para isolar artefatos do MeliCrowd dos defaults do Postgres.
CREATE SCHEMA IF NOT EXISTS melicrowd AUTHORIZATION melicrowd;

ALTER DATABASE melicrowd SET search_path TO melicrowd, public;
